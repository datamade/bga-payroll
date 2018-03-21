import json

from django.urls import reverse
import pytest

from data_import.models import SourceFile, RespondingAgency, Upload


@pytest.mark.django_db
def test_source_file_upload(source_file_upload_blob, client):
    data = {'source_files': json.dumps(source_file_upload_blob)}

    rv = client.post(reverse('upload-source-file'), data=data)
    assert rv.status_code == 200

    # TO-DO: Test for more specific info.

    assert Upload.objects.all().count() == 1
    assert RespondingAgency.objects.all().count() == 2
    assert SourceFile.objects.all().count() == 2
