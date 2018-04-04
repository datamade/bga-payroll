from django.db import connection


class ImportUtility(object):

    def __init__(self, s_file_id):
        self.raw_payroll_table = 'raw_payroll_{}'.format(s_file_id)
        self.raw_position_table = 'raw_position_{}'.format(s_file_id)
        self.raw_salary_table = 'raw_salary_{}'.format(s_file_id)
        self.raw_person_table = 'raw_person_{}'.format(s_file_id)

    def populate_models_from_raw_data(self):
        self.insert_responding_agency()

        self.insert_employer()

        self.select_raw_position()
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
            INSERT INTO payroll_employer (name)
              SELECT DISTINCT employer
              FROM {} AS raw
              LEFT JOIN payroll_employer AS existing
              ON raw.employer = existing.name
              WHERE existing.name IS NULL
        '''.format(self.raw_payroll_table)

        insert_children = '''
            INSERT INTO payroll_employer (name, parent_id)
              SELECT DISTINCT ON (employer, department)
                department AS employer_name,
                parent.id AS parent_id
              FROM {} AS child
              JOIN payroll_employer AS parent
              ON child.employer = parent.name
              WHERE department IS NOT NULL
            ON CONFLICT DO NOTHING
        '''.format(self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert_parents)
            cursor.execute(insert_children)

    def select_raw_position(self):
        select = '''
            SELECT DISTINCT ON (employer, department, title)
              COALESCE(department, employer) AS employer_name,
              CASE WHEN department IS NULL THEN NULL
                ELSE employer
              END AS parent_name,
              title
            INTO {raw_position}
            FROM {raw_payroll}
        '''.format(raw_position=self.raw_position_table,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

    def insert_position(self):
        insert = '''
            INSERT INTO payroll_position (employer_id, title)
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
                COALESCE(title, 'EMPLOYEE')
              FROM {} AS raw
              JOIN employer_ids AS emp
              ON COALESCE(raw.department, raw.employer) = emp.employer_name
              AND CASE WHEN raw.department IS NOT NULL THEN raw.employer
                  ELSE 'No parent'
                  END = CASE WHEN raw.department IS NOT NULL THEN emp.parent_name
                  ELSE 'No parent'
                  END
            ON CONFLICT DO NOTHING
        '''.format(self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def select_raw_salary(self):
        select = '''
            WITH named_positions AS (
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
            )
            SELECT
              record_id,
              position_id,
              salary,
              date_started,
              data_year,
              nextval('payroll_salary_id_seq') AS salary_id
            INTO {raw_salary}
            FROM {raw_payroll} AS raw
            JOIN named_positions AS pos
            ON COALESCE(raw.title, 'EMPLOYEE') = pos.position_title
            AND COALESCE(raw.department, raw.employer) = pos.employer_name
            AND CASE WHEN raw.department IS NOT NULL THEN raw.employer
                ELSE 'No parent'
                END = CASE WHEN raw.department IS NOT NULL THEN pos.parent_name
                ELSE 'No parent'
                END
        '''.format(raw_salary=self.raw_salary_table,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

    def insert_salary(self):
        insert = '''
            INSERT INTO payroll_salary (id, amount, start_date, vintage, position_id)
              SELECT
                salary_id,
                REGEXP_REPLACE(salary, '[^0-9,.]', '', 'g')::NUMERIC,
                NULLIF(TRIM(date_started), '')::DATE,
                data_year,
                position_id
              FROM {raw_salary}
        '''.format(raw_salary=self.raw_salary_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def select_raw_person(self):
        select = '''
            SELECT
              record_id,
              first_name,
              last_name,
              nextval('payroll_person_id_seq') AS person_id
            INTO {raw_person}
            FROM {raw_payroll}
        '''.format(raw_person=self.raw_person_table,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

    def insert_person(self):
        insert = '''
            INSERT INTO payroll_person (id, first_name, last_name)
              SELECT
                person_id,
                first_name,
                last_name
              FROM {raw_person}
        '''.format(raw_person=self.raw_person_table)

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
