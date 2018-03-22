from django.contrib.auth import get_user_model
from django.db import models

from payroll.models import SluggedModel


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


def upload_name(instance, filename):
    year = instance.reporting_year
    agency = instance.responding_agency.slug

    return '{year}/payroll/{agency}/{filename}'.format(year=year,
                                                       agency=agency,
                                                       filename=filename)


class SourceFile(models.Model):
    '''
    Model for keeping track of source files.

    Add a SourceFile foreign key to each model. For models whose objects can
    appear in many years of data – i.e., Employer, Person – this should be
    a ManyToManyField. As a bonus, the data is connected to Upload/s via its
    related SourceFile/s.
    '''
    source_file = models.FileField(max_length=1000, upload_to=upload_name, null=True)
    responding_agency = models.ForeignKey('RespondingAgency', on_delete=models.CASCADE)
    reporting_year = models.IntegerField()
    reporting_period_start_date = models.DateField()
    reporting_period_end_date = models.DateField()
    response_date = models.DateField()
    upload = models.ForeignKey('Upload', on_delete=models.CASCADE, related_name='files')
    google_drive_file_id = models.CharField(max_length=255)

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