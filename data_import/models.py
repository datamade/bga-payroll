from django.db import models


class Upload(models.Model):
    '''
    Class for keeping track of upload events.

    Proposed fields:
    - id
    - created_at
    - created_by
    '''
    pass


class SourceFile(models.Model):
    '''
    Class for keeping track of source files.

    Proposed fields:
    - id
    - file (https://docs.djangoproject.com/en/2.0/ref/models/fields/#django.db.models.FileField.upload_to)
    - reporting_agency
    - reporting_period_start (default Jan. 1 of given year)
    - reporting_period_end (default Dec. 31 of given year)
    - upload - Upload foreign key

    Add a SourceFile foreign key to each model. For models whose objects can
    appear in many years of data – i.e., Employer, Person – this should be
    a ManyToManyField. As a bonus, the data is connected to Upload/s via its
    related SourceFile/s.
    '''
    pass
