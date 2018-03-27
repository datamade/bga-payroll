import csv
import datetime
import functools
from os.path import basename

from cchardet import UniversalDetector
from csvkit.convert import guess_format
from django.core.files.uploadedfile import UploadedFile


class CsvMeta(object):
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
        self.chunk = next(incoming_file.chunks())


    @property
    @functools.lru_cache()
    def file_type(self):
        file_type = guess_format(self.file.name.lower())

        return file_type


    @property
    @functools.lru_cache()
    def file_encoding(self):
        detector = UniversalDetector()

        for line in self.chunk.splitlines():
            detector.feed(line)
            if detector.done:
                break

        detector.close()
        encoding = detector.result['encoding']

        return encoding


    @property
    @functools.lru_cache()
    def field_names(self):
        try:
            reader = csv.reader(self.chunk.splitlines())
            fields = next(reader)

        except:  # Can't catch csv.Error, does not inherit from base class
            decoded_chunk = self.chunk.decode(self.file_encoding).splitlines()
            reader = csv.reader(decoded_chunk)
            fields = next(reader)

        return [self._clean_field(field) for field in fields]


    def _clean_field(self, field):
        return '_'.join(field.strip().lower().split(' '))


    def trim_extra_fields(self):
        infile = self.file.open(mode='r')
        lines = infile.read()\
                      .decode(self.file_encoding)\
                      .splitlines()

        reader = csv.DictReader(lines)
        reader.fieldnames = self.field_names
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
