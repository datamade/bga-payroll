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
            file = os.path.join(pwd, 'raw', '2017_payroll.csv')

            print('Inserting 2017 data')
            # id,Employer,Last Name,First Name,Title,Department,Salary,Date Started,Data Year
            with open(file, 'r', encoding='WINDOWS-1250') as f:
                cursor = connection.cursor()
                cursor.copy_expert('COPY raw_payroll FROM STDIN CSV HEADER', f)

            print('Indexing raw data')
            self._make_indexes()

#        print('Extracting governmental units')
#        self._insert_gov_unit()
#
#        print('Extracting departments')
#        self._insert_department()
#
#        print('Extracting people')
#        self._insert_person()
#
#        print('Extracting positions')
#        self._insert_position()
#
#        print('Extracting salaries')
#        self._insert_salary()

        print('Extracting tenures')
        self._insert_tenure()


    def _run(self, query):
        with connection.cursor() as cursor:
            cursor.execute(query)

    def _create_raw_table(self):
        drop = 'DROP TABLE IF EXISTS raw_payroll'

        create = '''
            CREATE TABLE raw_payroll (
                id VARCHAR,
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
            SELECT DISTINCT trim(employer) FROM raw_payroll
        '''

        self._run(select)

    def _insert_department(self):
        select = '''
            INSERT INTO payroll_department (governmental_unit_id, name)
            SELECT DISTINCT ON (employer, department)
                gunit.id,
                trim(department)
            FROM raw_payroll AS raw
            JOIN payroll_governmentalunit AS gunit
            ON raw.employer = gunit.name
            WHERE department IS NOT NULL
        '''

        self._run(select)

    def _insert_person(self):
        truncate = 'TRUNCATE payroll_person CASCADE'

        self._run(truncate)

        select = '''
            INSERT INTO payroll_person (first_name, last_name)
            SELECT DISTINCT ON (
                employer,
                department,
                first_name,
                last_name,
                title,
                salary
            )
                trim(first_name),
                trim(last_name)
            FROM raw_payroll
        '''

        self._run(select)

    def _insert_position(self):
        self._run(truncate)

        select = '''
            INSERT INTO payroll_position (department_id, title)
            SELECT DISTINCT ON (
                employer,
                department,
                title
            )
                dept.id,
                trim(title)
            FROM raw_payroll AS raw
            JOIN payroll_department AS dept
            ON raw.department = dept.name
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
        select = '''
            INSERT INTO payroll_tenure (
                person_id,
                position_id,
                salary_id,
                start_date
            )

            SELECT
                person.id AS person_id,
                position_id,
                sal.id AS salary_id,
                NULLIF(trim(start_date), '')::DATE
            FROM raw_payroll AS raw

            JOIN (
            SELECT
                gunit.name AS employer,
                dept.name AS department,
                pos.id AS position_id,
                pos.title AS title
            FROM payroll_governmentalunit AS gunit

            JOIN payroll_department AS dept
              ON dept.governmental_unit_id = gunit.id

            JOIN payroll_position AS pos
              ON pos.department_id = dept.id
            ) AS jobs
            ON trim(raw.employer) = jobs.employer
            AND trim(raw.department) = jobs.department
            AND trim(raw.title) = jobs.title

            JOIN payroll_salary AS sal
              ON REGEXP_REPLACE(raw.salary, '[^0-9,.]', '', 'g')::NUMERIC = sal.amount

            JOIN payroll_person AS person
              ON trim(raw.first_name) = person.first_name
             AND trim(raw.last_name) = person.last_name
        '''

        self._run(select)
