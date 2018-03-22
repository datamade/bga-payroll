import json

from django.urls import reverse
import pytest

from data_import.models import SourceFile, RespondingAgency, Upload


@pytest.mark.django_db
def test_source_file_upload(source_file_upload_blob, client):
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
