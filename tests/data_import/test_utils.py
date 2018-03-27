from django.core.files.uploadedfile import UploadedFile
import pytest

from data_import.exceptions import OperationNotPermittedOnInstance
from data_import.utils import CsvMeta


def test_alter_uploadedfile_raises_exception(mocker):
    mock_uploadedfile = mocker.MagicMock(spec=UploadedFile)

    meta = CsvMeta(mock_uploadedfile)

    with pytest.raises(OperationNotPermittedOnInstance) as err:
        meta.trim_extra_fields()

    assert 'Cannot alter instance' in str(err)
