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


@pytest.mark.dev
@pytest.mark.parametrize('raw_field,task,queue,status,match_vintage', [
    ('Responding Agency', tasks.select_unseen_responding_agency, utils.RespondingAgencyQueue, 'responding agency unmatched', False),
    ('Employer', tasks.select_unseen_parent_employer, utils.ParentEmployerQueue, 'parent employer unmatched', False),
    ('Department', tasks.select_unseen_child_employer, utils.ChildEmployerQueue, 'child employer unmatched', False),
    ('Department', tasks.select_unseen_child_employer, utils.ChildEmployerQueue, 'child employer unmatched', True),
])
@pytest.mark.django_db(transaction=True)
def test_select_unseen_responding_agency(transactional_db,
                                         responding_agency,
                                         employer,
                                         canned_data,
                                         raw_table_setup,
                                         queue_teardown,
                                         raw_field,
                                         task,
                                         queue,
                                         status,
                                         match_vintage):
    s_file = raw_table_setup

    with connection.cursor() as cursor:
        if raw_field == 'Responding Agency':
            existing = responding_agency.build(name=canned_data['Responding Agency'])

            select = '''
                SELECT
                  COUNT(distinct raw.responding_agency)
                FROM {raw_payroll} AS raw
                LEFT JOIN data_import_respondingagency AS existing
                ON raw.responding_agency = existing.name
                WHERE existing.name IS NULL
            '''.format(raw_payroll=s_file.raw_table_name)

        elif raw_field == 'Employer':
            existing = employer.build(name=canned_data['Employer'])

            select = '''
                SELECT
                  COUNT(distinct raw.employer)
                FROM {raw_payroll} AS raw
                LEFT JOIN payroll_employer AS existing
                ON raw.employer = existing.name
                AND existing.parent_id IS NULL
                WHERE existing.name IS NULL
            '''.format(raw_payroll=s_file.raw_table_name)

        elif raw_field == 'Department':
            parent = employer.build(name=canned_data['Employer'])

            if match_vintage:
                parent.vintage = s_file.upload
                parent.save()

            existing = employer.build(name=canned_data['Department'], parent=parent)

            select = '''
                WITH child_employers AS (
                    SELECT
                      child.name AS employer_name,
                      parent.name AS parent_name,
                      parent.vintage_id AS parent_vintage
                    FROM payroll_employer AS child
                    JOIN payroll_employer AS parent
                    ON child.parent_id = parent.id
                ), unseen_child_employers AS (
                    SELECT DISTINCT ON (raw.employer, raw.department)
                      raw.employer,
                      raw.department
                    FROM {raw_payroll} AS raw
                    LEFT JOIN child_employers AS existing
                    ON raw.department = existing.employer_name
                    AND raw.employer = existing.parent_name
                    WHERE existing.employer_name IS NULL
                    AND raw.department IS NOT NULL
                )
                SELECT COUNT(*) FROM unseen_child_employers
            '''.format(raw_payroll=s_file.raw_table_name,
                       vintage=s_file.upload.id)

        cursor.execute(select)

        n_unseen, = cursor.fetchone()

    work = task.delay(s_file_id=s_file.id)
    work.get()

    q = queue(s_file.id)

    assert q.remaining == n_unseen

    remaining = True
    enqueued = []

    while remaining:
        uid, item = q.checkout()

        if item:
            enqueued.append(item['name'])
        else:
            remaining = False

    assert existing.name not in enqueued

    s_file.refresh_from_db()

    assert s_file.status == status
