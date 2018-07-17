from django.core.management.base import BaseCommand
from django.db.models import Sum, Q
import pysolr

from django.conf import settings

from data_import.models import StandardizedFile
from payroll.models import Employer, Person, Salary


class Command(BaseCommand):
    help = 'build a solr index'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.searcher = pysolr.Solr(settings.SOLR_URL)
        self.reporting_years = [x.reporting_year for x
                                in StandardizedFile.objects.distinct('reporting_year')]


    def add_arguments(self, parser):
        parser.add_argument(
            '--entity-types',
            dest='entity_types',
            help='Comma separated list of entity types to index',
            default='units,departments,positions,people'
        )
        parser.add_argument(
            '--recreate',
            action='store_true',
            dest='recreate',
            default=False,
            help='Delete all existing documents before creating the search index.'
        )
        parser.add_argument(
            '--s_file',
            dest='s_file_id',
            default=None,
            help='Specify a specific standardized file to index'
        )
        parser.add_argument(
            '--reporting_year',
            dest='reporting_year',
            default=None,
            help='Specify a specific reporting year to index'
        )


    def handle(self, *args, **options):
        if options['recreate']:
            self.stdout.write(self.style.SUCCESS('Dropping existing index'))
            self.searcher.delete(q='*:*')

        entities = options['entity_types'].split(',')

        for entity in entities:
            getattr(self, 'index_{}'.format(entity))()

    def index_units(self):
        self.stdout.write(self.style.SUCCESS('Indexing units'))

        documents = []

        units = Employer.objects.filter(parent_id__isnull=True)

        for unit in units:
            name = unit.name
            taxonomy = str(unit.taxonomy)

            of_unit = Q(job__position__employer=unit) | Q(job__position__employer__parent=unit)

            for year in self.reporting_years:
                in_year = Q(vintage__standardized_file__reporting_year=year)

                salaries = Salary.objects.filter(of_unit & in_year)
                expenditure = salaries.aggregate(expenditure=Sum('amount'))['expenditure']
                headcount = salaries.count()

                documents.append({
                    'id': 'unit.{0}.{1}'.format(unit.id, year),
                    'name': name,
                    'entity_type': 'Employer',
                    'year': year,
                    'taxonomy_s': taxonomy,
                    'size_class_s': unit.size_class,
                    'expenditure_d': expenditure,
                    'headcount_i': headcount,
                    'text': name,
                })

        self.searcher.add(documents)

        success_message = 'Added {0} documents for {1} units to the index'.format(len(documents),
                                                                                  units.count())

        self.stdout.write(self.style.SUCCESS(success_message))

    def index_departments(self):
        self.stdout.write(self.style.SUCCESS('Indexing departments'))

        documents = []

        departments = Employer.objects.filter(parent_id__isnull=False)

        for department in departments:
            name = department.name

            of_department = Q(job__position__employer=department)

            for year in self.reporting_years:
                in_year = Q(vintage__standardized_file__reporting_year=year)

                salaries = Salary.objects.filter(of_department & in_year)
                expenditure = salaries.aggregate(expenditure=Sum('amount'))['expenditure']
                headcount = salaries.count()

                document = {
                    'id': 'department.{0}.{1}'.format(department.id, year),
                    'name': name,
                    'entity_type': 'Employer',
                    'year': year,
                    'expenditure_d': expenditure,
                    'headcount_i': headcount,
                    'parent_s': department.parent.slug,
                    'text': name,
                }

                if department.universe:
                    document['universe_s'] = str(department.universe)

                documents.append(document)

        self.searcher.add(documents)

        success_message = 'Added {0} documents for {1} departments to the index'.format(len(documents),
                                                                                        departments.count())

        self.stdout.write(self.style.SUCCESS(success_message))
