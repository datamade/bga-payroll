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
        self.select_raw_employer()
        self.select_raw_position()
        self.insert_employer()

    def select_raw_employer(self):
        query = '''
            SELECT *
            INTO {raw_employer}
            FROM (
              SELECT
                DISTINCT employer AS employer_name,
                NULL AS parent_name
              FROM {raw_payroll}
              UNION
              SELECT DISTINCT ON (employer, department)
                department AS employer_name,
                employer AS parent_name
              FROM {raw_payroll}
            ) AS employers
        '''.format(raw_employer=self.raw_employer_table,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(query)

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
        '''
        - Select employers with no parent, and insert them into
          payroll_employer.
        - Join employers with a parent with payroll_employer to
          retrieve the appropriate parent ID, and insert them into
          payroll employer.

        n.b. In both tables, parent is null for top-level employers.
        '''
        insert_parents = '''
            INSERT INTO payroll_employer (name)
              SELECT
                employer_name
              FROM {}
              WHERE parent_name IS NULL
        '''.format(self.raw_employer_table)

        insert_children = '''
            INSERT INTO payroll_employer (name, parent_id)
              SELECT
                child.employer_name,
                parent.id
              FROM {} AS child
              JOIN payroll_employer AS parent
              ON child.parent_name = parent.name
              WHERE parent.parent_id IS NULL
              AND child.parent_name IS NOT NULL
        '''.format(self.raw_employer_table)

        with connection.cursor() as cursor:
            cursor.execute(insert_parents)
            cursor.execute(insert_children)

    def insert_position(self):
        pass

    def insert_salary(self):
        '''
        Select employer id, employer name, and parent name
        from employer table (for joining to raw table):

        SELECT
          child.id AS employer_id,
          child.name AS employer_name,
          parent.name AS parent_name
        FROM payroll_employer AS child
        JOIN payroll_employer AS parent
        ON child.parent_id = parent.id
        UNION
        SELECT
          id,
          name AS employer_name,
          null AS parent_name
        FROM payroll_employer
        WHERE parent_id IS NULL
        '''
        pass

    def insert_person(self):
        pass
