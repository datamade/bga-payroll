import csv
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Import some data to get this show on the road'

    def add_arguments(self, parser):
        parser.add_argument('--skip_raw',
                            action='store_true',
                            help='Drop and recreate the table for the raw data')

    def handle(self, *args, **kwargs):
        if kwargs.get('skip_raw'):
            print('Skipping create raw table')

        else:
            print('Creating raw table')
            self._create_raw_table()

            pwd = os.path.dirname(__file__)
            file = os.path.join(pwd, '2017_payroll.sorted.csv')

            print('Inserting 2017 data')
            with open(file, 'r', encoding='WINDOWS-1250') as f:
                cursor = connection.cursor()

                copy = '''
                    COPY raw_payroll (
                        null_id,
                        employer,
                        last_name,
                        first_name,
                        title,
                        department,
                        salary,
                        start_date,
                        vintage
                    ) FROM STDIN CSV
                '''

                cursor.copy_expert(copy, f)

            print('Indexing raw data')
            self._make_indexes()

        print('Extracting governmental units')
        self._insert_gov_unit()

        print('Extracting departments')
        self._insert_department()

        print('Extracting people')
        self._insert_person()

        print('Extracting positions')
        self._insert_position()

        print('Extracting salaries')
        self._insert_salary()

        print('Extracting tenures')
        self._insert_tenure()

    def _run(self, query):
        with connection.cursor() as cursor:
            cursor.execute(query)

    def _create_raw_table(self):
        drop = 'DROP TABLE IF EXISTS raw_payroll'

        create = '''
            CREATE TABLE raw_payroll (
                id UUID DEFAULT uuid_generate_v4(),
                null_id VARCHAR,
                employer VARCHAR,
                last_name VARCHAR,
                first_name VARCHAR,
                title VARCHAR,
                department VARCHAR,
                salary VARCHAR,
                start_date VARCHAR,
                vintage INT
            )
        '''

        self._run(drop)
        self._run(create)

    def _make_indexes(self):
        for field in ('employer', 'department',
                      'first_name', 'last_name',
                      'title', 'salary'):

            index = 'CREATE INDEX ON raw_payroll ({})'.format(field)

            self._run(index)

    def _insert_gov_unit(self):
        truncate = 'TRUNCATE payroll_governmentalunit CASCADE'

        self._run(truncate)

        select = '''
            INSERT INTO payroll_governmentalunit (name)
            SELECT DISTINCT TRIM(employer) FROM raw_payroll
        '''

        self._run(select)

    def _insert_department(self):
        select = '''
            INSERT INTO payroll_department (governmental_unit_id, name)
            SELECT DISTINCT ON (employer, department)
                gunit.id,
                TRIM(department)
            FROM raw_payroll AS raw
            JOIN payroll_governmentalunit AS gunit
            ON TRIM(raw.employer) = gunit.name
        '''

        self._run(select)

    def _insert_person(self):
        truncate = 'TRUNCATE payroll_person CASCADE'

        self._run(truncate)

        select = '''
            INSERT INTO payroll_person (id, first_name, last_name)
            SELECT
                id,
                TRIM(first_name),
                TRIM(last_name)
            FROM raw_payroll
        '''

        self._run(select)

    def _insert_position(self):
        select = '''
            INSERT INTO payroll_position (department_id, title)
            SELECT DISTINCT ON (
                employer,
                department,
                title
            )
                dept.id,
                TRIM(title)
            FROM raw_payroll AS raw
            JOIN payroll_department AS dept
            ON TRIM(raw.department) = dept.name
        '''

        self._run(select)

    def _insert_salary(self):
        truncate = 'TRUNCATE payroll_salary CASCADE'

        self._run(truncate)

        select = '''
            INSERT INTO payroll_salary (amount, vintage)
            SELECT DISTINCT ON (salary)
                REGEXP_REPLACE(salary, '[^0-9,.]', '', 'g')::NUMERIC,
                vintage
            FROM raw_payroll
            WHERE salary IS NOT NULL
        '''

        self._run(select)

    def _insert_tenure(self):
        '''
        NOTE TO SELF: This doesn't account for tenures in positions
        where the title or department is null in the source data
        (about 33k records, in total). Find a way to get those, too.
        '''
        select = '''
            INSERT INTO payroll_tenure (
                person_id,
                position_id,
                salary_id,
                start_date
            )
            SELECT DISTINCT ON (raw.id)
                raw.id,
                position_id,
                sal.id,
                NULLIF(TRIM(raw.start_date), '')::date
            FROM raw_payroll AS raw

            JOIN (
                SELECT
                    dept.name AS department,
                    pos.title AS title,
                    pos.id AS position_id
                FROM payroll_department AS dept
                JOIN payroll_position AS pos
                  ON dept.id = pos.department_id
            ) AS jobs
            ON TRIM(raw.department) = jobs.department
            AND TRIM(raw.title) = jobs.title

            JOIN payroll_salary AS sal
              ON REGEXP_REPLACE(
                  raw.salary, '[^0-9,.]', '', 'g'
              )::NUMERIC = sal.amount
        '''

        self._run(select)
