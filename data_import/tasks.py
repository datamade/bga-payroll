from __future__ import absolute_import, unicode_literals

from celery import shared_task, Task
from celery.signals import task_prerun
from django.db import connection

from data_import.utils import CsvMeta, ImportUtility


class DataImportTask(Task):
    def setup(self, s_file_id):
        '''
        Extending init breaks test discovery in Django. Instead,
        define a setup method that sets common attributes for tasks.
        '''
        from data_import.models import StandardizedFile

        self.s_file = StandardizedFile.objects.get(id=s_file_id)
        self.import_utility = ImportUtility(s_file_id)

    def update_status(self, status):
        self.s_file.status = status
        self.s_file.save()


@task_prerun.connect()
def task_prerun(sender=DataImportTask, *args, **kwargs):
    '''
    In lieu of an extended init on the custom Task object,
    hook into the task_prerun signal. This is fired before
    all tasks are run.
    '''
    s_file_id = kwargs['kwargs']['s_file_id']

    if s_file_id:
        sender.setup(s_file_id)


@shared_task(bind=True, base=DataImportTask)
def copy_to_database(self, *, s_file_id):
    '''
    Define a task method, and bind it to the base task.
    The setup method of the base task will be fired before
    the code in this task method, e.g, self.s_file and
    self.import_utility have been defined.
    '''
    table_name = self.s_file.raw_table_name

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

    meta = CsvMeta(self.s_file.standardized_file)
    formatted_data_file = meta.trim_extra_fields()

    with open(formatted_data_file, 'r', encoding='utf-8') as f:
        with connection.cursor() as cursor:
            copy_fmt = 'COPY "{table}" ({cols}) FROM STDIN CSV HEADER'

            copy = copy_fmt.format(table=table_name,
                                   cols=','.join(meta.REQUIRED_FIELDS))

            cursor.copy_expert(copy, f)

            cursor.execute('CREATE INDEX ON {} (employer)'.format(table_name))
            cursor.execute('CREATE INDEX ON {} (department)'.format(table_name))

    self.update_status('copied to database')

    return 'Copied {} to database'.format(formatted_data_file)


@shared_task(bind=True, base=DataImportTask)
def select_unseen_responding_agency(self, s_file_id):
    self.setup(s_file_id)

    self.import_utility.select_unseen_responding_agency()

    self.update_status('responding agency unmatched')

    return 'Selected responding agencies'


@shared_task(bind=True, base=DataImportTask)
def insert_responding_agency(self, s_file_id):
    self.setup(s_file_id)

    self.import_utility.insert_responding_agency()

    return 'Inserted responding agencies'


@shared_task(bind=True, base=DataImportTask)
def select_unseen_employer(self, s_file_id):
    self.setup(s_file_id)

    self.import_utility.select_unseen_employer()

    self.update_status('employer unmatched')

    return 'Selected employers'


@shared_task(bind=True, base=DataImportTask)
def insert_employer(self, s_file_id):
    self.setup(s_file_id)

    self.import_utility.insert_employer()

    return 'Inserted employers'


@shared_task(bind=True, base=DataImportTask)
def select_invalid_salary(self, s_file_id):
    self.setup(s_file_id)

    self.import_utility.insert_position()

    self.import_utility.select_raw_person()
    self.import_utility.insert_person()

    self.import_utility.select_raw_job()
    self.import_utility.insert_job()

    self.update_status('salary unvalidated')

    # TO-DO: Select salary for review

    return 'Selected salaries'


@shared_task(bind=True, base=DataImportTask)
def insert_salary(self, s_file_id):
    self.setup(s_file_id)

    self.import_utility.insert_salary()

    self.update_status('complete')

    return 'Inserted salaries'
