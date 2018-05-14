from django.core.files.uploadedfile import UploadedFile
import pytest

from data_import.exceptions import OperationNotPermittedOnInstance
from data_import import utils


def test_alter_uploadedfile_raises_exception(mocker):
    mock_uploadedfile = mocker.MagicMock(spec=UploadedFile)

    # Return a generator from file.chunks() so init doesn't fail.
    mock_uploadedfile.chunks.return_value = iter(['foo'])

    # Patch _field_names setter to avoid StopIteration as result of
    # passing in mock (e.g., empty) file
    mocker.patch.object(utils.CsvMeta, '_field_names')
    mocker.patch.object(utils.CsvMeta, '_file_encoding')

    meta = utils.CsvMeta(mock_uploadedfile)

    with pytest.raises(OperationNotPermittedOnInstance) as err:
        meta.trim_extra_fields()

    assert 'Cannot alter instance' in str(err)
