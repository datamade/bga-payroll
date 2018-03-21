from django import forms


class UploadForm(forms.Form):
    '''
    Collect standardized data.
    '''
    standardized_file = forms.FileField(label='Standardized data file')
    reporting_year = forms.IntegerField(label='Reporting year')
