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
                cursor.copy_expert('COPY raw_payroll FROM STDIN CSV', f)

            print('Indexing raw data')
            self._make_indexes()

        print('Extracting employers')
        self._insert_employer()

        print('Extracting people')
        self._insert_person()

        print('Extracting positions')
        self._insert_position()

        print('Extracting salary')
        self._insert_salary()

    def _run(self, query):
        with connection.cursor() as cursor:
            cursor.execute(query)

    def _create_raw_table(self):
        drop = 'DROP TABLE IF EXISTS raw_payroll'

        create = '''
            CREATE TABLE raw_payroll (
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

    def _insert_employer(self):
        truncate = 'TRUNCATE payroll_employer CASCADE'

        self._run(truncate)

        select = '''
            INSERT INTO payroll_employer (name)
            SELECT DISTINCT employer FROM raw_payroll;


            INSERT INTO payroll_employer (parent_id, name)
            SELECT DISTINCT ON (id, department)
                emp.id,
                raw.department
            FROM raw_payroll AS raw
            JOIN payroll_employer AS emp
            ON raw.employer = emp.name
            WHERE raw.department IS NOT NULL;
        '''

        self._run(select)

    def _insert_person(self):
        '''
        NOTE: This creates multiples of people who have different titles
        within the same department. This seems preferable to deleting
        two John Smiths working in the same department. We could potentially
        lose a John Smith if two started in the same department on the same
        day with the same rate of pay.
        '''
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
                start_date
            )
                first_name,
                last_name
            FROM raw_payroll
        '''

        self._run(select)

    def _insert_position(self):
        truncate = 'TRUNCATE payroll_employer CASCADE'

        self._run(truncate)

        select = '''
            INSERT INTO payroll_position (employer_id, title)
            SELECT DISTINCT ON (
                employer,
                title
            )
                emp.id,
                COALESCE(title, 'EMPLOYEE')
            FROM raw_payroll AS raw
            JOIN payroll_employer AS emp
            ON raw.employer = emp.name
            WHERE raw.department IS NULL;


            INSERT INTO payroll_position (employer_id, title)
            WITH department AS (
                SELECT
                    child.id AS id,
                    parent.name AS parent,
                    child.name AS department
                FROM payroll_employer AS child
                JOIN payroll_employer AS parent
                ON child.parent_id = parent.id
            )
            SELECT DISTINCT ON (
                raw.employer,
                raw.department,
                title
            )
                dept.id,
                COALESCE(title, 'EMPLOYEE')
            FROM raw_payroll AS raw
            JOIN department AS dept
            ON raw.employer = dept.parent
            AND raw.department = dept.department
            WHERE raw.department IS NOT NULL;
        '''

        self._run(select)

    def _insert_salary(self):
        '''
        Take advantage of ordered inserts and automatic serials to create
        a temp table with a serial ID, fill it with data, insert some of
        that data into the salary table, then use the salary serial ID (which
        will equal the serial ID from the salary table) to insert the rest
        of the data into the person_salaries table.
        '''
        truncate = 'TRUNCATE payroll_salary CASCADE'

        self._run(truncate)

        transaction = '''
            ALTER SEQUENCE payroll_salary_id_seq RESTART WITH 1;


            CREATE TEMP TABLE ps_lookup (
                id SERIAL,
                person_id INT,
                position_id INT,
                amount DOUBLE PRECISION,
                start_date DATE,
                vintage INT
            );


            INSERT INTO ps_lookup (person_id, position_id, amount, start_date, vintage)
            WITH positions AS (
                SELECT
                    employer.id AS employer_id,
                    employer.name AS employer_name,
                    position.id AS position_id,
                    position.title AS position_name
                FROM payroll_employer AS employer
                JOIN payroll_position AS position
                ON position.employer_id = employer.id
            )
            SELECT DISTINCT ON (employer_id, person_id, position_id, salary, start_date)
                person.id AS person_id,
                position.position_id,
                REGEXP_REPLACE(salary, '[^0-9,.]', '', 'g')::NUMERIC,
                raw.start_date::date,
                '2017'::int AS vintage
            FROM raw_payroll AS raw

            JOIN positions AS position
            ON position.employer_name = raw.employer
            AND position.position_name = COALESCE(raw.title, 'EMPLOYEE')

            JOIN payroll_person AS person
            ON person.first_name = raw.first_name
            AND person.last_name = raw.last_name

            WHERE raw.department IS NULL;


            INSERT INTO ps_lookup (person_id, position_id, amount, start_date, vintage)
            WITH positions AS (
                SELECT
                    child_employer.id AS employer_id,
                    child_employer.name AS employer_name,
                    parent_employer.name AS parent_employer_name,
                    position.id AS position_id,
                    position.title AS position_name
                FROM payroll_employer AS child_employer
                JOIN payroll_employer AS parent_employer
                ON child_employer.parent_id = parent_employer.id
                JOIN payroll_position AS position
                ON position.employer_id = child_employer.id
            )
            SELECT DISTINCT ON (employer_id, person_id, position_id, salary, raw.start_date)
                person.id AS person_id,
                position.position_id,
                REGEXP_REPLACE(salary, '[^0-9,.]', '', 'g')::NUMERIC,
                NULLIF(TRIM(raw.start_date), '')::date,
                '2017'::int AS vintage
            FROM raw_payroll AS raw

            JOIN positions AS position
            ON position.parent_employer_name = raw.employer
            AND position.employer_name = raw.department
            AND position.position_name = COALESCE(raw.title, 'EMPLOYEE')

            JOIN payroll_person AS person
            ON person.first_name = raw.first_name
            AND person.last_name = raw.last_name

            WHERE raw.department IS NOT NULL;


            INSERT INTO payroll_salary (amount, start_date, vintage, position_id)
            SELECT
                amount,
                start_date,
                vintage,
                position_id
            FROM ps_lookup;


            INSERT INTO payroll_person_salaries (person_id, salary_id)
            SELECT
                person_id,
                id
            FROM ps_lookup;
        '''

        self._run(transaction)

