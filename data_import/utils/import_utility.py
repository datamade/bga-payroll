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

        self.reporting_year = s_file.reporting_year  # Actual year
        self.vintage = s_file.upload.id  # Standard file upload

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
              DISTINCT TRIM(raw.responding_agency)
            FROM {raw_payroll} AS raw
            LEFT JOIN data_import_respondingagencyalias AS existing
            ON TRIM(raw.responding_agency) = TRIM(existing.name)
            WHERE existing.name IS NULL
        '''.format(raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

            for agency in cursor:
                q.add({'name': agency[0]})

    def insert_responding_agency(self):
        # Unseen names mapped to an existing responding agency will have been
        # added as aliases, i.e., they will no longer appear in this select.
        from data_import.models import RespondingAgency, RespondingAgencyAlias

        select = '''
            SELECT
              DISTINCT TRIM(responding_agency)
            FROM {raw_payroll} AS raw
            LEFT JOIN data_import_respondingagencyalias AS existing
            ON TRIM(raw.responding_agency) = TRIM(existing.name)
            WHERE existing.name IS NULL
        '''.format(raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

            for row in cursor:
                name, = row
                agency = RespondingAgency.objects.create(name=name)
                RespondingAgencyAlias.objects.create(name=name, responding_agency=agency)

        self._link_responding_agency_with_standardized_file()

    def _link_responding_agency_with_standardized_file(self):
        insert = '''
            INSERT INTO data_import_standardizedfile_responding_agencies (
                standardizedfile_id,
                respondingagency_id
            )
            SELECT DISTINCT ON (agency.id)
              {s_file_id},
              agency.responding_agency_id
            FROM {raw_payroll} AS raw
            JOIN data_import_respondingagencyalias AS agency
            ON TRIM(raw.responding_agency) = TRIM(agency.name)
        '''.format(s_file_id=self.s_file_id,
                   raw_payroll=self.raw_payroll_table)

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
            SELECT
              DISTINCT TRIM(employer)
            FROM {raw_payroll} AS raw
            LEFT JOIN payroll_employeralias AS alias
            ON TRIM(raw.employer) = TRIM(alias.name)
            LEFT JOIN payroll_employer AS existing
            ON alias.employer_id = existing.id
            WHERE existing.parent_id IS NULL
            AND alias.name IS NULL
        '''.format(raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select)

            for employer in cursor:
                q.add({'name': employer[0]})

    def insert_parent_employer(self):
        from payroll.models import Employer, EmployerAlias

        select_parents = '''
            SELECT
              DISTINCT TRIM(employer)
            FROM {raw_payroll} AS raw
            LEFT JOIN payroll_employeralias AS alias
            ON TRIM(raw.employer) = TRIM(alias.name)
            LEFT JOIN payroll_employer AS existing
            ON alias.employer_id = existing.id
            WHERE existing.parent_id IS NULL
            AND alias.name IS NULL
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(select_parents)

            for row in cursor:
                name, = row
                employer = Employer.objects.create(name=name, vintage_id=self.vintage)
                EmployerAlias.objects.create(name=name, employer=employer)

        self._insert_unit_responding_agency()
        self._classify_parent_employers()
        self._insert_parent_employer_population()

    def _classify_parent_employers(self):
        '''
        In the future, there will be a review step to classify employers
        that are not in the canonical list, e.g., are not classified in this
        step. For now, just leave them unclassified.
        '''
        update_non_school_districts = '''
            UPDATE payroll_employer
            SET taxonomy_id = model_taxonomy.id
            FROM raw_taxonomy
            JOIN payroll_employertaxonomy AS model_taxonomy
            USING (entity_type, chicago, cook_or_collar)
            WHERE LOWER(payroll_employer.name) = LOWER(raw_taxonomy.entity)
              AND payroll_employer.parent_id IS NULL
              AND payroll_employer.taxonomy_id IS NULL
        '''

        update_school_districts = '''
            UPDATE payroll_employer
            SET taxonomy_id = (
              SELECT id FROM payroll_employertaxonomy
              WHERE entity_type ilike 'school district'
              AND chicago = FALSE
            )
            /* ISBE reports school district salaries. The state
            reports ISBE salaries. Record keeping is fun! */
            FROM (
              SELECT
                unit.id AS unit_id
              FROM payroll_employer AS unit
              JOIN payroll_unitrespondingagency AS ura
              ON unit.id = ura.unit_id
              JOIN data_import_respondingagency AS ra
              ON ura.responding_agency_id = ra.id
              WHERE ra.name ilike 'isbe'
            ) AS isbe_reported
            WHERE payroll_employer.id = isbe_reported.unit_id
              AND payroll_employer.taxonomy_id IS NULL
        '''

        update_higher_ed = '''
            UPDATE payroll_employer
            SET taxonomy_id = (
              SELECT id FROM payroll_employertaxonomy
              WHERE entity_type ilike 'higher education'
              AND chicago = FALSE
            )
            FROM (
              SELECT
                unit.id AS unit_id
              FROM payroll_employer AS unit
              JOIN payroll_unitrespondingagency AS ura
              ON unit.id = ura.unit_id
              JOIN data_import_respondingagency AS ra
              ON ura.responding_agency_id = ra.id
              WHERE ra.name ilike 'ibhe'
            ) AS ibhe_reported
            WHERE payroll_employer.id = ibhe_reported.unit_id
              AND payroll_employer.taxonomy_id IS NULL
        '''

        with connection.cursor() as cursor:
            cursor.execute(update_non_school_districts)
            cursor.execute(update_school_districts)
            cursor.execute(update_higher_ed)

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
                LOWER(emp.name) = LOWER(pop.name)
                AND LOWER(unmatched.entity_type) IN ('municipal', 'county')
                AND pop.classification != 'township'
              ) OR (
                LOWER(REGEXP_REPLACE(emp.name, ' township', '', 'i')) = LOWER(pop.name)
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

    def _insert_unit_responding_agency(self):
        insert = '''
            INSERT INTO payroll_unitrespondingagency (
              unit_id,
              responding_agency_id,
              reporting_year
            )
            SELECT DISTINCT ON (emp.id, agency.id)
              emp.id,
              agency.id,
              {reporting_year}
            FROM {raw_payroll} AS raw
            JOIN payroll_employer AS emp
            ON TRIM(raw.employer) = TRIM(emp.name)
            JOIN data_import_respondingagency AS agency
            ON TRIM(raw.responding_agency) = TRIM(agency.name)
            WHERE emp.parent_id IS NULL
            ON CONFLICT DO NOTHING
        '''.format(reporting_year=self.reporting_year,
                   raw_payroll=self.raw_payroll_table)

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
            ON TRIM(raw.employer) = TRIM(parent.parent_name)
            /* Join to filter records with a corresponding child. */
            LEFT JOIN child_employers AS child
            ON TRIM(raw.employer) = TRIM(child.parent_name)
            AND TRIM(raw.department) = TRIM(child.employer_name)
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
              ON TRIM(raw.employer) = TRIM(parent.name)
              WHERE department IS NOT NULL
            ON CONFLICT DO NOTHING
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table)

        with connection.cursor() as cursor:
            cursor.execute(insert_children)

        self._add_employer_universe()

    def _add_employer_universe(self):
        update = '''
            WITH pattern_matched_employers AS (
              SELECT
                id,
                name,
                CASE
                  WHEN
                    (name ~* E'\\mpd'
                    OR name ~* E'(?<!state )police'
                    OR name ~* E'(?<!homeland )security'
                    OR name ~* E'public safety')
                    AND name !~* E'(board|comm(isss?ion)?(er)?s?)'
                  THEN 'Police Department'
                  WHEN name ~* E'\\m(fp?d|fire)' THEN 'Fire Department'
                END AS match
              FROM payroll_employer
              /* Only add departments to universes. */
              WHERE parent_id IS NOT NULL
              /* Only classify unclassified departments. */
              AND universe_id IS NULL
            )
            UPDATE payroll_employer
            SET universe_id = xwalk.universe_id FROM (
              SELECT
                emp.id AS employer_id,
                uni.id AS universe_id
              FROM pattern_matched_employers AS emp
              JOIN payroll_employeruniverse AS uni
              ON emp.match = uni.name
            ) xwalk
            WHERE payroll_employer.id = xwalk.employer_id
        '''

        with connection.cursor() as cursor:
            cursor.execute(update)

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
                COALESCE(title, 'Employee'),
                {vintage}
              FROM {raw_payroll} AS raw
              JOIN employer_ids AS existing
              ON (
                TRIM(raw.department) = TRIM(existing.employer_name)
                AND TRIM(raw.employer) = TRIM(existing.parent_name)
                AND raw.department IS NOT NULL
              ) OR (
                TRIM(raw.employer) = TRIM(existing.employer_name)
                AND raw.department IS NULL
                /* Only allow for matches on top-level employers, i.e., where
                there is no parent. */
                AND existing.parent_name IS NULL
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
            INSERT INTO payroll_person (id, first_name, last_name, vintage_id, noindex)
              SELECT
                person_id,
                first_name,
                last_name,
                {vintage},
                FALSE
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
            )
            SELECT
              record_id,
              person_id,
              position.id AS position_id,
              NULLIF(TRIM(date_started), '')::DATE AS start_date,
              NEXTVAL('payroll_job_id_seq') AS job_id
              /* payroll_job does not have a uniquely identifying
              set of fields for performing joins. Instead, create an
              intermediate table with the unique record_id from the raw
              data and the corresponding Job ID, selected here, for
              use in a later join to create the Salary table. */
            INTO {raw_job}
            FROM {raw_person}
            JOIN {raw_payroll} AS raw
            USING (record_id)
            JOIN employer_ids AS emp
            ON (
              TRIM(raw.department) = TRIM(emp.employer_name)
              AND TRIM(raw.employer) = TRIM(emp.parent_name)
              AND raw.department IS NOT NULL
            ) OR (
              TRIM(raw.employer) = TRIM(emp.employer_name)
              AND raw.department IS NULL
              /* Only allow for matches on top-level employers, i.e., where
              there is no parent. */
              AND emp.parent_name IS NULL
            )
            JOIN payroll_position AS position
            ON position.employer_id = emp.employer_id
            AND TRIM(position.title) = TRIM(COALESCE(raw.title, 'Employee'))
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
            INSERT INTO payroll_salary (job_id, amount, extra_pay, vintage_id)
              SELECT
                raw_job.job_id,
                REGEXP_REPLACE(base_salary, '[^0-9.]', '', 'g')::NUMERIC,
                REGEXP_REPLACE(extra_pay, '[^0-9.]', '', 'g')::NUMERIC,
                {vintage}
              FROM {raw_payroll}
              JOIN {raw_job} AS raw_job
              USING (record_id)
        '''.format(vintage=self.vintage,
                   raw_payroll=self.raw_payroll_table,
                   raw_job=self.raw_job_table)

        with connection.cursor() as cursor:
            cursor.execute(insert)
