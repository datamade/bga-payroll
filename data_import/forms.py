import csv
import datetime

from cchardet import UniversalDetector
from csvkit.convert import guess_format
from django import forms


class UploadForm(forms.Form):
    '''
    Collect standardized data.
    '''
    FILE_ENCODING = 'utf-8'

    standardized_file = forms.FileField(label='Standardized data file')
    reporting_year = forms.IntegerField(label='Reporting year')

    def _get_incoming_fields(self, incoming_file):
        chunk = next(incoming_file.chunks())

        try:
            content = chunk.decode('utf-8').splitlines()

        except UnicodeDecodeError:
            encoding = self._get_encoding(incoming_file)
            self.FILE_ENCODING = encoding
            content = chunk.decode(encoding).splitlines()

        finally:
            reader = csv.reader(content)

        fields = next(reader)

        return [self._clean_incoming_field(field) for field in fields]

    def _get_encoding(self, incoming_file):
        detector = UniversalDetector()

        for line in incoming_file.readlines():
            detector.feed(line)
            if detector.done:
                break

        detector.close()
        encoding = detector.result['encoding']

        return encoding

    def _clean_incoming_field(self, field):
        return '_'.join(field.strip().lower().split(' '))

    def _validate_fields(self, incoming_fields):
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

        missing_fields = ', '.join(set(required_fields) - set(incoming_fields))

        if missing_fields:
            message = 'Standardized file missing fields: {}'.format(missing_fields)
            raise forms.ValidationError(message)

    def _validate_filetype(self, incoming_file):
        s_file_type = guess_format(incoming_file.name.lower())

        if s_file_type != 'csv':
            raise forms.ValidationError('Please upload a CSV')

    def clean_standardized_file(self):
        s_file = self.cleaned_data['standardized_file']

        self._validate_filetype(s_file)

        fields = self._get_incoming_fields(s_file)
        self._validate_fields(fields)

        return s_file

    def clean_reporting_year(self):
        reporting_year = self.cleaned_data['reporting_year']

        if reporting_year > datetime.datetime.today().year:
            raise forms.ValidationError('Reporting year cannot exceed the current year')

        return reporting_year
