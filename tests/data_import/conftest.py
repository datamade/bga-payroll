import datetime
from uuid import uuid4

from django.core.files import File
import pytest


@pytest.fixture
def mock_file(mocker):
    mock_file = mocker.MagicMock(spec=File)
    mock_file.name = 'mock_file.csv'

    return mock_file


@pytest.fixture
def standardized_file(request):
    s_file = open('tests/data_import/fixtures/standardized_data_sample.2016.csv')

    @request.addfinalizer
    def close():
        s_file.close()

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
        'reporting_year': 2017,
    }

    return blob
