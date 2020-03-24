import datetime

from django.urls import reverse
import pytest

from data_import.utils import CsvMeta


@pytest.mark.django_db
@pytest.mark.source_file
def test_valid_source_file_upload():
    '''
    TO-DO: Write a test to post to the new admin upload.
    '''
    pass


@pytest.mark.django_db
@pytest.mark.standardized_data
def test_missing_fields_raises_exception(standardized_data_upload_blob,
                                         mocker,
                                         admin_client):

    bad_fields = ['not', 'the', 'right', 'fields']
    mock_get_fields = mocker.patch.object(CsvMeta, '_field_names')
    mock_get_fields.return_value = bad_fields

    mock_file = standardized_data_upload_blob['standardized_file']

    rv = admin_client.post(reverse('upload-standardized-file'),
                           data=standardized_data_upload_blob,
                           files={'standardized_file': mock_file})

    assert rv.status_code != 302
    assert 'Standardized file missing fields:' in rv.content.decode('utf-8')


@pytest.mark.django_db
@pytest.mark.standardized_data
def test_non_csv_raises_exception(standardized_data_upload_blob,
                                  admin_client):

    mock_file = standardized_data_upload_blob['standardized_file']
    mock_file.name = 'not_a_csv.xlsx'

    standardized_data_upload_blob['standardized_file'] = mock_file

    rv = admin_client.post(reverse('upload-standardized-file'),
                           data=standardized_data_upload_blob,
                           files={'standardized_file': mock_file})

    assert rv.status_code != 302
    assert 'Please upload a CSV' in rv.content.decode('utf-8')


@pytest.mark.django_db
@pytest.mark.standardized_data
def test_future_date_raises_exception(standardized_data_upload_blob,
                                      admin_client):

    ten_years_from_now = datetime.datetime.today().year + 10
    standardized_data_upload_blob['reporting_year'] = ten_years_from_now

    mock_file = standardized_data_upload_blob['standardized_file']

    rv = admin_client.post(reverse('upload-standardized-file'),
                           data=standardized_data_upload_blob,
                           files={'standardized_file': mock_file})

    assert rv.status_code != 302
    assert 'Reporting year cannot exceed the current year' in rv.content.decode('utf-8')


@pytest.mark.django_db
@pytest.mark.standardized_data
def test_valid_standardized_data_upload(standardized_data_upload_blob,
                                        real_files,
                                        admin_client,
                                        mocker):

    # Mock our delayed tasks (which we'll test over in test_tasks)
    mock_copy = mocker.patch('data_import.views.StandardizedFile.copy_to_database')

    standardized_data_upload_blob['standardized_file'] = real_files[1]

    rv = admin_client.post(reverse('upload-standardized-file'),
                           data=standardized_data_upload_blob,
                           files={'standardized_file': real_files[1]})

    # Assert the page redirects, e.g., upload was successful
    assert rv.status_code == 302

    assert mock_copy.call_count == 1
