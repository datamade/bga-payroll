from django.db import connection
from django.db.models import Q, FloatField, Sum
from django.db.models.functions import Coalesce, NullIf
from postgres_stats.aggregates import Percentile
from rest_framework import serializers

from payroll.models import Employer, Unit, Department, Salary
from payroll.charts import ChartHelperMixin


# /v1/index/YEAR
class IndexSerializer(serializers.Serializer, ChartHelperMixin):

    salary_count = serializers.SerializerMethodField()
    unit_count = serializers.SerializerMethodField()
    department_count = serializers.SerializerMethodField()
    salary_json = serializers.SerializerMethodField()

    def get_salary_count(self, data_year):
        return Salary.objects.filter(vintage__standardized_file__reporting_year=data_year).count()

    def get_unit_count(self, data_year):
        return Unit.objects.filter(vintage__standardized_file__reporting_year=data_year).count()

    def get_department_count(self, data_year):
        return Department.objects.filter(vintage__standardized_file__reporting_year=data_year).count()

    def get_salary_json(self, data_year):
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT
                  COALESCE(amount, 0) + COALESCE(extra_pay, 0)
                FROM payroll_salary AS salary
                JOIN data_import_upload AS upload
                ON salary.vintage_id = upload.id
                JOIN data_import_standardizedfile AS file
                ON upload.id = file.upload_id
                WHERE file.reporting_year = {}
            '''.format(data_year))

            all_salaries = [x[0] for x in cursor]

        try:
            return self.bin_salary_data(all_salaries)

        except ValueError:
            if settings.DEBUG:
                return []
            raise


class EmployerSerializer(serializers.ModelSerializer, ChartHelperMixin):

    salaries = serializers.SerializerMethodField()
    median_tp = serializers.SerializerMethodField()
    median_bp = serializers.SerializerMethodField()
    median_ep = serializers.SerializerMethodField()
    headcount = serializers.SerializerMethodField()
    total_expenditure = serializers.SerializerMethodField()
    salary_percentile = serializers.SerializerMethodField()
    expenditure_percentile = serializers.SerializerMethodField()
    employee_salary_json = serializers.SerializerMethodField()
    source_link = serializers.SerializerMethodField()
    payroll_expenditure = serializers.SerializerMethodField()

    @property
    def employer_queryset(self):
        return Employer.objects.filter(
            Q(id=self.instance.id) | Q(parent_id=self.instance.id)
        )

    @property
    def median_salaries(self):
        if not hasattr(self, '_median_salaries'):
            median_base_pay = Percentile(
                'positions__jobs__salaries__amount', 0.5, output_field=FloatField()
            )
            median_extra_pay = Percentile(
                'positions__jobs__salaries__extra_pay', 0.5, output_field=FloatField()
            )
            median_total_pay = Percentile(
                (
                    NullIf(
                        Coalesce('positions__jobs__salaries__amount', 0) +
                        Coalesce('positions__jobs__salaries__extra_pay', 0), 0
                    )
                ), 0.5, output_field=FloatField()
            )

            self._median_salaries = self.employer_queryset.aggregate(
                median_base_pay=median_base_pay,
                median_extra_pay=median_extra_pay,
                median_total_pay=median_total_pay
            )

        return self._median_salaries

    @property
    def entity_payroll(self):
        if not hasattr(self, '_entity_payroll'):
            entity_base_pay = Sum(Coalesce("positions__jobs__salaries__amount", 0))
            entity_extra_pay = Sum(Coalesce("positions__jobs__salaries__extra_pay", 0))

            self._entity_payroll = self.employer_queryset.aggregate(
                base_pay=entity_base_pay,
                extra_pay=entity_extra_pay
            )

        return self._entity_payroll

    def get_salaries(self, obj):
        '''
        TODO: Return attributes needed in template.
        '''
        return list(str(s) for s in Salary.of_employer(obj.id, n=5))

    def get_median_tp(self, obj):
        return self.median_salaries['median_total_pay']

    def get_median_bp(self, obj):
        return self.median_salaries['median_base_pay']

    def get_median_ep(self, obj):
        return self.median_salaries['median_extra_pay']

    def get_headcount(self, obj):
        return len(obj.employee_salaries)

    def get_total_expenditure(self, obj):
        return self.entity_payroll['base_pay'] + self.entity_payroll['extra_pay']

    def get_salary_percentile(self, obj):
        if obj.is_unclassified:
            return 'N/A'

        query = '''
            WITH employer_parent_lookup AS (
              SELECT
                id,
                COALESCE(parent_id, id) AS parent_id
              FROM payroll_employer
            ),
            median_salaries_by_unit AS (
              SELECT
                percentile_cont(0.5) WITHIN GROUP (
                  ORDER BY COALESCE(salary.amount, 0) + COALESCE(salary.extra_pay, 0) ASC
                ) AS median_salary,
                lookup.parent_id AS unit_id
              FROM payroll_salary AS salary
              JOIN payroll_job AS job
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN employer_parent_lookup AS lookup
              ON position.employer_id = lookup.id
              JOIN payroll_employer AS employer
              ON lookup.parent_id = employer.id
              WHERE employer.taxonomy_id = {taxonomy}
              GROUP BY lookup.parent_id
            ),
            salary_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY median_salary ASC) AS percentile,
                unit_id
              FROM median_salaries_by_unit
            )
            SELECT percentile
            FROM salary_percentiles
            WHERE unit_id = {id}
            '''.format(taxonomy=obj.taxonomy.id,
                       id=obj.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def get_expenditure_percentile(self, obj):
        if obj.is_unclassified:
            return 'N/A'

        query = '''
            WITH employer_parent_lookup AS (
              SELECT
                id,
                COALESCE(parent_id, id) AS parent_id
              FROM payroll_employer
            ),
            expenditure_by_unit AS (
              SELECT
                SUM(COALESCE(salary.amount, 0) + COALESCE(salary.extra_pay, 0)) AS total_budget,
                lookup.parent_id AS unit_id
              FROM payroll_salary AS salary
              JOIN payroll_job AS job
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN employer_parent_lookup AS lookup
              ON position.employer_id = lookup.id
              JOIN payroll_employer AS employer
              ON lookup.parent_id = employer.id
              WHERE employer.taxonomy_id = {taxonomy}
              GROUP BY lookup.parent_id
            ),
            exp_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY total_budget ASC) AS percentile,
                unit_id
              FROM expenditure_by_unit
            )
            SELECT
              percentile
            FROM exp_percentiles
            WHERE unit_id = {id}
        '''.format(taxonomy=obj.taxonomy.id,
                   id=obj.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def get_employee_salary_json(self, obj):
        return self.bin_salary_data(obj.employee_salaries)

    def get_source_link(self, obj):
        return obj.source_file(self.context['data_year'])

    def get_payroll_expenditure(self, obj):
        return self._make_pie_chart('payroll-expenditure-chart',
                                    self.entity_payroll['base_pay'],
                                    self.entity_payroll['extra_pay'])


# /v1/units/SLUG/YEAR
class UnitSerializer(EmployerSerializer):

    class Meta:
        model = Unit
        fields = '__all__'

    department_salaries = serializers.SerializerMethodField()
    population_percentile = serializers.SerializerMethodField()
    highest_spending_department = serializers.SerializerMethodField()
    composition_json = serializers.SerializerMethodField()

    def get_department_salaries(self, obj):
        pass

    def get_population_percentile(self, obj):
        if obj.get_population() is None:
            return 'N/A'

        query = '''
            WITH pop_percentile AS (
              SELECT
                percent_rank() OVER (ORDER BY pop.population ASC) AS percentile,
                pop.employer_id AS unit_id
              FROM payroll_employerpopulation AS pop
              JOIN payroll_employer AS emp
              ON pop.employer_id = emp.id
              JOIN payroll_employertaxonomy AS tax
              ON emp.taxonomy_id = tax.id
              WHERE tax.id = {taxonomy}
            )
            SELECT percentile FROM pop_percentile
            WHERE unit_id = {id}
        '''.format(taxonomy=obj.taxonomy_id, id=obj.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def get_highest_spending_department(self, obj):
        query = '''
          WITH all_department_expenditures AS (
            SELECT
              SUM(COALESCE(salary.amount, 0) + COALESCE(salary.extra_pay, 0)) AS dept_budget,
              employer.id as dept_id
            FROM payroll_salary AS salary
            JOIN payroll_job AS job
            ON salary.job_id = job.id
            JOIN payroll_position AS positions
            ON job.position_id = positions.id
            JOIN payroll_employer AS employer
            ON positions.employer_id = employer.id
            GROUP BY employer.id
          ),
          parent_department_expenditures AS (
            SELECT
              *
            FROM all_department_expenditures as ade
            JOIN payroll_employer AS employer
            ON ade.dept_id = employer.id
            WHERE employer.parent_id = {id}
          )
          SELECT
            employer.name,
            dept_budget,
            employer.slug
          FROM parent_department_expenditures
          JOIN payroll_employer as employer
          ON parent_department_expenditures.dept_id = employer.id
          ORDER BY dept_budget DESC
          LIMIT 1
        '''.format(id=obj.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        if result is None:
            name, amount, slug = ['N/A'] * 3

        else:
            name, amount, slug = result

        highest_spending_department = {
            'name': name,
            'amount': amount,
            'slug': slug,
        }

        return highest_spending_department

    def get_composition_json(self, obj):
        pass


# /v1/departments/SLUG/YEAR
class DepartmentSerializer(EmployerSerializer):

    class Meta:
        model = Department
        fields = '__all__'

    percent_of_total_expenditure = serializers.SerializerMethodField()

    def get_percent_of_total_expenditure(self, obj):
        pass


# /v1/people/SLUG/YEAR
class PersonSerializer(serializers.ModelSerializer):

    current_job = serializers.SerializerMethodField()
    all_jobs = serializers.SerializerMethodField()
    current_salary = serializers.SerializerMethodField()
    current_employer = serializers.SerializerMethodField()
    employer_type = serializers.SerializerMethodField()
    employer_salary_json = serializers.SerializerMethodField()
    employer_percentile = serializers.SerializerMethodField()
    like_employer_percentile = serializers.SerializerMethodField()
    salaries = serializers.SerializerMethodField()
    source_link = serializers.SerializerMethodField()
    noindex = serializers.SerializerMethodField()

    def get_current_job(self, obj):
        pass

    def get_all_jobs(self, obj):
        pass

    def get_current_salary(self, obj):
        pass

    def get_current_employer(self, obj):
        pass

    def get_employer_type(self, obj):
        pass

    def get_employer_salary_json(self, obj):
        pass

    def get_employer_percentile(self, obj):
        pass

    def get_like_employer_percentile(self, obj):
        pass

    def get_salaries(self, obj):
        pass

    def get_source_link(self, obj):
        pass

    def get_noindex(self, obj):
        pass
