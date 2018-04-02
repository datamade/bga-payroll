from django.core.files.uploadedfile import UploadedFile
from django.db import connection
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

    with connection.cursor() as cursor:
        cursor.execute('''
            SELECT
              (SELECT COUNT(*) FROM {raw_payroll}) AS raw_count,
              (SELECT COUNT(*) FROM {raw_salary}) AS generated_count
        '''.format(raw_payroll=imp.raw_payroll_table,
                   raw_salary=imp.raw_salary_table))

        result, = cursor
        raw_count, generated_count = result

        # Test we make a salary item for each record.

        assert raw_count == generated_count

    # test some other stuff
