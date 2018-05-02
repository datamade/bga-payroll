from django.db import connection

from data_import.utils.table_names import TableNamesMixin
from data_import.utils.queues import ChildEmployerQueue, ParentEmployerQueue, \
    RespondingAgencyQueue


# TO-DO: Return select / insert counts for logging

class ImportUtility(TableNamesMixin):

    def __init__(self, s_file_id, init=False):
        super().__init__(s_file_id)

        self.s_file_id = s_file_id
        self.init = init

        from data_import.models import StandardizedFile
        s_file = StandardizedFile.objects.get(id=s_file_id)

        self.vintage = s_file.upload.id

    def populate_models_from_raw_data(self):
        self.insert_responding_agency()

        self.insert_parent_employer()
        self.insert_child_employer()

        self.insert_position()

        self.select_raw_person()
        self.insert_person()

        self.select_raw_job()
        self.insert_job()

        self.insert_salary()

    def select_unseen_responding_agency(self):
        q = RespondingAgencyQueue(self.s_file_id)

        select = '''
            SELECT
              DISTINCT responding_agency
            FROM {raw} AS raw
            LEFT JOIN data_import_respondingagency AS existing
            ON TRIM(LOWER(raw.responding_agency)) = TRIM(LOWER(existing.name))
            WHERE existing.name IS NULL
        '''.format(raw=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

            for agency in cursor:
                q.add({'name': agency[0]})

    def insert_responding_agency(self):
        insert = '''
            INSERT INTO data_import_respondingagency (name)
              SELECT
                DISTINCT responding_agency
              FROM {} AS raw
              LEFT JOIN data_import_respondingagency AS existing
              ON TRIM(LOWER(raw.responding_agency)) = TRIM(LOWER(existing.name))
              WHERE existing.name IS NULL
        '''.format(self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def select_unseen_parent_employer(self):
        '''
        Select all parent employers we have not yet seen, regardless
        of whether they directly employ people (department is null) or
        not (department is not null). Do this, in order to avoid the
        user having to review every department of a parent employer
        that can be matched to an existing department.
        '''
        q = ParentEmployerQueue(self.s_file_id)

        select = '''
            SELECT DISTINCT employer
            FROM {raw_payroll} AS raw
            LEFT JOIN payroll_employer AS existing
            ON (
              TRIM(LOWER(raw.employer)) = TRIM(LOWER(existing.name))
              AND existing.parent_id IS NULL
            )
            WHERE existing.name IS NULL
        '''.format(raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

            for employer in cursor:
                q.add({'name': employer[0]})

    def insert_parent_employer(self):
        insert_parents = '''
            INSERT INTO payroll_employer (name, vintage_id)
              SELECT
                DISTINCT employer,
                {vintage}
              FROM {raw_payroll} AS raw
            ON CONFLICT DO NOTHING
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert_parents)

    def select_unseen_child_employer(self):
        '''
        If the parent is new as of this vintage, don't force the
        user to review children, because we won't have seen any of
        them.
        '''
        # TO-DO: This is selecting things we've already seen. Why?
        q = ChildEmployerQueue(self.s_file_id)

        select = '''
            WITH employers AS (
              SELECT
                child.name AS employer_name,
                parent.name AS parent_name,
                parent.vintage_id AS parent_vintage
              FROM payroll_employer AS child
              LEFT JOIN payroll_employer AS parent
              ON child.parent_id = parent.id
              JOIN data_import_upload AS upload
              ON parent.vintage_id = upload.id
            )
            SELECT DISTINCT ON (employer, department)
              employer,
              department
            FROM {raw_payroll} AS raw
            LEFT JOIN employers AS existing
            ON (
              TRIM(LOWER(raw.department)) = TRIM(LOWER(existing.employer_name))
              AND TRIM(LOWER(raw.employer)) = TRIM(LOWER(existing.parent_name))
              AND raw.department IS NOT NULL
              AND existing.parent_vintage != {vintage}
            )
            WHERE existing.employer_name IS NULL
        '''.format(raw_payroll=self.raw_payroll_table,
                   vintage=self.vintage)

        with connection.cursor() as cursor:
            cursor.execute(select)

            for employer in cursor:
                parent, department = employer
                q.add({
                    'name': department,
                    'parent': parent,
                })

    def insert_child_employer(self):
        insert_children = '''
            INSERT INTO payroll_employer (name, parent_id, vintage_id)
              SELECT DISTINCT ON (employer, department)
                department AS employer_name,
                parent.id AS parent_id,
                {vintage}
              FROM {raw_payroll} AS raw
              JOIN payroll_employer AS parent
              ON TRIM(LOWER(raw.employer)) = TRIM(LOWER(parent.name))
              WHERE department IS NOT NULL
            ON CONFLICT DO NOTHING
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert_children)

    def insert_position(self):
        '''
        n.b., There is a unique index on payroll_position
        (employer_id, title), so duplicate insertions are
        no'oped with ON CONFLICT DO NOTHING.
        '''
        insert = '''
            INSERT INTO payroll_position (employer_id, title, vintage_id)
              WITH employer_ids AS (
                SELECT
                  child.id AS employer_id,
                  child.name AS employer_name,
                  parent.name AS parent_name
                FROM payroll_employer AS child
                LEFT JOIN payroll_employer AS parent
                ON child.parent_id = parent.id
              )
              SELECT
                employer_id,
                COALESCE(title, 'EMPLOYEE'),
                {vintage}
              FROM {raw_payroll} AS raw
              JOIN employer_ids AS existing
              ON (
                TRIM(LOWER(raw.department)) = TRIM(LOWER(existing.employer_name))
                AND TRIM(LOWER(raw.employer)) = TRIM(LOWER(existing.parent_name))
                AND raw.department IS NOT NULL
              ) OR (
                TRIM(LOWER(raw.employer)) = TRIM(LOWER(existing.employer_name))
                AND raw.department IS NULL
              )
            ON CONFLICT DO NOTHING
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def select_raw_person(self):
        select = '''
            SELECT
              record_id,
              first_name,
              last_name,
              {vintage},
              NEXTVAL('payroll_person_id_seq') AS person_id
              /* payroll_person does not have a uniquely identifying
              set of fields for performing joins. Instead, create an
              intermediate table with the unique record_id from the raw
              data and the corresponding Person ID, selected here, for
              use in a later join to create the Job table. */
            INTO {raw_person}
            FROM {raw_payroll}
        '''.format(vintage=self.vintage,
                   raw_person=self.raw_person_table,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

    def insert_person(self):
        insert = '''
            INSERT INTO payroll_person (id, first_name, last_name, vintage_id)
              SELECT
                person_id,
                first_name,
                last_name,
                {vintage}
              FROM {raw_person}
        '''.format(vintage=self.vintage,
                   raw_person=self.raw_person_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def select_raw_job(self):
        select = '''
            WITH employer_ids AS (
              SELECT
                child.id AS employer_id,
                child.name AS employer_name,
                parent.name AS parent_name
              FROM payroll_employer AS child
              LEFT JOIN payroll_employer AS parent
              ON child.parent_id = parent.id
            ), position_ids AS (
              SELECT
                record_id,
                pos.id AS position_id
              FROM {raw_payroll} AS raw
              JOIN employer_ids AS employer
              ON (
                raw.department = employer.employer_name
                AND raw.employer = employer.parent_name
                AND raw.department IS NOT NULL
              ) OR (
                raw.employer = employer.employer_name
                AND raw.department IS NULL
              )
              JOIN payroll_position AS pos
              ON pos.employer_id = employer.employer_id
              AND pos.title = raw.title
            )
            SELECT
              record_id,
              person_id,
              position_id,
              NULLIF(TRIM(date_started), '')::DATE AS start_date,
              NEXTVAL('payroll_job_id_seq') AS job_id
              /* payroll_job does not have a uniquely identifying
              set of fields for performing joins. Instead, create an
              intermediate table with the unique record_id from the raw
              data and the corresponding Job ID, selected here, for
              use in a later join to create the Salary table. */
            INTO {raw_job}
            FROM {raw_person}
            JOIN position_ids
            USING (record_id)
            JOIN {raw_payroll}
            USING (record_id)
        '''.format(raw_job=self.raw_job_table,
                   raw_person=self.raw_person_table,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

    def insert_job(self):
        insert = '''
            INSERT INTO payroll_job (id, person_id, position_id, start_date, vintage_id)
              SELECT
                job_id,
                person_id,
                position_id,
                start_date,
                {vintage}
              FROM {raw_job}
            ON CONFLICT DO NOTHING
        '''.format(vintage=self.vintage,
                   raw_job=self.raw_job_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def insert_salary(self):
        insert = '''
            INSERT INTO payroll_salary (job_id, amount, vintage_id)
              SELECT
                raw_job.job_id,
                REGEXP_REPLACE(salary, '[^0-9.]', '', 'g')::NUMERIC,
                {vintage}
              FROM {raw_payroll}
              JOIN {raw_job} AS raw_job
              USING (record_id)
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table,
                   raw_job=self.raw_job_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)
