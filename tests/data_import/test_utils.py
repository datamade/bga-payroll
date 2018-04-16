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


@pytest.mark.django_db(transaction=True)
def test_import_utility(standardized_file,
                        real_file,
                        transactional_db,
                        raw_table_teardown):

    s_file = standardized_file.build(standardized_file=real_file)

    copy_to_database(s_file_id=s_file.id)

    imp = ImportUtility(s_file.id, s_file.upload.id)

    with connection.cursor() as cursor:
        # Do some validation on the individual model tables, so we have a
        # clue where things went wrong, when making changes to the queries.
        # (If we check that the generated data matches the source data first,
        # we'll know if it doesn't match, but we won't know where to start
        # looking for the culprit.)

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

        validate_job = '''
            SELECT
              (SELECT COUNT(*) FROM {raw_payroll}) AS raw_count,
              (SELECT COUNT(*) FROM {raw_job}) AS generated_count
        '''.format(raw_payroll=imp.raw_payroll_table,
                   raw_job=imp.raw_job_table)

        cursor.execute(validate_job)

        result, = cursor
        raw_count, generated_count = result

        assert raw_count == generated_count

        # Reconstruct the source data from the data model tables, and check
        # that it fully overlaps with the raw source (with salary and start
        # date transformed, for matching purposes). The following query will
        # return rows that occur in one select, but not the other, e.g., it
        # should return no rows for a full overlap.
        #
        # See https://stackoverflow.com/questions/5727882/check-if-two-selects-are-equivalent

        reconstruct = '''
            WITH reconstructed AS (
              SELECT
                CASE
                  WHEN emp.parent_id IS NULL THEN emp.name
                  ELSE parent.name
                END AS employer,
                CASE
                  WHEN emp.parent_id IS NOT NULL THEN emp.name
                  ELSE NULL
                END AS department,
                pos.title,
                per.first_name,
                per.last_name,
                sal.amount AS salary,
                job.start_date AS date_started
              FROM payroll_person AS per
              JOIN payroll_job AS job
              ON job.person_id = per.id
              JOIN payroll_salary AS sal
              ON sal.job_id = job.id
              JOIN payroll_position AS pos
              ON pos.id = job.position_id
              JOIN payroll_employer AS emp
              ON pos.employer_id = emp.id
              LEFT JOIN payroll_employer AS parent
              ON emp.parent_id = parent.id
            ), raw AS (
              SELECT
                employer,
                department,
                title,
                first_name,
                last_name,
                salary::NUMERIC,
                NULLIF(date_started, '')::DATE
              FROM {raw_payroll}
            )
            SELECT * FROM raw
            EXCEPT
            SELECT * FROM reconstructed
            UNION ALL
            SELECT * FROM reconstructed
            EXCEPT
            SELECT * FROM raw
        '''.format(raw_payroll=imp.raw_payroll_table)

        cursor.execute(reconstruct)

        assert not cursor.fetchone()
