from django.db import connection
import pytest

from data_import import tasks
from data_import import utils
from payroll.models import Employer


@pytest.mark.celery
@pytest.mark.django_db(transaction=True)
def test_copy_to_database(raw_table_setup):
    s_file = raw_table_setup[1]

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

        # There are 54 records in the standard data fixture. If that
        # changes, this will fail.

        assert n_records == 54

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


class TestSelectUnseenBase(object):
    def run_and_validate_task(self):
        work = self.task.delay(s_file_id=self.s_file.id)
        work.get()

        self._assert_queue_len_equals_n_unseen()
        self._assert_existing_entity_not_enqueued()
        self._assert_status_updated()

    @property
    def _n_unseen(self):
        with connection.cursor() as cursor:
            cursor.execute(self.unseen_select)
            n_unseen, = cursor.fetchone()

        return n_unseen

    def _assert_queue_len_equals_n_unseen(self):
        assert self.queue.remaining == self._n_unseen

    def _assert_existing_entity_not_enqueued(self):
        remaining = True
        enqueued = []

        while remaining:
            uid, item = self.queue.checkout()

            if item:
                enqueued.append(item['name'])
            else:
                remaining = False

        assert self.existing_entity.name not in enqueued

    def _assert_status_updated(self):
        self.s_file.refresh_from_db()
        assert self.s_file.status == self.target_status


class TestSelectUnseenRespondingAgency(TestSelectUnseenBase):
    task = tasks.select_unseen_responding_agency
    target_status = 'responding agency unmatched'

    @property
    def unseen_select(self):
        select = '''
            SELECT
              COUNT(distinct raw.responding_agency) - 1
            FROM {raw_payroll} AS raw
        '''.format(raw_payroll=self.s_file.raw_table_name)

        return select

    @property
    def queue(self):
        return utils.RespondingAgencyQueue(self.s_file.id)

    @pytest.mark.django_db(transaction=True)
    def test_select_unseen_responding_agency(self,
                                             responding_agency,
                                             canned_data,
                                             raw_table_setup,
                                             queue_teardown):
        self.s_file = raw_table_setup[1]

        self.existing_entity = responding_agency.build(name=canned_data['Responding Agency'])

        self.run_and_validate_task()


class TestSelectUnseenParentEmployer(TestSelectUnseenBase):
    task = tasks.select_unseen_parent_employer
    target_status = 'parent employer unmatched'

    @property
    def unseen_select(self):
        select = '''
            SELECT
              COUNT(distinct raw.employer) - 1
            FROM {raw_employer} AS raw
        '''.format(raw_employer=self.s_file.raw_table_name)

        return select

    @property
    def queue(self):
        return utils.ParentEmployerQueue(self.s_file.id)

    @pytest.mark.django_db(transaction=True)
    def test_select_unseen_parent_employer(self,
                                           employer,
                                           canned_data,
                                           raw_table_setup,
                                           queue_teardown):

        self.s_file = raw_table_setup[1]

        self.existing_entity = employer.build(name=canned_data['Employer'])

        self.run_and_validate_task()


class TestSelectUnseenChildEmployer(TestSelectUnseenBase):
    task = tasks.select_unseen_child_employer
    target_status = 'child employer unmatched'

    @property
    def queue(self):
        return utils.ChildEmployerQueue(self.s_file.id)


class TestSelectUnseenChildEmployerExistingParent(TestSelectUnseenChildEmployer):
    @property
    def unseen_select(self):
        select = '''
            SELECT COUNT(*) - 1
            FROM (
              SELECT DISTINCT ON (TRIM(employer), TRIM(department))
              * FROM {raw_payroll}
              WHERE department IS NOT NULL
            ) AS child_employers
        '''.format(raw_payroll=self.s_file.raw_table_name)

        return select

    @pytest.mark.django_db(transaction=True)
    def test_select_unseen_child_employer_with_existing_parent(self,
                                                               employer,
                                                               canned_data,
                                                               raw_table_setup,
                                                               queue_teardown):
        self.s_file = raw_table_setup[1]

        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT TRIM(employer) FROM {raw_payroll}
            '''.format(raw_payroll=self.s_file.raw_table_name))

            for record in cursor:
                parent_name, = record
                employer.build(name=parent_name)

        parent = Employer.objects.get(name=canned_data['Employer'])
        self.existing_entity = employer.build(name=canned_data['Department'], parent=parent)

        self.run_and_validate_task()


class TestSelectUnseenChildEmployerNewParent(TestSelectUnseenChildEmployer):
    @property
    def unseen_select(self):
        select = '''
            SELECT COUNT(*)
            FROM (
              SELECT DISTINCT ON (employer, department)
              * FROM {raw_payroll}
              WHERE employer != '{canned_data}'
                AND department IS NOT NULL
            ) AS child_employers
        '''.format(raw_payroll=self.s_file.raw_table_name,
                   canned_data=self.existing_entity.parent.name)

        return select

    @pytest.mark.dev
    @pytest.mark.django_db(transaction=True)
    def test_select_unseen_child_employer_with_new_parent(self,
                                                          employer,
                                                          canned_data,
                                                          raw_table_setup,
                                                          queue_teardown):
        self.s_file = raw_table_setup[1]

        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT DISTINCT employer FROM {raw_payroll}
            '''.format(raw_payroll=self.s_file.raw_table_name))

            for record in cursor:
                parent_name, = record
                employer.build(name=parent_name)

        parent = Employer.objects.get(name=canned_data['Employer'])
        parent.vintage = self.s_file.upload
        parent.save()

        self.existing_entity = employer.build(name=canned_data['Department'], parent=parent)

        self.run_and_validate_task()
