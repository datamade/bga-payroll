from django.db import connection


class ImportUtility(object):

    def __init__(self, s_file_id):
        self.s_file_id = s_file_id

        def make_table_name(table_name):
            return 'raw_{0}_{1}'.format(table_name, self.s_file_id)

        self.raw_payroll_table = make_table_name('payroll')
        self.raw_employer_table = make_table_name('employer')
        self.raw_position_table = make_table_name('position')
        self.raw_salary_table = make_table_name('salary')
        self.raw_person_table = make_table_name('person')

    def import_new(self):
        self.select_raw_position()
        self.insert_employer()
        self.insert_position()
        self.select_raw_salary()

    def select_raw_position(self):
        query = '''
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
            cursor.execute(query)

    def insert_employer(self):
        insert_parents = '''
            INSERT INTO payroll_employer (name)
              SELECT DISTINCT employer FROM {}
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
        '''.format(self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert_parents)
            cursor.execute(insert_children)

    def insert_position(self):
        '''
        Get names, IDs, and (if applicable) parents from the
        employer table, and join to the raw table to select a list
        of positions, e.g., distinct employer / title combinations.
        '''
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
        '''.format(self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def select_raw_salary(self):
        query = '''
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
            cursor.execute(query)

    def insert_person(self):
        pass
