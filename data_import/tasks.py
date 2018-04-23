from __future__ import absolute_import, unicode_literals

from celery import shared_task
from django.db import connection

from data_import.models import StandardizedFile
from data_import.utils import CsvMeta, ImportUtility


def create_raw_table(table_name):
    columns = '''
        record_id UUID DEFAULT gen_random_uuid(),
        responding_agency VARCHAR,
        employer VARCHAR,
        last_name VARCHAR,
        first_name VARCHAR,
        title VARCHAR,
        department VARCHAR,
        salary VARCHAR,
        date_started VARCHAR,
        data_year INT
    '''

    create = 'CREATE TABLE {} ({})'.format(table_name, columns)

    with connection.cursor() as cursor:
        cursor.execute(create)


@shared_task
def copy_to_database(*, s_file_id):
    s_file = StandardizedFile.objects.get(id=s_file_id)

    table_name = s_file.raw_table_name
    create_raw_table(table_name)

    meta = CsvMeta(s_file.standardized_file)

    formatted_data_file = meta.trim_extra_fields()

    with open(formatted_data_file, 'r', encoding='utf-8') as f:
        with connection.cursor() as cursor:
            copy_fmt = 'COPY "{table}" ({cols}) FROM STDIN CSV HEADER'

            copy = copy_fmt.format(table=table_name,
                                   cols=','.join(meta.REQUIRED_FIELDS))

            cursor.copy_expert(copy, f)

            cursor.execute('CREATE INDEX ON {} (employer)'.format(table_name))
            cursor.execute('CREATE INDEX ON {} (department)'.format(table_name))

    insert_responding_agency(s_file_id=s_file_id)

    return 'Dumped {} to database'.format(formatted_data_file, table_name)


@shared_task
def insert_responding_agency(*, s_file_id):
    imp = ImportUtility(s_file_id)
    imp.select_unseen_responding_agencies()

    return 'Inserted responding agencies'


@shared_task
def insert_employer(*, s_file_id):
    imp = ImportUtility(s_file_id)
    imp.insert_employer()

    return 'Inserted employers'


@shared_task
def insert_salary(*, s_file_id):
    imp = ImportUtility(s_file_id)
    imp.insert_salary()

    return 'Inserted salaries'
