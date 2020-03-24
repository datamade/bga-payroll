import csv
import os
import shutil

from django.core.files import File
from django.db import connection
import pytest

from data_import.tasks import copy_to_database


@pytest.fixture
def real_files(request, project_directory):
    s_file_2017 = File(open(os.path.join(project_directory, 'tests/data_import/fixtures/standardized_data_sample.2017.csv')))
    s_file_2018 = File(open(os.path.join(project_directory, 'tests/data_import/fixtures/standardized_data_sample.2018.csv')))

    @request.addfinalizer
    def close():
        s_file_2017.close()
        s_file_2018.close()

        for upload_directory in ('2017', '2018'):
            try:
                # When this fixture is used to test a valid upload, the
                # file is saved to disk at 2018/payroll/standardized/...
                # Clean up that file tree.
                shutil.rmtree(upload_directory)

            except FileNotFoundError:
                pass

    return s_file_2017, s_file_2018


@pytest.fixture
def canned_data():
    '''
    Yield the first row of the canned data fixture, so we have access to
    values we know will match.
    '''
    with open('tests/data_import/fixtures/standardized_data_sample.2018.csv', 'r') as data:
        reader = csv.DictReader(data)
        yield next(reader)


@pytest.fixture
def standardized_data_upload_blob(mock_file):
    blob = {
        'standardized_file': mock_file,
        'reporting_year': 2018,
    }

    return blob


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def raw_table_setup(transactional_db,
                    standardized_file,
                    real_files,
                    celery_worker,
                    request):

    file_2017, file_2018 = real_files

    s_file_2017 = standardized_file.build(standardized_file=file_2017, reporting_year=2017)
    s_file_2018 = standardized_file.build(standardized_file=file_2018, reporting_year=2018)

    # Call copy_to_database directly, rather than using the transition
    # method on the StandardizedFile object, so we can have test execution
    # wait until the delayed work is finished via work.get()
    copy_2017 = copy_to_database.delay(s_file_id=s_file_2017.id)
    copy_2017.get()

    copy_2018 = copy_to_database.delay(s_file_id=s_file_2018.id)
    copy_2018.get()

    @request.addfinalizer
    def raw_table_teardown():
        '''
        Transactional tests don't clean up data from outside the ORM.
        Raw tables are named with the associated StandardizedFile ID,
        but are not formal models, and thus need to be torn down
        manually.
        '''
        drop = '''
            SELECT 'DROP TABLE ' || tablename || ';'
            FROM pg_tables
            WHERE tablename LIKE 'raw_payroll_%'
        '''

        with connection.cursor() as cursor:
            cursor.execute(drop)

    return s_file_2017, s_file_2018


@pytest.fixture
def queue_teardown(request):
    '''
    Queues are persistent between tests. Flush them after use, so we start
    from a clean state each time.
    '''
    @request.addfinalizer
    def flush_queue():
        from redis import Redis
        from django.conf import settings

        queue = Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT)
        queue.flushdb()
