from django.core.files import File
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import connection

from data_import.models import Upload, StandardizedFile
from data_import.tasks import copy_to_database
from data_import.utils import ImportUtility


class Command(BaseCommand):
    help = 'Load specified data file'

    def add_arguments(self, parser):
        parser.add_argument('--data_file',
                            help='Path to data file')
        parser.add_argument('--reporting_year',
                            help='Year to which data pertains')
        parser.add_argument('--amend',
                            help='Specify flag if incoming data should replace '
                                 'existing data for the given responding agency '
                                 'and reporting year',
                            action='store_true')

    def handle(self, *args, **options):
        try:
            assert all([options.get('data_file'), options.get('reporting_year')])
        except AssertionError:
            raise ValueError('Please provide a data file and reporting year')

        self.data_file = options['data_file']
        self.reporting_year = options['reporting_year']
        self.amend = options.get('amend', False)

        self.upload()

    def upload(self):
        upload = Upload.objects.create()

        with open(self.data_file, 'r') as data_file:
            s_file = StandardizedFile.objects.create(
                standardized_file=File(data_file),
                reporting_year=self.reporting_year,
                upload=upload,
            )

        # Call task directly so it blocks until the file has been copied
        copy = copy_to_database.delay(s_file_id=s_file.id)
        copy.get()

        self.stdout.write('Copied standardized file {} to database'.format(s_file.id))

        import_util = ImportUtility(s_file.id)
        import_util.populate_models_from_raw_data()

        self.stdout.write('Populated models from standardized file {}'.format(s_file.id))

        call_command('sync_pgviews')
        call_command('build_solr_index', reporting_year=self.reporting_year, recreate=True)

