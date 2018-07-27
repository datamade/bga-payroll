from os.path import basename

from celery import chain
from django.contrib.auth import get_user_model
from django.db import connection, models
from django_fsm import FSMField, transition

from bga_database.base_models import SluggedModel
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
    '''
    Model for keeping track of reporting agencies.
    '''
    name = models.CharField(max_length=255)

    def __str__(self):
        return self.name


def source_file_upload_name(instance, filename):
    fmt = '{year}/payroll/source/{agency}/{filename}'

    return fmt.format(year=instance.reporting_year,
                      agency=instance.responding_agency.slug,
                      filename=filename)


class SourceFile(models.Model):
    '''
    Model for keeping track of source files.

    Add a SourceFile foreign key to each model. For models whose objects can
    appear in many years of data – i.e., Employer, Person – this should be
    a ManyToManyField. As a bonus, the data is connected to Upload/s via its
    related SourceFile/s.
    '''
    source_file = models.FileField(
        max_length=1000,
        upload_to=source_file_upload_name
    )
    responding_agency = models.ForeignKey(
        'RespondingAgency',
        related_name='source_files',
        on_delete=models.CASCADE,
        help_text='''
            If your responding agency is not in the list, click the green plus
            sign to add it.
        '''
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
    standardized_file = models.ForeignKey(
        'StandardizedFile',
        on_delete=models.SET_NULL,
        null=True,
        related_name='source_files'
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

    @property
    def raw_table_name(self):
        return 'raw_payroll_{}'.format(self.id)

    @property
    def intermediate_table_name(self):
        return 'intermediate_payroll_{}'.format(self.id)

    @property
    def processing(self):
        '''
        TO-DO: Find a less expensive way to check whether an instance
        is processing.
        '''
        return False

    @property
    def review_step(self):
        return '-'.join(self.status.split(' ')[:-1])

    def post_delete_handler(self):
        '''
        Drop the associated raw table.
        '''
        with connection.cursor() as cursor:
            cursor.execute('DROP TABLE IF EXISTS {}'.format(self.raw_table_name))

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
            tasks.reshape_raw_payroll.si(s_file_id=self.id),
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
    def select_invalid_salary(self):
        work = chain(
            tasks.insert_child_employer.si(s_file_id=self.id),
            tasks.select_invalid_salary.si(s_file_id=self.id),
            tasks.insert_salary.si(s_file_id=self.id),
            tasks.build_solr_index.si()
        )

        work.apply_async()


def post_delete_handler(sender, instance, **kwargs):
    try:
        instance.post_delete_handler()

    except AttributeError:  # No custom handler defined.
        pass


models.signals.post_delete.connect(post_delete_handler)
