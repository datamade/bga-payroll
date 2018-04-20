from django.db import connection
from django.db.utils import ProgrammingError

from data_import.utils.table_names import TableNamesMixin


class Queue(TableNamesMixin):
    '''
    Base class for review queues.
    '''
    def __init__(self, s_file_id):
        super().__init__(s_file_id)

        self.table_name = self.table_name_fmt.format(s_file_id)

    def initialize(self):
        create = '''
            CREATE TABLE {table_name} ({columns})
        '''.format(table_name=self.table_name,
                   columns=self.columns)

        try:
            with connection.cursor() as cursor:
                cursor.execute(create)

        except ProgrammingError:
            raise  # TO-DO: Custom exception?


class RespondingAgencyQueue(Queue):
    table_name_fmt = 'respondingagency_queue_{}'
    columns = '''
        name VARCHAR,
        match VARCHAR NULL,
        processed BOOLEAN DEFAULT FALSE
    '''

    def process(self, unseen, match):
        with connection.cursor() as cursor:
            update = '''
                UPDATE {0} SET
                  match = '{1}',
                  processed = TRUE
                WHERE name = '{2}'
            '''.format(self.table_name,
                       match,
                       unseen)

            cursor.execute(update)

    def flush(self):
        with connection.cursor() as cursor:
            update = '''
                UPDATE {raw_payroll} AS raw SET
                  responding_agency = match
                FROM {queue} AS q
                WHERE raw.responding_agency = q.name
            '''.format(raw_payroll=self.raw_payroll_table,
                       queue=self.table_name)

            cursor.execute(update)


class EmployerQueue(Queue):
    table_name_fmt = 'employer_queue_{}'
    columns = '''
        name VARCHAR,
        parent VARCHAR NULL,
        match VARCHAR NULL,
        processed BOOLEAN DEFAULT FALSE
    '''


class SalaryQueue(Queue):
    table_name_fmt = 'salary_queue_{}'
    columns = '''
        record_id UUID,
        conflicting_record INT NULL,
        match VARCHAR NULL,
        processed BOOLEAN DEFAULT FALSE
    '''
