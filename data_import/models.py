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
    - filename
    - upload - Upload foreign key

    Add a SourceFile foreign key to each model. For models whose objects can
    appear in many years of data – i.e., Employer, Person – this should be
    a ManyToManyField. As a bonus, the data is connected to Upload/s via its
    related SourceFile/s.
    '''
    pass
