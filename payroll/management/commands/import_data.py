import sys

from django.core.files import File
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import Count

import sqlalchemy as sa
from sqlalchemy.engine.url import URL

from data_import.models import Upload, StandardizedFile
from data_import.tasks import copy_to_database
from data_import.utils import ImportUtility, CsvMeta

from payroll.models import Unit, Job, Department, Person


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

        self.reporting_year = options['reporting_year']
        self.amend = options.get('amend', False)

        self.data_file = self.validate(options['data_file'])

        django_conn = connection.get_connection_params()

        conn_kwargs = {
            'username': django_conn.get('user', ''),
            'password': django_conn.get('password', ''),
            'host': django_conn.get('host', ''),
            'port': django_conn.get('port', ''),
            'database': django_conn.get('database', ''),
        }

        self.engine = sa.create_engine(URL('postgresql', **conn_kwargs))

        self.upload()

    def prompt(self, prompt):
        confirm = input('{} [y/n] '.format(prompt))
        if confirm.lower() != 'y':
            sys.exit()

    def validate(self, data_file):
        with open(data_file, 'rb') as df:
            meta = CsvMeta(File(df))

            if meta.file_type != 'csv':
                raise CommandError('Data file must be a CSV')

            missing_fields = ', '.join(set(CsvMeta.REQUIRED_FIELDS) - set(meta.field_names))

            if missing_fields:
                message = 'Standardized file missing fields: {}'.format(missing_fields)
                raise CommandError(message)

            valid_file_name = meta.trim_extra_fields()

        self.stdout.write('Validated {}'.format(data_file))

        return valid_file_name

    def get_units(self, s_file):
        if not getattr(self, '_units', None):
            with self.engine.begin() as conn:
                select_distinct_units = '''
                    SELECT DISTINCT employer FROM {raw_table}
                '''.format(raw_table=s_file.raw_table_name)

                result = conn.execute(select_distinct_units)

                self._units = [r[0] for r in result]

        return self._units

    def pre_import(self, s_file):
        if self.amend:
            existing_units = []

            for unit_name in self.get_units(s_file):
                try:
                    unit = Unit.objects.get(name=unit_name)

                except Unit.DoesNotExist:
                    self.stdout.write('Could not find unit "{}"'.format(unit_name))
                    self.prompt('Do you wish to continue?')

                except Unit.MultipleObjectsExist:
                    self.stdout.write('Found more than one Unit named "{}"'.format(unit_name))
                    self.prompt('Do you know the unit slug?')
                    slug = input('Please provide the slug of the Unit you wish to amend: ')

                    try:
                        unit = Unit.objects.get(slug=slug)
                    except Unit.DoesNotExist:
                        self.stdout.write('Could not find Unit with slug "{}"'.format(slug))
                        sys.exit()
                    else:
                        existing_units.append(unit)

                else:
                    existing_units.append(unit)

            for unit in existing_units:
                salaries = unit.get_salaries(year=self.reporting_year)
                self.prompt('Found {0} salaries for unit {1}.\n{2}\nDo you wish to delete? '.format(salaries.count(), unit.name, salaries))
                summary = salaries.delete()
                self.stdout.write('Deletion summary: {}'.format(summary))

    def upload(self):
        upload = Upload.objects.create()

        with open(self.data_file, 'r') as data_file:
            s_file = StandardizedFile.objects.create(
                standardized_file=File(data_file),
                reporting_year=self.reporting_year,
                upload=upload
            )

        # Call task directly so it blocks until the file has been copied
        copy = copy_to_database.delay(s_file_id=s_file.id)
        copy.get()

        self.stdout.write('Copied standardized file {} to database'.format(s_file.id))
        self.stdout.write('Beginning import')

        with transaction.atomic():
            self.pre_import(s_file)

            import_util = ImportUtility(s_file.id)
            import_util.populate_models_from_raw_data()

            self.stdout.write('Populated models from standardized file {}'.format(s_file.id))

            self.post_import(s_file)

        self.stdout.write('Import complete')

    def post_import(self, s_file):
        if self.amend:
            jobs = Job.objects.filter(salaries__isnull=True)
            self.prompt('Found {0} jobs with no salaries.\n{1}\nDo you wish to delete? '.format(jobs.count(), jobs))
            summary = jobs.delete()
            self.stdout.write('Deletion summary: {}'.format(summary))

            departments = Department.objects.annotate(n_employees=Count('positions__jobs')).filter(n_employees=0)
            self.prompt('Found {0} departments with no jobs.\n{1}\nDo you wish to delete? '.format(departments.count(), departments))
            summary = departments.delete()
            self.stdout.write('Deletion summary: {}'.format(summary))

            people = Person.objects.annotate(n_jobs=Count('jobs')).filter(n_jobs=0)
            self.prompt('Found {0} people with no jobs.\n{1}\nDo you wish to delete? '.format(people.count(), people))
            summary = people.delete()
            self.stdout.write('Deletion summary: {}'.format(summary))

        call_command('sync_pgviews')

        self.stdout.write('Synced pg_views for standardized file {}'.format(s_file.id))

        call_command(
            'build_solr_index',
            reporting_year=self.reporting_year,
            recreate=True,
            chunksize=100
        )

        self.stdout.write('Updated index for standardized_file {}'.format(s_file.id))
