import datetime

from django import forms
from django.contrib.auth.mixins import LoginRequiredMixin

from data_import.models import StandardizedFile
from data_import.utils import CsvMeta


class UploadForm(LoginRequiredMixin, forms.ModelForm):
    class Meta:
        model = StandardizedFile
        fields = []

    '''
    Collect standardized data.
    '''
    standardized_file = forms.FileField(label='Standardized data file')
    reporting_year = forms.IntegerField(label='Reporting year')

    def _validate_fields(self, incoming_fields):
        missing_fields = ', '.join(set(CsvMeta.REQUIRED_FIELDS) - set(incoming_fields))

        if missing_fields:
            message = 'Standardized file missing fields: {}'.format(missing_fields)
            raise forms.ValidationError(message)

    def _validate_filetype(self, incoming_file_type):
        if incoming_file_type != 'csv':
            raise forms.ValidationError('Please upload a CSV')

    def clean_standardized_file(self):
        s_file = self.cleaned_data['standardized_file']

        meta = CsvMeta(s_file)

        self._validate_filetype(meta.file_type)
        self._validate_fields(meta.field_names)

        now = datetime.datetime.now().strftime('%Y-%m-%dT%H%M%S')
        s_file.name = '{}-{}'.format(now, s_file.name)

        return s_file

    def clean_reporting_year(self):
        reporting_year = self.cleaned_data['reporting_year']

        if reporting_year > datetime.datetime.today().year:
            raise forms.ValidationError('Reporting year cannot exceed the current year')

        return reporting_year
