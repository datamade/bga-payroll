import ast
import datetime
from os.path import basename

from celery import chain
from celery.task.control import inspect, revoke
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import connection, models
from django_fsm import FSMField, transition

from bga_database.base_models import AliasModel, SluggedModel
from data_import import tasks


def set_deleted_user():
    return get_user_model().objects.get_or_create(username='deleted').first()


class Upload(models.Model):
    '''
    Model for keeping track of upload events.

    When adding source files via Gmail, one upload event is created for each
    batch. In these cases, `created_by` is null.

    Similarly, one upload event is created for each standardized data upload.
    `created_by` is the authenticated user.
    '''
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(get_user_model(), null=True, on_delete=models.SET(set_deleted_user))

    def __str__(self):
        if self.created_by:
            return '{user} on {date}'.format(user=str(self.created_by),
                                             date=self.created_at)
        else:
            return '{date}'.format(date=self.created_at)


class RespondingAgency(SluggedModel):
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


class RespondingAgencyAlias(AliasModel):
    entity_type = 'responding_agency'
    responding_agency = models.ForeignKey(
        'RespondingAgency',
        related_name='aliases',
        on_delete=models.CASCADE
    )

    def clean(self):
        super().clean()

        duplicate_alias = type(self).objects.filter(name=self.name)
        if len(duplicate_alias) == 1:
            raise ValidationError('{} name must be unique.'.format(self))


def source_file_upload_name(instance, filename):
    fmt = '{year}/payroll/source/{agency}/{filename}'

    return fmt.format(year=instance.reporting_year,
                      agency=instance.responding_agency.slug,
                      filename=filename)


class SourceFile(models.Model):
    source_file = models.FileField(
        max_length=1000,
        upload_to=source_file_upload_name
    )
    responding_agency = models.ForeignKey(
        'RespondingAgency',
        related_name='source_files',
        on_delete=models.CASCADE
    )
    reporting_year = models.IntegerField()
    # Date fields are blank so they are not required in the admin interface.
    # A default is set as described in the help text, if they are not
    # provided.
    reporting_period_start_date = models.DateField(
        help_text='Leave blank for Jan. 1 of reporting year',
        blank=True
    )
    reporting_period_end_date = models.DateField(
        help_text='Leave blank for Dec. 31 of reporting year',
        blank=True
    )
    response_date = models.DateField(null=True)
    upload = models.ForeignKey(
        'Upload',
        on_delete=models.CASCADE,
        related_name='source_file'
    )

    def save(self, *args, **kwargs):
        self.reporting_year = self.reporting_period_start_date.year
        super().save()

    def __str__(self):
        # For FieldFile API:
        # https://docs.djangoproject.com/en/2.0/ref/models/fields/#django.db.models.fields.files.FieldFile
        return '{0} – {1}'.format(self.responding_agency, self.reporting_year)


def standardized_file_upload_name(instance, filename):
    fmt = '{year}/payroll/standardized/{filename}'

    return fmt.format(year=instance.reporting_year,
                      filename=basename(filename))


class StandardizedFile(models.Model):
    class State:
        UPLOADED = 'uploaded'
        RA_PENDING = 'responding agency unmatched'
        P_EMP_PENDING = 'parent employer unmatched'
        C_EMP_PENDING = 'child employer unmatched'
        SAL_PENDING = 'salary unvalidated'
        COMPLETE = 'complete'

    standardized_file = models.FileField(
        max_length=1000,
        upload_to=standardized_file_upload_name
    )
    responding_agencies = models.ManyToManyField(
        'RespondingAgency',
        related_name='standardized_files'
    )
    reporting_year = models.IntegerField()
    upload = models.ForeignKey(
        'Upload',
        on_delete=models.CASCADE,
        related_name='standardized_file'
    )
    status = FSMField(default=State.UPLOADED)

    def __str__(self):
        return str(self.standardized_file)

    @property
    def raw_table_name(self):
        return 'raw_payroll_{}'.format(self.id)

    @property
    def review_step(self):
        return '-'.join(self.status.split(' ')[:-1])

    def _add_runtime(self, task):
        start_time = datetime.datetime.fromtimestamp(task['time_start'])
        now = datetime.datetime.utcnow()

        runtime = relativedelta(now, start_time)
        task['runtime'] = '{} hours, {} minutes'.format(runtime.hours, runtime.minutes)

        return task

    def get_task(self):
        inspector = inspect()

        for _, task_array in inspector.active().items():
            for task in task_array:
                kw_args = ast.literal_eval(task['kwargs'])
                if kw_args.get('s_file_id') == self.id:
                    return self._add_runtime(task)

        for _, task_array in inspector.reserved().items():
            for task in task_array:
                kw_args = ast.literal_eval(task['kwargs'])
                if kw_args.get('s_file_id') == self.id:
                    return self._add_runtime(task)

    @transition(field=status,
                source=State.UPLOADED,
                target=State.RA_PENDING)
    def copy_to_database(self):
        work = chain(
            tasks.copy_to_database.si(s_file_id=self.id),
            tasks.select_unseen_responding_agency.si(s_file_id=self.id)
        )

        work.apply_async()

    @transition(field=status,
                source=State.RA_PENDING,
                target=State.P_EMP_PENDING)
    def select_unseen_parent_employer(self):
        work = chain(
            tasks.insert_responding_agency.si(s_file_id=self.id),
            tasks.select_unseen_parent_employer.si(s_file_id=self.id)
        )

        work.apply_async()

    @transition(field=status,
                source=State.P_EMP_PENDING,
                target=State.C_EMP_PENDING)
    def select_unseen_child_employer(self):
        work = chain(
            tasks.insert_parent_employer.si(s_file_id=self.id),
            tasks.select_unseen_child_employer.si(s_file_id=self.id)
        )

        work.apply_async()

    @transition(field=status,
                source=State.C_EMP_PENDING,
                target=State.COMPLETE)
    def insert_salaries(self):
        work = chain(
            tasks.insert_child_employer.si(s_file_id=self.id),
            tasks.insert_salaries.si(s_file_id=self.id),
            tasks.build_solr_index.si(s_file_id=self.id)
        )

        work.apply_async()

    def post_delete_handler(self):
        '''
        Remove related objects, revoke delayed work, and drop raw tables, if
        they exist.
        '''
        print('Revoking work')
        task = self.get_task()

        if task:
            revoke(task['id'], terminate=True)

        print('Removing related responding agencies')
        self.responding_agencies.clear()

        with connection.cursor() as cursor:
            for table in ('raw_payroll_{}', 'raw_person_{}', 'raw_job_{}'):
                table_name = table.format(self.id)
                print('Dropping {}'.format(table_name))
                cursor.execute('DROP TABLE IF EXISTS {}'.format(table_name))


def post_delete_handler(sender, instance, **kwargs):
    try:
        instance.post_delete_handler()

    except AttributeError:  # No custom handler defined.
        pass


models.signals.post_delete.connect(post_delete_handler)
