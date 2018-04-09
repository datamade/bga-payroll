from django.db import connection


class ImportUtility(object):

    def __init__(self, s_file_id, upload_id):
        self.vintage = upload_id
        self.raw_payroll_table = 'raw_payroll_{}'.format(s_file_id)
        self.raw_position_table = 'raw_position_{}'.format(s_file_id)
        self.raw_salary_table = 'raw_salary_{}'.format(s_file_id)
        self.raw_person_table = 'raw_person_{}'.format(s_file_id)

    def populate_models_from_raw_data(self):
        self.insert_responding_agency()

        self.insert_employer()

        self.insert_position()

        self.select_raw_salary()
        self.insert_salary()

        self.select_raw_person()
        self.insert_person()

        self.link_person_salary()

    def insert_responding_agency(self):
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

    def select_raw_salary(self):
        # TO-DO: Document use of nextval here and in person select.
        select = '''
            WITH position_ids AS (
              SELECT
                pos.id AS position_id,
                pos.title AS position_title,
                emp.id AS employer_id,
                emp.name AS employer_name,
                parent.name AS parent_name
              FROM payroll_position AS pos
              JOIN payroll_employer AS emp
              ON pos.employer_id = emp.id
              LEFT JOIN payroll_employer AS parent
              ON emp.parent_id = parent.id
            ), raw_salary AS (
              SELECT
                record_id,
                position_id,
                salary,
                date_started,
                {vintage},
                nextval('payroll_salary_id_seq') AS salary_id
              FROM {raw_payroll} AS raw
              JOIN position_ids AS existing
              ON (
                raw.department = existing.employer_name
                AND raw.employer = existing.parent_name
                AND raw.title = existing.position_title
                AND raw.department IS NOT NULL
              ) OR (
                raw.employer = existing.employer_name
                AND raw.title = existing.position_title
                AND raw.department IS NULL
              )
            )
            SELECT * INTO {raw_salary} FROM raw_salary
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table,
                   raw_salary=self.raw_salary_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

    def insert_salary(self):
        insert = '''
            INSERT INTO payroll_salary (id, amount, start_date, vintage_id, position_id)
              SELECT
                salary_id,
                REGEXP_REPLACE(salary, '[^0-9,.]', '', 'g')::NUMERIC,
                NULLIF(TRIM(date_started), '')::DATE,
                {vintage},
                position_id
              FROM {raw_salary}
        '''.format(vintage=self.vintage,
                   raw_salary=self.raw_salary_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def select_raw_person(self):
        select = '''
            SELECT
              record_id,
              first_name,
              last_name,
              {vintage},
              nextval('payroll_person_id_seq') AS person_id
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

    def link_person_salary(self):
        insert = '''
            INSERT INTO payroll_person_salaries (person_id, salary_id)
              SELECT
                person_id,
                salary_id
              FROM {raw_person}
              JOIN {raw_salary}
              USING (record_id)
        '''.format(raw_person=self.raw_person_table,
                   raw_salary=self.raw_salary_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)
