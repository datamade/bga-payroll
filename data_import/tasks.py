from __future__ import absolute_import, unicode_literals

from celery import shared_task
from django.db import connection

from data_import.utils import CsvMeta, ImportUtility


# TO-DO: Abstract some stuff (imports, i.e.) into a base class:
# https://blog.balthazar-rouberol.com/celery-best-practices
# https://celery.readthedocs.io/en/latest/userguide/tasks.html?highlight=context#task-inheritance

@shared_task
def copy_to_database(*, s_file_id):
    from data_import.models import StandardizedFile

    s_file = StandardizedFile.objects.get(id=s_file_id)

    table_name = s_file.raw_table_name

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

    s_file.status = 'copied'
    s_file.save()

    return 'Copied {} to database'.format(formatted_data_file)


@shared_task
def select_unseen_responding_agency(*, s_file_id):
    imp = ImportUtility(s_file_id)
    imp.select_unseen_responding_agency()

    return 'Selected responding agencies'


@shared_task
def insert_responding_agency(*, s_file_id):
    imp = ImportUtility(s_file_id)
    imp.insert_responding_agency()

    return 'Inserted responding agencies'


@shared_task
def select_unseen_employer(*, s_file_id):
    imp = ImportUtility(s_file_id)
    imp.select_unseen_employer()

    return 'Selected employers'


@shared_task
def insert_employer(*, s_file_id):
    imp = ImportUtility(s_file_id)
    imp.insert_employer()

    return 'Inserted employers'


@shared_task
def select_invalid_salary(*, s_file_id):
    imp = ImportUtility(s_file_id)

    imp.insert_position()

    imp.select_raw_person()
    imp.insert_person()

    imp.select_raw_job()
    imp.insert_job()

    # TO-DO: Select salary for review

    return 'Selected salaries'


@shared_task
def insert_salary(*, s_file_id):
    imp = ImportUtility(s_file_id)
    imp.insert_salary()

    return 'Inserted salaries'
