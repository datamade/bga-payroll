import csv
import itertools
from os.path import basename

from cchardet import UniversalDetector
from csvkit.convert import guess_format
from django.db.models.fields.files import FieldFile

from data_import.exceptions import OperationNotPermittedOnInstance


class CsvMeta(object):
    '''
    Utility class for metadata about `incoming_file`, which can be an
    uploaded data file (django.core.files.uploadedfile.UploadedFile) or
    a file stored with a model (django.db.models.fields.files.FieldFile).
    '''
    REQUIRED_FIELDS = [
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

    def __init__(self, incoming_file):
        self.file = incoming_file

        # We need two copies of the file chunk generator:
        # One to detect file encoding, and one to grab the field names.
        all_chunks, first_chunk = itertools.tee(self.file.chunks())
        self.first_chunk = next(first_chunk)
        self.chunks = all_chunks

        self.file_type = guess_format(self.file.name.lower())
        self.file_encoding = self._file_encoding()
        self.field_names = self._field_names()

    def _file_encoding(self):
        detector = UniversalDetector()

        for chunk in self.chunks:
            for line in chunk.splitlines():
                detector.feed(line)
                if detector.done:
                    break

        detector.close()
        encoding = detector.result['encoding']

        return encoding

    def _field_names(self):
        decoded_chunk = self.first_chunk.decode(self.file_encoding).splitlines()

        reader = csv.reader(decoded_chunk)
        fields = next(reader)

        return [self._clean_field(field) for field in fields]

    @classmethod
    def _clean_field(cls, field):
        return '_'.join(field.strip().lower().split(' '))

    def trim_extra_fields(self):
        '''
        From standardized upload, grab REQUIRED_FIELDS and write them
        to a UTF-8 temp file for copying to the database.
        '''
        if isinstance(self.file, FieldFile):
            infile = self.file.open(mode='r')
            lines = infile.read().decode(self.file_encoding).splitlines()
            reader = csv.DictReader(lines)

            # Downcase and underscore field names, so they will match with
            # REQUIRED_FIELDS.
            reader.fieldnames = self.field_names

            # Discard header.
            next(reader)

            outfile_name = '/tmp/{}'.format(basename(self.file.name))

            with open(outfile_name, 'w', encoding='utf-8') as outfile:
                writer = csv.DictWriter(outfile, fieldnames=self.REQUIRED_FIELDS)
                writer.writeheader()

                for row in reader:
                    out_row = {field: row[field] for field in self.REQUIRED_FIELDS}
                    writer.writerow(out_row)

            infile.close()

            return outfile_name

        else:
            message = 'Cannot alter instance of {}'.format(type(self.file))
            raise OperationNotPermittedOnInstance(message)
