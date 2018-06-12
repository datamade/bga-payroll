from django.db import connection

from data_import.utils.table_names import TableNamesMixin
from data_import.utils.queues import ChildEmployerQueue, ParentEmployerQueue, \
    RespondingAgencyQueue


# TO-DO: Return select / insert counts for logging

class ImportUtility(TableNamesMixin):
    def __init__(self, s_file_id):
        super().__init__(s_file_id)

        self.s_file_id = s_file_id

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
            FROM {raw_payroll} AS raw
            LEFT JOIN data_import_respondingagency AS existing
            ON TRIM(LOWER(raw.responding_agency)) = TRIM(LOWER(existing.name))
            WHERE existing.name IS NULL
        '''.format(raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

            for agency in cursor:
                q.add({'name': agency[0]})

    def insert_responding_agency(self):
        insert = '''
            INSERT INTO data_import_respondingagency (name)
              SELECT
                DISTINCT responding_agency
              FROM {raw_payroll} AS raw
              LEFT JOIN data_import_respondingagency AS existing
              ON TRIM(LOWER(raw.responding_agency)) = TRIM(LOWER(existing.name))
              WHERE existing.name IS NULL
        '''.format(raw_payroll=self.raw_payroll_table)

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
            ON TRIM(LOWER(raw.employer)) = TRIM(LOWER(existing.name))
            AND existing.parent_id IS NULL
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
              LEFT JOIN payroll_employer AS existing
              ON TRIM(LOWER(raw.employer)) = TRIM(LOWER(existing.name))
              AND existing.parent_id IS NULL
              WHERE existing.name IS NULL
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert_parents)

        self._classify_parent_employers()
        self._insert_parent_employer_population()

    def _classify_parent_employers(self):
        '''
        In the future, there will be a review step to classify employers
        that are not in the canonical list, e.g., are not classified in this
        step. For now, just leave them unclassified.
        '''
        update = '''
            UPDATE payroll_employer
            SET taxonomy_id = model_taxonomy.id
            FROM raw_taxonomy
            JOIN payroll_employertaxonomy AS model_taxonomy
            USING (entity_type, chicago, cook_or_collar)
            WHERE TRIM(LOWER(payroll_employer.name)) = TRIM(LOWER(raw_taxonomy.entity))
              AND payroll_employer.parent_id IS NULL
        '''

        with connection.cursor() as cursor:
            cursor.execute(update)

    def _insert_parent_employer_population(self):
        '''
        All entities in the 2017 data could be matched to an entity in the
        raw_population data. This may or may not be true for future years.
        For now, just leave potential unmatched employers be.
        '''
        insert = '''
            INSERT INTO payroll_employerpopulation (
              employer_id,
              population,
              data_year
            )
              WITH unmatched_gov_units AS (
                SELECT
                  emp.id,
                  tax.entity_type
                FROM payroll_employer AS emp
                JOIN payroll_employertaxonomy AS tax
                ON emp.taxonomy_id = tax.id
                LEFT JOIN payroll_employerpopulation AS pop
                ON pop.employer_id = emp.id
                WHERE emp.parent_id IS NULL
                AND LOWER(tax.entity_type) in (
                  'municipal',
                  'county',
                  'township'
                )
                AND pop.employer_id IS NULL
              )
              SELECT DISTINCT ON (emp.id)
                emp.id,
                pop.population,
                pop.data_year
              FROM payroll_employer AS emp
              JOIN unmatched_gov_units AS unmatched
              USING (id)
              JOIN raw_population AS pop
              ON (
                TRIM(LOWER(emp.name)) = TRIM(LOWER(pop.name))
                AND LOWER(unmatched.entity_type) IN ('municipal', 'county')
                AND pop.classification != 'township'
              ) OR (
                TRIM(LOWER(REGEXP_REPLACE(emp.name, ' township', '', 'i'))) = TRIM(LOWER(pop.name))
                AND LOWER(unmatched.entity_type) = 'township'
                AND pop.classification = 'township'
              )
              /* There are a handful of instances where there are CDPs called
              the same thing as a city or village. They always have a smaller
              population. We want the city or village, so order by population
              in order to grab the larger population via DISTINCT ON. */
              ORDER BY emp.id, pop.population DESC
        '''

        with connection.cursor() as cursor:
            cursor.execute(insert)

    def select_unseen_child_employer(self):
        '''
        If the parent is new as of this vintage, don't force the
        user to review children, because we won't have seen any of
        them.
        '''
        q = ChildEmployerQueue(self.s_file_id)

        select = '''
            WITH child_employers AS (
              SELECT
                child.name AS employer_name,
                parent.name AS parent_name,
                parent.vintage_id = {vintage} AS new_parent
              FROM payroll_employer AS parent
              LEFT JOIN payroll_employer AS child
              ON parent.id = child.parent_id
            )
            SELECT DISTINCT ON (employer, department)
              employer,
              department
            FROM {raw_payroll} AS raw
            /* Join to filter records where new_parent is True.
            Parents will always exist, because we added them in
            the prior step. */
            LEFT JOIN child_employers AS parent
            ON TRIM(LOWER(raw.employer)) = TRIM(LOWER(parent.parent_name))
            /* Join to filter records with a corresponding child. */
            LEFT JOIN child_employers AS child
            ON TRIM(LOWER(raw.employer)) = TRIM(LOWER(child.parent_name))
            AND TRIM(LOWER(raw.department)) = TRIM(LOWER(child.employer_name))
            WHERE raw.department IS NOT NULL
            AND parent.new_parent IS FALSE
            AND child.employer_name IS NULL
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

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
                position.id AS position_id
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
              JOIN payroll_position AS position
              ON position.employer_id = existing.employer_id
              AND TRIM(LOWER(position.title)) = TRIM(LOWER(raw.title))
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
