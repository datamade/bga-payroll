import datetime
import json

from django.urls import reverse
import pytest

from data_import.models import SourceFile, RespondingAgency, Upload
from data_import.utils import CsvMeta


@pytest.mark.django_db
@pytest.mark.source_file
def test_valid_source_file_upload(source_file_upload_blob, client):
    data = {'source_files': json.dumps(source_file_upload_blob)}

    rv = client.post(reverse('upload-source-file'), data=data)
    assert rv.status_code == 200

    assert Upload.objects.all().count() == 1

    responding_agencies = RespondingAgency.objects.all()

    assert responding_agencies.count() == 2

    incoming_agencies = [file['responding_agency'] for file in source_file_upload_blob]
    created_agencies = [agency.name for agency in responding_agencies]

    assert set(incoming_agencies) == set(created_agencies)

    source_files = SourceFile.objects.all()

    assert source_files.count() == 2
    assert all([f.google_drive_file_id for f in source_files])


@pytest.mark.django_db
@pytest.mark.standardized_data
def test_missing_fields_raises_exception(standardized_data_upload_blob,
                                         mocker,
                                         client):

    bad_fields = ['not', 'the', 'right', 'fields']
    mock_get_fields = mocker.patch.object(CsvMeta, 'field_names')
    mock_get_fields.return_value = bad_fields

    mock_file = standardized_data_upload_blob['standardized_file']

    rv = client.post(reverse('upload'),
                     data=standardized_data_upload_blob,
                     files={'standardized_file': mock_file})

    assert rv.status_code != 302
    assert 'Standardized file missing fields:' in rv.content.decode('utf-8')


@pytest.mark.django_db
@pytest.mark.standardized_data
def test_non_csv_raises_exception(standardized_data_upload_blob,
                                  client):

    mock_file = standardized_data_upload_blob['standardized_file']
    mock_file.name = 'not_a_csv.xlsx'

    standardized_data_upload_blob['standardized_file'] = mock_file

    rv = client.post(reverse('upload'),
                     data=standardized_data_upload_blob,
                     files={'standardized_file': mock_file})

    assert rv.status_code != 302
    assert 'Please upload a CSV' in rv.content.decode('utf-8')


@pytest.mark.django_db
@pytest.mark.standardized_data
def test_future_date_raises_exception(standardized_data_upload_blob,
                                      client):

    ten_years_from_now = datetime.datetime.today().year + 10
    standardized_data_upload_blob['reporting_year'] = ten_years_from_now

    mock_file = standardized_data_upload_blob['standardized_file']

    rv = client.post(reverse('upload'),
                     data=standardized_data_upload_blob,
                     files={'standardized_file': mock_file})

    assert rv.status_code != 302
    assert 'Reporting year cannot exceed the current year' in rv.content.decode('utf-8')


@pytest.mark.django_db
@pytest.mark.standardized_data
def test_valid_standardized_data_upload(standardized_data_upload_blob,
                                        real_file,
                                        client,
                                        mocker):

    # Mock our delayed task (which we'll test over in test_tasks)
    mock_copy = mocker.patch('data_import.views.copy_to_database.delay')

    standardized_data_upload_blob['standardized_file'] = real_file

    rv = client.post(reverse('upload'),
                     data=standardized_data_upload_blob,
                     files={'standardized_file': real_file})

    # Assert the page redirects, e.g., upload was successful
    assert rv.status_code == 302

    assert mock_copy.call_count == 1
