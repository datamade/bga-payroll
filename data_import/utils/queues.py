from django.db import connection
from django.db.utils import ProgrammingError


class Queue(object):
    '''
    Base class for review queues.
    '''
    def __init__(self, s_file_id):
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

    def flush(self):
        pass


class RespondingAgencyQueue(Queue):
    table_name_fmt = 'respondingagency_queue_{}'
    columns = '''
        name VARCHAR
    '''


class EmployerQueue(Queue):
    table_name_fmt = 'employer_queue_{}'
    columns = '''
        name VARCHAR,
        parent VARCHAR NULL
    '''


class SalaryQueue(Queue):
    table_name_fmt = 'salary_queue_{}'
    columns = '''
        record_id UUID,
        conflicting_record INT NULL
    '''
