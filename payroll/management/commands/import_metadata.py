from contextlib import redirect_stdout
from datetime import datetime
from functools import partialmethod
import json

from census import Census
from django.core.management.base import BaseCommand
from django.db import connection
import sqlalchemy as sa
from sqlalchemy.engine.url import URL
from us import states

from bga_database.local_settings import CENSUS_API_KEY
from bga_database.settings import BASE_DIR
from data.processors.get_taxonomy import PayrollDatabaseScraper


class Command(BaseCommand):
    help = 'load in employer metadata from the census api and old bga database'

    DATA_DIR = '/data/output'
    taxonomy_file_fmt = BASE_DIR + DATA_DIR + '/{date}-employer_taxonomy.csv'
    population_file_fmt = BASE_DIR + DATA_DIR + '/illinois_{geography}_population.json'

    total_population_table = 'B01003_001E'
    data_year = 2016

    def add_arguments(self, parser):
        parser.add_argument('--endpoints',
                            help='a specific endpoint to load data from',
                            default='population,taxonomy')

        parser.add_argument('--refresh',
                            action='store_true',
                            default=False,
                            help='re-download source data')

    def handle(self, *args, **options):
        django_conn = connection.get_connection_params()

        conn_kwargs = {
            'username': django_conn.get('user', ''),
            'password': django_conn.get('password', ''),
            'host': django_conn.get('host', ''),
            'port': django_conn.get('port', ''),
            'database': django_conn.get('database', ''),
        }

        self.engine = sa.create_engine(URL('postgresql', **conn_kwargs))

        self.endpoints = options['endpoints'].split(',')

        self.refresh = options['refresh']

        if not self.refresh:  # use the cached taxonomy file
            self.taxonomy_file = self.taxonomy_file_fmt.format(date='2018-05-30')

        for endpoint in self.endpoints:
            getattr(self, '{}_etl'.format(endpoint))()

    def executeTransaction(self, query, *args, **kwargs):
        with self.engine.begin() as conn:
            conn.execute(query, *args, **kwargs)

    #######
    # ETL #
    #######

    def etl(self, endpoint, *args):
        if self.refresh:
            getattr(self, 'grab_{}'.format(endpoint))()

        getattr(self, 'insert_{}'.format(endpoint))()

    population_etl = partialmethod(etl, 'population')
    taxonomy_etl = partialmethod(etl, 'taxonomy')

    ############
    # DOWNLOAD #
    ############

    def grab_population(self):
        print('downloading population')

        c = Census(CENSUS_API_KEY, year=self.data_year)

        for geography in ('place', 'county', 'county subdivision'):

            geo = {
                'for': '{}:*'.format(geography),
                'in': 'state:{}'.format(states.IL.fips),
            }

            pop = c.acs5.get(('NAME', self.total_population_table), geo)

            outfile = self.population_file_fmt.format(geography=geography.replace(' ', '_'))

            with open(outfile, 'w') as f:
                f.write(json.dumps(pop))

        print('population downloaded')

    def grab_taxonomy(self):
        print('downloading taxonomy')

        today = datetime.now().strftime('%Y-%m-%d')
        self.taxonomy_file = self.taxonomy_file_fmt.format(date=today)

        with open(self.taxonomy_file, 'w') as outfile:
            with redirect_stdout(outfile):
                pds = PayrollDatabaseScraper()
                pds.scrape()

        print('taxonomy downloaded')

    ##########
    # INSERT #
    ##########

    def remake_raw(self, entity_type, columns):
        self.executeTransaction('''
            DROP TABLE IF EXISTS raw_{}
        '''.format(entity_type))

        self.executeTransaction('''
            CREATE TABLE raw_{0} ({1})
        '''.format(entity_type, columns))

    def insert_population(self):
        print('inserting population')

        self.remake_raw('population', '''
            name VARCHAR,
            classification VARCHAR,
            geoid VARCHAR,
            population INT,
            data_year INT
        ''')

        inserts = []

        cook_or_collar = [
            'cook',
            'dupage',
            'kane',
            'lake',
            'mchenry',
            'will',
        ]

        for geography in ('place', 'county', 'county subdivision'):

            infile = self.population_file_fmt.format(geography=geography.replace(' ', '_'))

            with open(infile, 'r') as f:
                pop = json.load(f)

            for place in pop:
                if geography == 'place':
                    # Parse name like Valley City village, Illinois
                    classfied_name, *_ = place['NAME'].split(',')
                    name_parts = classfied_name.split(' ')
                    name, classification = ' '.join(name_parts[:-1]), name_parts[-1]

                elif geography == 'county':
                    # Parse name like Adams County, Illinois
                    name, _ = place['NAME'].split(',')

                    # For some reason, this comes back from the Census API
                    # with a space. It doesn't have a space: https://www.dewittcountyill.com/
                    if name.startswith('De Witt'):
                        name = name.replace('De Witt', 'DeWitt')

                    classification = 'county'

                elif geography == 'county subdivision':
                    # Parse name like York township, DuPage County, Illinois
                    classfied_name, county, _ = place['NAME'].split(',')
                    name_parts = classfied_name.split(' ')
                    name, classification = ' '.join(name_parts[:-1]), name_parts[-1]

                    if classification != 'township':
                        continue

                    parsed_county = ' '.join(county.split(' ')[:-1]).lower().strip()

                    # Data only includes townships in Cook and collar counties,
                    # so omit the others, to avoid name collisions (township
                    # name is not unique statewide).
                    if parsed_county not in cook_or_collar:
                        continue

                place_meta = {
                    'name': name,
                    'classification': classification,
                    'geoid': place[geography],
                    'population': int(place[self.total_population_table]),
                    'data_year': self.data_year,
                }

                inserts.append(place_meta)

        insert = '''
            INSERT INTO raw_population (
              name,
              classification,
              geoid,
              population,
              data_year
            ) VALUES (
              :name,
              :classification,
              :geoid,
              :population,
              :data_year
            )
        '''

        self.executeTransaction(sa.text(insert), *inserts)

        print('inserted population')

    def insert_taxonomy(self):
        print('inserting taxonomy')

        columns = '''
            entity VARCHAR,
            entity_type VARCHAR,
            chicago BOOLEAN,
            cook_or_collar BOOLEAN
        '''

        self.remake_raw('taxonomy', columns)

        with open(self.taxonomy_file, 'r', encoding='utf-8') as f:
            with connection.cursor() as cursor:
                copy_fmt = 'COPY "{table}" ({cols}) FROM STDIN CSV HEADER'

                copy = copy_fmt.format(table='raw_taxonomy',
                                       cols=columns.replace(' VARCHAR', '')
                                                   .replace(' BOOLEAN', ''))

                cursor.copy_expert(copy, f)

        print('inserted taxonomy')
