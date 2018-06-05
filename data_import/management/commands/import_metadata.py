import json
from functools import partialmethod

from census import Census
from django.core.management.base import BaseCommand
import sqlalchemy as sa
from us import states

from bga_database.local_settings import CENSUS_API_KEY, DATABASES
from data.processors.get_taxonomy import PayrollDatabaseScraper


DB_CONN = 'postgresql://{USER}:{PASSWORD}@{HOST}:{PORT}/{NAME}'

# TO-DO: Figure out how to use the test database, when appropriate (i.e.,
# during testing)

engine = sa.create_engine(DB_CONN.format(**DATABASES['default']),
                          convert_unicode=True,
                          server_side_cursors=True)

class Command(BaseCommand):
    help = 'load in employer metadata from the census api and old bga database'

    base_dir = 'data/output/'
    taxonomy_file = base_dir + '2018-05-30-employer_taxonomy.csv'
    place_population_file = base_dir + 'illinois_place_population.json'
    county_population_file = base_dir + 'illinois_county_population.json'
    total_population_table = 'B01003_001E'
    data_year = 2016

    def add_arguments(self, parser):
        parser.add_argument('--endpoints',
                            help='a specific endpoint to load data from',
                            default='population,taxonomy')

        parser.add_argument('--import_only',
                            action='store_true',
                            default=None,
                            help='only load metadata')

        parser.add_argument('--download_only',
                            action='store_true',
                            default=None,
                            help='only download metadata')

    def handle(self, *args, **options):
        self.connection = engine.connect()

        self.endpoints = options['endpoints'].split(',')

        self.download_only = options['download_only']
        self.import_only = options['import_only']

        for endpoint in self.endpoints:
            getattr(self, '{}_etl'.format(endpoint))()

    def executeTransaction(self, query, *args, **kwargs):
        with self.connection.begin() as trans:
            try:
                if kwargs:
                    self.connection.execute(query, **kwargs)
                else:
                    self.connection.execute(query, *args)
            except:
                client.captureException()
                raise

    #######
    # ETL #
    #######

    def etl(self, endpoint, *args):
        if not self.import_only:
            getattr(self, 'grab_{}'.format(endpoint))()

        if not self.download_only:
            getattr(self, 'insert_{}'.format(endpoint))()

    population_etl = partialmethod(etl, 'population')
    taxonomy_etl = partialmethod(etl, 'taxonomy')

    ############
    # DOWNLOAD #
    ############

    def grab_population(self):
        print('downloading population')

        c = Census(CENSUS_API_KEY, year=self.data_year)

        for geography in ('place', 'county'):

            geo = {
                'for': '{}:*'.format(geography),
                'in': 'state:{}'.format(states.IL.fips),
            }

            pop = c.acs5.get(('NAME', self.total_population_table), geo)

            outfile = getattr(self, '{}_population_file'.format(geography))

            with open(outfile, 'w') as f:
                f.write(json.dumps(pop))

        print('population downloaded')

    def grab_taxonomy(self):
        print('downloading taxonomy')

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

        for geography in ('place', 'county'):

            infile = getattr(self, '{}_population_file'.format(geography))

            with open(infile, 'r') as f:
                pop = json.load(f)

            for place in pop:
                if geography == 'place':
                    # parse name like Valley City village, Illinois
                    classfied_name, _ = place['NAME'].split(',')
                    name_parts = classfied_name.split(' ')
                    name, classification = ' '.join(name_parts[:-1]), name_parts[-1]

                elif geography == 'county':
                    # parse name like Adams County, Illinois
                    name, _ = place['NAME'].split(',')

                    # For some reason, this comes back from the Census API
                    # with a space. It doesn't have a space: https://www.dewittcountyill.com/
                    if name == 'De Witt':
                        name = 'DeWitt'

                    classification = 'county'

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
