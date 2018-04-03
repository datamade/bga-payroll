from django.db import connection


class ImportUtility(object):

    def __init__(self, s_file_id):
        self.raw_payroll_table = 'raw_payroll_{}'.format(s_file_id)
        self.raw_position_table = 'raw_position_{}'.format(s_file_id)
        self.raw_salary_table = 'raw_salary_{}'.format(s_file_id)

        self.salary_lookup_table = 'salary_lookup_{}'.format(s_file_id)
        self.person_lookup_table = 'person_lookup_{}'.format(s_file_id)

    def import_new(self):
        self.insert_employer()
        self.select_raw_position()
        self.insert_position()
        self.select_raw_salary()
        self.insert_salary()
        self.insert_person()
        self.link_person_salary()

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
              SELECT DISTINCT ON (employer, department, title)
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
              data_year
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
            WITH raw_ordered AS (
              SELECT *
              FROM {raw_salary}
              ORDER BY salary DESC
            ), created_people AS (
              INSERT INTO payroll_salary (amount, start_date, vintage, position_id)
                SELECT
                  REGEXP_REPLACE(salary, '[^0-9,.]', '', 'g')::NUMERIC,
                  NULLIF(TRIM(date_started), '')::DATE,
                  data_year,
                  position_id
                FROM raw_ordered
              RETURNING id
            )
            SELECT
              (SELECT record_id FROM raw_ordered),
              (SELECT id FROM created_people) AS salary_id
            INTO {salary_lookup}
        '''.format(raw_salary=self.raw_salary_table,
                   salary_lookup=self.salary_lookup_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def insert_person(self):
        '''
        Default to not collapsing people within a year. Insert
        first and last name from raw_payroll, and select record_id
        and payroll_person.id into an intermediate table to create
        salary relationship.
        '''
        insert = '''
            WITH raw_ordered AS (
              SELECT
                record_id,
                first_name,
                last_name
              FROM {raw_payroll}
              ORDER BY last_name, first_name
            ), created_people AS (
              INSERT INTO payroll_person (first_name, last_name)
                SELECT
                  first_name,
                  last_name
                FROM raw_ordered
              RETURNING id
            )
            SELECT
              (SELECT record_id FROM raw_ordered),
              (SELECT id FROM created_people) AS person_id
            INTO {person_lookup}
        '''.format(raw_payroll=self.raw_payroll_table,
                   person_lookup=self.person_lookup_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def link_person_salary(self):
        insert = '''
            INSERT INTO payroll_person_salaries (person_id, salary_id)
              SELECT
                person_id,
                salary_id
              FROM {person_lookup}
              JOIN {salary_lookup}
              USING (record_id)
        '''

        with connection.cursor() as cursor:
            cursor.execute(insert)
