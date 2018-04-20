from django.db import connection

from data_import.models import StandardizedFile
from data_import.utils.table_names import TableNamesMixin
from data_import.utils.queues import RespondingAgencyQueue


class ImportUtility(TableNamesMixin):

    def __init__(self, s_file_id, init=False):
        super().__init__(s_file_id)

        self.s_file_id = s_file_id
        self.init = init

        s_file = StandardizedFile.objects.get(id=s_file_id)

        self.vintage = s_file.upload.id

    def populate_models_from_raw_data(self):
        self.insert_responding_agency()

        self.insert_employer()

        self.insert_position()

        self.select_raw_person()
        self.insert_person()

        self.select_raw_job()
        self.insert_job()

        self.insert_salary()

    def insert_responding_agency(self):
        if not self.init:
            q = RespondingAgencyQueue(self.s_file_id)
            q.initialize()

            insert = '''
                WITH unseen AS (
                  SELECT
                    DISTINCT responding_agency
                  FROM {raw} AS raw
                  LEFT JOIN data_import_respondingagency AS existing
                  ON raw.responding_agency = existing.name
                  WHERE existing.name IS NULL
                )
                INSERT INTO {review} (name)
                  SELECT * FROM unseen
            '''.format(raw=self.raw_payroll_table,
                       review=q.table_name)

        else:
            insert = '''
                INSERT INTO data_import_respondingagency (name)
                  SELECT
                    DISTINCT responding_agency
                  FROM {} AS raw
                  LEFT JOIN data_import_respondingagency AS existing
                  ON raw.responding_agency = existing.name
                  WHERE existing.name IS NULL
            '''.format(self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def insert_employer(self):
        '''
        Insert parents that do not already exist, then insert
        departments, no-op'ing on duplicates via the unique index
        on payroll_employer name / parent ID. The uniqueness of
        everything else is predicated on the uniqueness of the
        parents. TO-DO: Explain this in better English!
        '''
        insert_parents = '''
            INSERT INTO payroll_employer (name, vintage_id)
              SELECT
                DISTINCT employer,
                {vintage}
              FROM {raw_payroll} AS raw
              LEFT JOIN payroll_employer AS existing
              ON raw.employer = existing.name
              WHERE existing.name IS NULL
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

        insert_children = '''
            INSERT INTO payroll_employer (name, parent_id, vintage_id)
              SELECT DISTINCT ON (employer, department)
                department AS employer_name,
                parent.id AS parent_id,
                {vintage}
              FROM {raw_payroll} AS raw
              JOIN payroll_employer AS parent
              ON raw.employer = parent.name
              WHERE department IS NOT NULL
            ON CONFLICT DO NOTHING
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert_parents)
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
                raw.department = existing.employer_name
                AND raw.employer = existing.parent_name
                AND raw.department IS NOT NULL
              ) OR (
                raw.employer = existing.employer_name
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
