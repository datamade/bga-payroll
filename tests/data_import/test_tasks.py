from django.db import connection
import pytest

from data_import import tasks
from data_import import utils


@pytest.mark.celery
@pytest.mark.django_db(transaction=True)
def test_copy_to_database(raw_table_setup):
    s_file = raw_table_setup

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

        # There are 101 records in the standard data fixture. If that
        # changes, this will fail.

        assert n_records == 101

        # We auto-generate record ID when copying raw data into the table,
        # so it is not a "required" field, e.g., omit it for comparison.

        cursor.execute('''
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = '{}'
              AND column_name != 'record_id'
        '''.format(s_file.raw_table_name))

        columns = [row[0] for row in cursor]

        assert set(columns) == set(utils.CsvMeta.REQUIRED_FIELDS)

    s_file.refresh_from_db()

    assert s_file.status == 'copied to database'


@pytest.mark.django_db(transaction=True)
def test_select_unseen_responding_agency(transactional_db,
                                         responding_agency,
                                         raw_table_setup,
                                         queue_teardown):

    # Create a responding agency, so we can check that it is not added to
    # the review queue.
    existing = responding_agency.build()

    s_file = raw_table_setup

    work = tasks.select_unseen_responding_agency.delay(s_file_id=s_file.id)
    work.get()

    queue = utils.RespondingAgencyQueue(s_file.id)

    # There are three distinct responding agencies in the data fixture. We
    # added a responding agency matching one of them. Assert that the other
    # two were added to the queue.
    #
    # n.b., If the data fixture changes, this test will need to be updated.
    assert queue.remaining == 2
    remaining = True

    enqueued = []

    while remaining:
        uid, item = queue.checkout()

        if item:
            enqueued.append(item['name'])
        else:
            remaining = False

    # Assert we have not added the responding agency we've already seen
    # to the review queue.
    assert existing.name not in enqueued

    # Assert that the items we did are, are in fact responding agencies
    # in the raw data.
    with connection.cursor() as cursor:
        for item in enqueued:
            cursor.execute('''
                SELECT EXISTS(
                  SELECT 1 FROM {raw_payroll}
                  WHERE responding_agency = '{item}'
                )
            '''.format(raw_payroll=s_file.raw_table_name, item=item))

            exists, = cursor.fetchone()
            assert exists

    s_file.refresh_from_db()

    assert s_file.status == 'responding agency unmatched'
