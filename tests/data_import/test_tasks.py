from django.db import connection
import pytest

from data_import.tasks import copy_to_database
from data_import.utils.csv_meta import CsvMeta


@pytest.mark.django_db(transaction=True)
def test_copy_to_database(standardized_file,
                          real_file,
                          raw_table_teardown):

    s_file = standardized_file.build(standardized_file=real_file)

    copy_to_database(s_file_id=s_file.id)

    with connection.cursor() as cursor:
        cursor.execute('''
            SELECT EXISTS(
              SELECT 1
              FROM pg_tables
              WHERE tablename = '{}'
            )
        '''.format(s_file.raw_table_name))

        raw_table_exists = cursor.fetchone()[0]

        assert raw_table_exists

        cursor.execute('SELECT COUNT(*) FROM {}'.format(s_file.raw_table_name))

        n_records = cursor.fetchone()[0]

        # There are 99 records in the standard data fixture. If that
        # changes, this will fail.

        assert n_records == 99

        # We auto-generate record ID when copying raw data into the table,
        # so it is not a "required" field, e.g., omit it for comparison.

        cursor.execute('''
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{}'
              AND column_name != 'record_id'
        '''.format(s_file.raw_table_name))

        columns = [row[0] for row in cursor]

        assert set(columns) == set(CsvMeta.REQUIRED_FIELDS)
