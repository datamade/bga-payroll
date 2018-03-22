import csv

from csvkit.convert import guess_format
from django import forms


class UploadForm(forms.Form):
    '''
    Collect standardized data.
    '''
    standardized_file = forms.FileField(label='Standardized data file')
    reporting_year = forms.IntegerField(label='Reporting year')

    def _clean_incoming_fields(self, incoming_fields):
        def clean(field):
            return '_'.join(field.strip().lower().split(' '))

        return [clean(field) for field in incoming_fields]

    def _validate_fields(self, incoming_file):
        content = [line.decode() for line in incoming_file.file.readlines()]
        reader = csv.DictReader(content)
        incoming_fields = self._clean_incoming_fields(reader.fieldnames)

        required_fields = [
            'responding_agency',
            'employer',
            'last_name',
            'first_name',
            'title',
            'department',
            'salary',
            'date_started',
            'data_year',
        ]

        if set(incoming_fields) != set(required_fields):
            missing_fields = ', '.join(set(required_fields) - set(incoming_fields))
            message = 'Standardized file missing fields: {}'.format(missing_fields)
            raise forms.ValidationError(message)

    def _validate_filetype(self, incoming_file):
        s_file_type = guess_format(incoming_file.name.lower())

        if s_file_type != 'csv':
            raise forms.ValidationError('Please upload a CSV')

    def clean_standardized_file(self):
        s_file = self.cleaned_data['standardized_file']

        self._validate_filetype(s_file)
        self._validate_fields(s_file)

        return self.cleaned_data['standardized_file']
