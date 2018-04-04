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
                        transactional_db,
                        raw_table_teardown):

    s_file = standardized_file.build(standardized_file=real_file)

    copy_to_database(s_file_id=s_file.id)

    imp = ImportUtility(s_file.id)

    with connection.cursor() as cursor:
        validate_employer = '''
            WITH parents AS (
              SELECT DISTINCT employer
              FROM {raw_payroll}
            ), children AS (
              SELECT DISTINCT ON (employer, department) *
              FROM {raw_payroll}
              WHERE department IS NOT NULL
            )
            SELECT
              (SELECT COUNT(*) FROM parents) + (SELECT COUNT(*) FROM children) AS raw_count,
              (SELECT COUNT(*) FROM payroll_employer) AS generated_count
        '''.format(raw_payroll=imp.raw_payroll_table)

        cursor.execute(validate_employer)

        result, = cursor
        raw_count, generated_count = result

        assert raw_count == generated_count

        # TO-DO: Spotcheck parent/child relationship

        validate_position = '''
            WITH distinct_positions AS (
              SELECT DISTINCT ON (employer, department, title) *
              FROM {raw_payroll}
            )
            SELECT
              (SELECT COUNT(*) FROM distinct_positions) AS raw_count,
              (SELECT COUNT(*) FROM payroll_position) AS generated_count
        '''.format(raw_payroll=imp.raw_payroll_table)

        cursor.execute(validate_position)

        result, = cursor
        raw_count, generated_count = result

        assert raw_count == generated_count

        # TO-DO: Spotcheck a couple of positions (null department, null title)

        validate_salary = '''
            SELECT
              (SELECT COUNT(*) FROM {raw_payroll}) AS raw_count,
              (SELECT COUNT(*) FROM {raw_salary}) AS generated_count
        '''.format(raw_payroll=imp.raw_payroll_table,
                   raw_salary=imp.raw_salary_table)

        cursor.execute(validate_salary)

        result, = cursor
        raw_count, generated_count = result

        assert raw_count == generated_count

        # TO-DO: Spotcheck a couple of linked person / salaries
