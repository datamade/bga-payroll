from django.core.files.uploadedfile import UploadedFile
import pytest

from data_import.exceptions import OperationNotPermittedOnInstance
from data_import.utils import CsvMeta


def test_alter_uploadedfile_raises_exception(mocker):
    mock_uploadedfile = mocker.MagicMock(spec=UploadedFile)

    # Patch _field_names setter to avoid StopIteration as result of
    # passing in mock (e.g., empty) file

    mocker.patch.object(CsvMeta, '_field_names')

    meta = CsvMeta(mock_uploadedfile)

    with pytest.raises(OperationNotPermittedOnInstance) as err:
        meta.trim_extra_fields()

    assert 'Cannot alter instance' in str(err)
