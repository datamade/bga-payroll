from django.core.files.uploadedfile import UploadedFile
import pytest

from data_import.exceptions import OperationNotPermittedOnInstance
from data_import.tasks import copy_to_database
from data_import.utils import CsvMeta, ImportUtility


def test_alter_uploadedfile_raises_exception(mocker):
    mock_uploadedfile = mocker.MagicMock(spec=UploadedFile)

    # Patch _field_names setter to avoid StopIteration as result of
    # passing in mock (e.g., empty) file

    mocker.patch.object(CsvMeta, '_field_names')

    meta = CsvMeta(mock_uploadedfile)

    with pytest.raises(OperationNotPermittedOnInstance) as err:
        meta.trim_extra_fields()

    assert 'Cannot alter instance' in str(err)


@pytest.mark.dev
@pytest.mark.django_db(transaction=True)
def test_import_utility(standardized_file,
                        real_file,
                        transactional_db):

    s_file = standardized_file.build(standardized_file=real_file)

    copy_to_database(s_file_id=s_file.id)

    imp = ImportUtility(s_file.id)
    imp.import_new()

    # test some stuff
