import datetime
import shutil
from uuid import uuid4

from django.core.files import File
from django.db import connection
import pytest

from data_import.models import StandardizedFile
from data_import.tasks import copy_to_database


@pytest.fixture
def mock_file(mocker):
    mock_file = mocker.MagicMock(spec=File)
    mock_file.name = 'mock_file.csv'

    return mock_file


@pytest.fixture
def real_file(request):
    s_file = File(open('tests/data_import/fixtures/standardized_data_sample.2016.csv'))

    @request.addfinalizer
    def close():
        s_file.close()

        try:
            # When this fixture is used to test a valid upload, the
            # file is saved to disk at 2016/payroll/standardized/...
            # Clean up that file tree.
            shutil.rmtree('2016')

        except FileNotFoundError:
            pass

    return s_file


@pytest.fixture
def source_file_upload_blob(mock_file):
    '''
    Rollin' thru Gmail.
    '''
    start_date = datetime.date(2016, 1, 1).isoformat()
    end_date = datetime.date(2016, 12, 31).isoformat()

    blob = [{
        'responding_agency': 'Chicago',
        'response_date': datetime.date(2017, 2, 16).isoformat(),
        'reporting_period_start_date': start_date,
        'reporting_period_end_date': end_date,
        'google_drive_file_id': str(uuid4()),
    }, {
        'responding_agency': 'Champaign County',
        'response_date': datetime.date(2017, 2, 28).isoformat(),
        'reporting_period_start_date': start_date,
        'reporting_period_end_date': end_date,
        'google_drive_file_id': str(uuid4()),
    }]

    return blob


@pytest.fixture
def standardized_data_upload_blob(mock_file):
    blob = {
        'standardized_file': mock_file,
        'reporting_year': 2016,
    }

    return blob


@pytest.fixture
@pytest.mark.django_db
def standardized_file(mock_file, upload):
    class StandardizedFileFactory():
        def build(self, **kwargs):
            data = {
                'reporting_year': 2016,
                'standardized_file': mock_file,
                'upload': upload.build(),
            }
            data.update(kwargs)

            return StandardizedFile.objects.create(**data)

    return StandardizedFileFactory()


@pytest.fixture
def raw_table_teardown(request):
    @request.addfinalizer
    def drop_table():
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


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def review_setup(transactional_db,
                 standardized_file,
                 real_file,
                 celery_worker):

    s_file = standardized_file.build(standardized_file=real_file)

    work = copy_to_database.delay(s_file_id=s_file.id)
    work.get()

    return s_file
