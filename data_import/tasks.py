from __future__ import absolute_import, unicode_literals

from celery import shared_task
from django.db import connection

from data_import.models import StandardizedFile
from data_import.utils import CsvMeta


def create_raw_table(table_name):
    create = '''
        CREATE TABLE "{}" (
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
        )
    '''.format(table_name)

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

    return 'copied {} to table {}'.format(formatted_data_file, table_name)
