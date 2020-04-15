from django.conf import settings
from django.db import connection
from django.db.models import Q, FloatField, Sum, Count
from django.db.models.functions import Coalesce, NullIf
from postgres_stats.aggregates import Percentile
from rest_framework import serializers

from payroll.models import Employer, Unit, Department, Salary, Person
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
    def employer_salaries(self):
        if not hasattr(self, '_salaries'):
            self._salaries = self.instance.get_salaries()
        return self._salaries

    @property
    def employer_median_salaries(self):
        if not hasattr(self, '_employer_median_salaries'):
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

            self._employer_median_salaries = self.employer_queryset.aggregate(
                median_base_pay=median_base_pay,
                median_extra_pay=median_extra_pay,
                median_total_pay=median_total_pay
            )

        return self._employer_median_salaries

    @property
    def employer_payroll(self):
        if not hasattr(self, '_employer_payroll'):
            entity_base_pay = Sum(Coalesce('positions__jobs__salaries__amount', 0))
            entity_extra_pay = Sum(Coalesce('positions__jobs__salaries__extra_pay', 0))

            self._employer_payroll = self.employer_queryset.aggregate(
                base_pay=entity_base_pay,
                extra_pay=entity_extra_pay
            )

        return self._employer_payroll

    def get_salaries(self, obj):
        data = []

        for salary in self.employer_salaries[:5]:
            data.append({
                'name': str(salary.job.person),
                'slug': salary.job.person.slug,
                'position': salary.job.position.title,
                'employer': salary.job.position.employer.name,
                'employer_slug': salary.job.position.employer.slug,
                'amount': salary.amount,
                'extra_pay': salary.extra_pay,
                'start_date': salary.job.start_date,
            })

        return data

    def get_median_tp(self, obj):
        return self.employer_median_salaries['median_total_pay']

    def get_median_bp(self, obj):
        return self.employer_median_salaries['median_base_pay']

    def get_median_ep(self, obj):
        return self.employer_median_salaries['median_extra_pay']

    def get_headcount(self, obj):
        return self.employer_salaries.count()

    def get_total_expenditure(self, obj):
        return self.employer_payroll['base_pay'] + self.employer_payroll['extra_pay']

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
            employer_median_salaries_by_unit AS (
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
              FROM employer_median_salaries_by_unit
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
        return self.bin_salary_data(
            list(s['total_pay'] for s in self.employer_salaries.values('total_pay'))
        )

    def get_source_link(self, obj):
        source_file = obj.source_file(self.context['data_year'])

        if source_file:
            return source_file.url

    def get_payroll_expenditure(self, obj):
        return {
            'container': 'payroll-expenditure-chart',
            'total_pay': self.employer_payroll['base_pay'] + self.employer_payroll['extra_pay'],
            'series_data': {
                'Name': 'Data',
                'data': [{
                    'name': 'Reported Base Pay',
                    'y': self.employer_payroll['base_pay'],
                    'label': 'base_pay',
                }, {
                    'name': 'Reported Extra Pay',
                    'y': self.employer_payroll['extra_pay'],
                    'label': 'extra_pay',
                }],
            },
        }


# /v1/units/SLUG/YEAR
class UnitSerializer(EmployerSerializer):

    class Meta:
        model = Unit
        fields = '__all__'

    department_salaries = serializers.SerializerMethodField()
    population_percentile = serializers.SerializerMethodField()
    highest_spending_department = serializers.SerializerMethodField()
    composition_json = serializers.SerializerMethodField()

    @property
    def department_statistics(self):
        if not hasattr(self, '_department_statistics'):
            entity_base_pay = Sum(Coalesce('positions__jobs__salaries__amount', 0))
            entity_extra_pay = Sum(Coalesce('positions__jobs__salaries__extra_pay', 0))
            median_total_pay = Percentile(
                (
                    NullIf(
                        Coalesce('positions__jobs__salaries__amount', 0) +
                        Coalesce('positions__jobs__salaries__extra_pay', 0), 0
                    )
                ), 0.5, output_field=FloatField()
            )
            headcount = Count('positions__jobs__salaries')

            self._department_statistics = Employer.objects.filter(parent=self.instance)\
                                                          .values('name', 'slug')\
                                                          .annotate(headcount=headcount,
                                                                    median_tp=median_total_pay,
                                                                    entity_bp=entity_base_pay,
                                                                    entity_ep=entity_extra_pay,
                                                                    total_expenditure=entity_base_pay + entity_extra_pay)\
                                                          .order_by('-total_expenditure')

        return self._department_statistics

    def get_department_salaries(self, obj):
        return self.department_statistics[:5]

    def get_highest_spending_department(self, obj):
        try:
            top_department = self.department_statistics[0]
        except IndexError:
            return None
        else:
            return {
                'name': top_department['name'],
                'amount': top_department['total_expenditure'],
                'slug': top_department['slug'],
            }

    def get_composition_json(self, obj):
        top_departments = self.department_statistics[:5]

        composition_json = []
        percentage_tracker = 0

        budget = self.employer_payroll['base_pay'] + self.employer_payroll['extra_pay']

        for i, value in enumerate(top_departments):
            proportion = (value['total_expenditure'] / budget) * 100
            composition_json.append({
                'name': value['name'],
                'data': [proportion],
                'index': i
            })
            percentage_tracker += proportion

        composition_json.append({
            'name': 'All else',
            'data': [100 - percentage_tracker],
            'index': 5

        })

        return composition_json

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


# /v1/departments/SLUG/YEAR
class DepartmentSerializer(EmployerSerializer):

    class Meta:
        model = Department
        fields = '__all__'

    percent_of_total_expenditure = serializers.SerializerMethodField()

    def get_percent_of_total_expenditure(self, obj):
        department_expenditure = sum(self.instance.employee_salaries)
        parent_expediture = sum(self.instance.parent.employee_salaries)

        return department_expenditure / parent_expediture * 100


# /v1/people/SLUG/YEAR
class PersonSerializer(serializers.ModelSerializer, ChartHelperMixin):

    class Meta:
        model = Person
        fields = '__all__'

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

    def _get_bar_color(self, lower, upper, **kwargs):
        '''
        Override _get_bar_color from the ChartHelperMixin to highlight the
        salary range to which the person belongs.
        '''
        if lower < int(kwargs['salary_amount']) <= upper:
            return settings.BAR_HIGHLIGHT
        else:
            return super()._get_bar_color(lower, upper)

    @property
    def person_current_job(self):
        if not hasattr(self, '_current_job'):
            self._current_job = self.instance.most_recent_job
        return self._current_job

    @property
    def person_current_salary(self):
        if not hasattr(self, '_current_salary'):
            self._current_salary = self.person_current_job.salaries.get()
        return self._current_salary

    @property
    def person_current_employer(self):
        if not hasattr(self, '_current_employer'):
            self._current_employer = self.person_current_job.position.employer
        return self._current_employer

    def get_current_job(self, obj):
        '''
        TODO: Consider caching current_jobs with an S, then accessing the most
        recent one here.
        '''
        return {
            'title': self.person_current_job.position.title,
            'start_date': self.person_current_job.start_date,
        }

    def get_all_jobs(self, obj):
        data = []

        for salary in Salary.objects.with_related_objects()\
                                    .filter(job__person=obj)\
                                    .order_by('-vintage__standardized_file__reporting_year'):

            data.append({
                'name': str(salary.job.person),
                'slug': salary.job.person.slug,
                'position': salary.job.position.title,
                'employer': salary.job.position.employer.name,
                'employer_slug': salary.job.position.employer.slug,
                'amount': salary.amount,
                'extra_pay': salary.extra_pay,
                'start_date': salary.job.start_date,
            })

        return data

    def get_current_salary(self, obj):
        return self.person_current_salary.total_pay

    def get_current_employer(self, obj):
        return {
            'endoint': self.person_current_employer.endpoint,
            'slug': self.person_current_employer.slug,
            'name': self.person_current_employer.name,
        }

    def get_employer_type(self, obj):
        if self.person_current_employer.is_unclassified:
            return None
        elif self.person_current_employer.is_department:
            return [str(self.person_current_employer.universe), str(self.person_current_employer.parent.taxonomy)]
        else:
            return [str(self.person_current_employer.taxonomy)]

    def get_employer_salary_json(self, obj):
        return self.bin_salary_data(
            list(s['total_pay'] for s in self.person_current_employer.get_salaries().values('total_pay')),
            salary_amount=self.person_current_salary.total_pay
        )

    def get_employer_percentile(self, obj):
        return self.person_current_salary.employer_percentile

    def get_like_employer_percentile(self, obj):
        return self.person_current_salary.like_employer_percentile

    def get_salaries(self, obj):
        data = []

        for salary in Salary.objects.with_related_objects()\
                                    .filter(job__position=self.person_current_job.position)\
                                    .exclude(job__person=obj)\
                                    .order_by('-total_pay'):

            data.append({
                'name': str(salary.job.person),
                'slug': salary.job.person.slug,
                'position': salary.job.position.title,
                'employer': salary.job.position.employer.name,
                'employer_slug': salary.job.position.employer.slug,
                'amount': salary.amount,
                'extra_pay': salary.extra_pay,
                'start_date': salary.job.start_date,
            })

        return data

    def get_source_link(self, obj):
        source_file = obj.source_file(self.context['data_year'])

        if source_file:
            return source_file.url

    def get_noindex(self, obj):
        return self.person_current_salary.amount < 30000 or obj.noindex
