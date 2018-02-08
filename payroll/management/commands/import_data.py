import csv
import os

from django.core.management.base import BaseCommand, CommandError
from django.db import connection


class Command(BaseCommand):
    help = 'Import some data to get this show on the road'

    def handle(self, *args, **kwargs):
        self._create_raw_table()

        pwd = os.path.dirname(__file__)
        file = os.path.join(pwd, 'raw', '2017_payroll.csv')

        # id,Employer,Last Name,First Name,Title,Department,Salary,Date Started,Data Year
        with open(file, 'r', encoding='WINDOWS-1250') as f:
            cursor = connection.cursor()
            cursor.copy_expert('COPY raw_payroll FROM STDIN CSV HEADER', f)

        self._insert_gov_unit()
        self._insert_department()

    def _run(self, query):
        with connection.cursor() as cursor:
            cursor.execute(query)

    def _create_raw_table(self):
        create = '''
            CREATE TABLE IF NOT EXISTS raw_payroll (
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

        self._run(create)

    def _insert_gov_unit(self):
        truncate = 'TRUNCATE payroll_governmentalunit CASCADE'

        self._run(truncate)

        select = '''
            INSERT INTO payroll_governmentalunit (name)
            SELECT DISTINCT employer FROM raw_payroll
        '''

        self._run(select)

    def _insert_department(self):
        select = '''
            INSERT INTO payroll_department (governmental_unit_id, name)
            SELECT DISTINCT ON (employer, department)
                gunit.id,
                department
            FROM raw_payroll AS raw
            JOIN payroll_governmentalunit AS gunit
            ON raw.employer = gunit.name
            WHERE department IS NOT NULL
        '''

        self._run(select)
