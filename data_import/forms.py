from django import forms


class UploadForm(forms.Form):
    '''
    Collect standardized data, and related source document/s.

    Proposed fields:
    - data - standardized payroll data
    - source - raw response file or files (https://docs.djangoproject.com/en/1.11/topics/http/file-uploads/#uploading-multiple-files)
    - reporting_agency - Django autocomplete field for querying existing
    agencies, also allows creation of a new agency, if necessary
    '''
    pass