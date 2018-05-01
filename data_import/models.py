from os.path import basename

from celery.task.control import inspect
from django.contrib.auth import get_user_model
from django.db import connection, models
from django_fsm import FSMField, transition

from bga_database.base_models import SluggedModel
from data_import.tasks import copy_to_database, select_unseen_responding_agency, \
    insert_responding_agency, select_unseen_parent_employer, insert_parent_employer, \
    select_unseen_child_employer, insert_child_employer, select_invalid_salary, \
    insert_salary


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
        upload_to=source_file_upload_name,
        null=True
    )
    responding_agency = models.ForeignKey(
        'RespondingAgency',
        on_delete=models.CASCADE
    )
    reporting_year = models.IntegerField()
    reporting_period_start_date = models.DateField()
    reporting_period_end_date = models.DateField()
    response_date = models.DateField()
    upload = models.ForeignKey(
        'Upload',
        on_delete=models.CASCADE,
        related_name='source_file'
    )
    google_drive_file_id = models.CharField(max_length=255)
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
        if self.source_file:
            return self.source_file.name

        else:
            agency = str(self.responding_agency)
            year = self.reporting_year
            return 'Pending file for {year} from {agency}'.format(agency=agency,
                                                                  year=year)

    def download_from_drive(self):
        '''
        Download file from Google Drive and save it to S3 via the source_file
        field of this model. Do this in a delayed task, rather than on save.
        '''
        raise NotImplementedError


def standardized_file_upload_name(instance, filename):
    fmt = '{year}/payroll/standardized/{filename}'

    return fmt.format(year=instance.reporting_year,
                      filename=basename(filename))


class StandardizedFile(models.Model):
    class State:
        UPLOADED = 'uploaded'
        COPIED = 'copied to database'
        RA_PENDING = 'responding agency unmatched'
        P_EMP_PENDING = 'parent employer unmatched'
        C_EMP_PENDING = 'child employer unmatched'
        SAL_PENDING = 'salary unvalidated'
        COMPLETE = 'complete'

    standardized_file = models.FileField(
        max_length=1000,
        upload_to=standardized_file_upload_name
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
                target=State.COPIED)
    def copy_to_database(self):
        copy_to_database.delay(s_file_id=self.id)

    @transition(field=status,
                source=State.COPIED,
                target=State.RA_PENDING)
    def select_unseen_responding_agency(self):
        select_unseen_responding_agency.delay(s_file_id=self.id)

    @transition(field=status,
                source=State.RA_PENDING,
                target=State.P_EMP_PENDING)
    def select_unseen_parent_employer(self):
        insert_responding_agency.delay(s_file_id=self.id)
        select_unseen_parent_employer.delay(s_file_id=self.id)

    @transition(field=status,
                source=State.P_EMP_PENDING,
                target=State.C_EMP_PENDING)
    def select_unseen_child_employer(self):
        insert_parent_employer.delay(s_file_id=self.id)
        select_unseen_child_employer.delay(s_file_id=self.id)

    @transition(field=status,
                source=State.C_EMP_PENDING,
                target=State.SAL_PENDING)
    def select_invalid_salary(self):
        insert_child_employer.delay(s_file_id=self.id)
        select_invalid_salary.delay(s_file_id=self.id)

    @transition(field=status,
                source=State.SAL_PENDING,
                target=State.COMPLETE)
    def insert_salary(self):
        insert_salary.delay(s_file_id=self.id)


def post_delete_handler(sender, instance, **kwargs):
    try:
        instance.post_delete_handler()

    except AttributeError:  # No custom handler defined.
        pass


models.signals.post_delete.connect(post_delete_handler)
