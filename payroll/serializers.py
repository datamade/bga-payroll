from django.conf import settings
from django.db import connection
from django.db.models import Q, FloatField, Sum, Max
from django.db.models.functions import Coalesce, NullIf
from postgres_stats.aggregates import Percentile
from rest_framework import serializers

from payroll.models import Employer, Unit, Department, Salary, Person
from payroll.charts import ChartHelperMixin
from payroll.utils import format_exact_number, format_ballpark_number, \
    format_salary, format_percentile


# /v1/index/YEAR
class IndexSerializer(serializers.Serializer, ChartHelperMixin):

    salary_count = serializers.SerializerMethodField()
    unit_count = serializers.SerializerMethodField()
    salary_json = serializers.SerializerMethodField()

    def get_salary_count(self, data_year):
        count = Salary.objects.filter(vintage__standardized_file__reporting_year=data_year).count()
        return format_exact_number(count)

    def get_unit_count(self, data_year):
        count = Unit.objects.filter(responding_agencies__reporting_year=2018).count()
        return format_exact_number(count)

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
    def salary_q(self):
        return Q(positions__jobs__salaries__vintage__standardized_file__reporting_year=self.context['data_year'])

    @property
    def employer_queryset(self):
        return Employer.objects.filter(
            Q(id=self.instance.id) | Q(parent_id=self.instance.id)
        )

    @property
    def employer_salaries(self):
        if not hasattr(self, '_salaries'):
            self._employer_salaries = self.instance.get_salaries(year=self.context['data_year'])
        return self._employer_salaries

    @property
    def employer_salary_count(self):
        if not hasattr(self, '_employer_salary_count'):
            self._employer_salary_count = self._employer_salaries.count()
        return self._employer_salary_count

    @property
    def employer_median_salaries(self):
        if not hasattr(self, '_employer_median_salaries'):
            median_base_pay = Percentile(
                'positions__jobs__salaries__amount',
                0.5,
                filter=self.salary_q,
                output_field=FloatField()
            )
            median_extra_pay = Percentile(
                'positions__jobs__salaries__extra_pay',
                0.5,
                filter=self.salary_q,
                output_field=FloatField()
            )
            median_total_pay = Percentile(
                NullIf(
                    Coalesce('positions__jobs__salaries__amount', 0) +
                    Coalesce('positions__jobs__salaries__extra_pay', 0), 0
                ),
                0.5,
                filter=self.salary_q,
                output_field=FloatField()
            )

            self._employer_median_salaries = self.employer_queryset.aggregate(
                median_base_pay=Coalesce(median_base_pay, 0),
                median_extra_pay=Coalesce(median_extra_pay, 0),
                median_total_pay=Coalesce(median_total_pay, 0)
            )

        return self._employer_median_salaries

    @property
    def employer_payroll(self):
        if not hasattr(self, '_employer_payroll'):
            entity_base_pay = Sum(
                Coalesce('positions__jobs__salaries__amount', 0),
                filter=self.salary_q
            )
            entity_extra_pay = Sum(
                Coalesce('positions__jobs__salaries__extra_pay', 0),
                filter=self.salary_q
            )

            self._employer_payroll = self.employer_queryset.aggregate(
                base_pay=Coalesce(entity_base_pay, 0),
                extra_pay=Coalesce(entity_extra_pay, 0)
            )

        return self._employer_payroll

    def get_salaries(self, obj):
        data = []

        # Sorting is expensive! Use self.employer_salaries as a subquery so we
        # are only ordering salaries from the given employer and year.
        top_salaries = Salary.objects.filter(
            id__in=self.employer_salaries.values_list('id', flat=True)
        ).order_by('-total_pay')[:5]

        # Only retrieve related objects of the top salaries, to further
        # optimize the query. Repeat the ordering operation for those five
        # salaries to ensure we retain order during display.
        top_salaries_with_related_objects = Salary.objects.with_related_objects().filter(
            id__in=top_salaries.values_list('id', flat=True)
        ).order_by('-total_pay')

        for salary in top_salaries_with_related_objects:
            if salary.amount:
                amount = format_salary(salary.amount)
            else:
                amount = 'Not reported'

            if salary.extra_pay:
                extra_pay = format_salary(salary.extra_pay)
            else:
                extra_pay = 'Not reported'

            data.append({
                'name': str(salary.job.person),
                'slug': salary.job.person.slug,
                'position': salary.job.position.title,
                'employer': salary.job.position.employer.name,
                'employer_endpoint': salary.job.position.employer.endpoint,
                'employer_slug': salary.job.position.employer.slug,
                'amount': amount,
                'extra_pay': extra_pay,
                'start_date': salary.job.start_date,
            })

        return data

    def get_median_tp(self, obj):
        if self.employer_median_salaries['median_total_pay']:
            return format_salary(self.employer_median_salaries['median_total_pay'])
        else:
            return 'Not reported'

    def get_median_bp(self, obj):
        if self.employer_median_salaries['median_base_pay']:
            return format_salary(self.employer_median_salaries['median_base_pay'])
        else:
            return 'Not reported'

    def get_median_ep(self, obj):
        if self.employer_median_salaries['median_extra_pay']:
            return format_salary(self.employer_median_salaries['median_extra_pay'])
        else:
            return 'Not reported'

    def get_headcount(self, obj):
        return format_ballpark_number(self.employer_salary_count)

    def get_total_expenditure(self, obj):
        return format_ballpark_number(self.employer_payroll['base_pay'] + self.employer_payroll['extra_pay'])

    def get_employee_salary_json(self, obj):
        if self.employer_salary_count > 0:
            return self.bin_salary_data(
                list(s['total_pay'] for s in self.employer_salaries.values('total_pay'))
            )
        else:
            return []

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
    highest_spending_department = serializers.SerializerMethodField()
    composition_json = serializers.SerializerMethodField()

    @property
    def department_statistics(self):
        if not hasattr(self, '_department_statistics'):
            # Combining annotations doesn't work! :scream_cat:
            # https://docs.djangoproject.com/en/3.0/topics/db/aggregation/#combining-multiple-aggregations
            #
            # Instead, use the raw manager to generate a queryset with the
            # needed annotations. https://docs.djangoproject.com/en/3.0/topics/db/sql/#performing-raw-queries
            aggregate_query = '''
                WITH department_salaries AS (
                  SELECT
                    employer.id,
                    employer.name,
                    employer.slug,
                    salary.amount,
                    salary.extra_pay
                  FROM payroll_salary AS salary
                  JOIN payroll_job AS job
                  ON salary.job_id = job.id
                  JOIN payroll_position AS position
                  ON position.id = job.position_id
                  JOIN payroll_employer AS employer
                  ON position.employer_id = employer.id
                  JOIN data_import_upload AS vintage
                  ON salary.vintage_id = vintage.id
                  JOIN data_import_standardizedfile AS s_file
                  ON s_file.upload_id = vintage.id
                  WHERE employer.parent_id = {parent_id}
                  AND s_file.reporting_year = {reporting_year}
                )
                SELECT
                  id,
                  name,
                  slug,
                  SUM(COALESCE(amount, 0)) AS entity_bp,
                  SUM(COALESCE(extra_pay, 0)) AS entity_ep,
                  SUM(COALESCE(amount, 0)) + SUM(COALESCE(extra_pay, 0)) AS total_expenditure,
                  percentile_cont(0.5) within GROUP (
                    ORDER BY
                      NULLIF((COALESCE(amount, 0) + COALESCE(extra_pay, 0)), 0)
                  ) AS median_tp,
                  COUNT(*) AS headcount
                FROM department_salaries
                GROUP BY id, name, slug
                ORDER BY total_expenditure DESC
            '''.format(parent_id=self.instance.id,
                       reporting_year=self.context['data_year'])

            self._department_statistics = Employer.objects.raw(aggregate_query)

        return self._department_statistics

    def get_salary_percentile(self, obj):
        if obj.is_unclassified or self.employer_salary_count == 0:
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
              JOIN data_import_upload AS vintage
              ON salary.vintage_id = vintage.id
              JOIN data_import_standardizedfile AS s_file
              ON vintage.id = s_file.upload_id
              WHERE employer.taxonomy_id = {taxonomy}
              AND s_file.reporting_year = {reporting_year}
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
                       reporting_year=self.context['data_year'],
                       id=obj.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return format_percentile(result[0] * 100)

    def get_expenditure_percentile(self, obj):
        if obj.is_unclassified or self.employer_salary_count == 0:
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
              JOIN data_import_upload AS vintage
              ON salary.vintage_id = vintage.id
              JOIN data_import_standardizedfile AS s_file
              ON vintage.id = s_file.upload_id
              WHERE employer.taxonomy_id = {taxonomy}
              AND s_file.reporting_year = {reporting_year}
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
                   reporting_year=self.context['data_year'],
                   id=obj.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return format_percentile(result[0] * 100)

    def get_department_salaries(self, obj):
        formatted_salaries = []

        for salary in self.department_statistics[:5]:
            formatted_salaries.append({
                'name': salary.name,
                'slug': salary.slug,
                'headcount': format_exact_number(salary.headcount),
                'median_tp': format_salary(salary.median_tp),
                'entity_bp': format_ballpark_number(salary.entity_bp),
                'entity_ep': format_ballpark_number(salary.entity_ep),
                'total_expenditure': format_ballpark_number(salary.total_expenditure),
            })

        return formatted_salaries

    def get_highest_spending_department(self, obj):
        try:
            top_department = self.department_statistics[0]
        except IndexError:
            return None
        else:
            return {
                'name': top_department.name,
                'amount': format_salary(top_department.total_expenditure),
                'slug': top_department.slug,
            }

    def get_composition_json(self, obj):
        top_departments = self.department_statistics[:5]

        composition_json = []
        percentage_tracker = 0

        budget = self.employer_payroll['base_pay'] + self.employer_payroll['extra_pay']

        for i, value in enumerate(top_departments):
            proportion = (value.total_expenditure / budget) * 100
            composition_json.append({
                'name': value.name,
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


# /v1/departments/SLUG/YEAR
class DepartmentSerializer(EmployerSerializer):

    class Meta:
        model = Department
        fields = '__all__'

    percent_of_total_expenditure = serializers.SerializerMethodField()

    def get_percent_of_total_expenditure(self, obj):
        department_salaries = self.employer_salaries.values_list('total_pay', flat=True)

        unit_salaries = self.instance.parent.get_salaries(year=self.context['data_year'])\
                                            .values_list('total_pay', flat=True)

        return format_percentile(sum(department_salaries) / sum(unit_salaries) * 100)

    def get_expenditure_percentile(self, obj):
        if obj.is_unclassified or obj.parent.is_unclassified:
            return 'N/A'

        query = '''
            WITH taxonomy_members AS (
              SELECT
                department.id,
                department.universe_id
              FROM payroll_employer AS unit
              JOIN payroll_employer AS department
              ON unit.id = department.parent_id
              WHERE unit.taxonomy_id = {taxonomy}
            ),
            expenditure_by_department AS (
              SELECT
                SUM(COALESCE(salary.amount, 0) + COALESCE(salary.extra_pay, 0)) AS total_budget,
                department.id AS department_id
              FROM payroll_salary AS salary
              JOIN payroll_job AS job
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN taxonomy_members AS department
              ON position.employer_id = department.id
              WHERE department.universe_id = {universe}
              GROUP BY department.id
            ),
            exp_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY total_budget ASC) AS percentile,
                department_id
              FROM expenditure_by_department
            )
            SELECT
              percentile
            FROM exp_percentiles
            WHERE department_id = {id}
        '''.format(taxonomy=obj.parent.taxonomy.id,
                   universe=obj.universe.id,
                   id=obj.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return format_percentile(result[0] * 100)

    def get_salary_percentile(self, obj):
        if obj.is_unclassified or obj.parent.is_unclassified:
            return 'N/A'

        query = '''
            WITH taxonomy_members AS (
              SELECT
                department.id,
                department.universe_id
              FROM payroll_employer AS unit
              JOIN payroll_employer AS department
              ON unit.id = department.parent_id
              WHERE unit.taxonomy_id = {taxonomy}
            ),
            median_salaries_by_department AS (
              SELECT
                percentile_cont(0.5) WITHIN GROUP (
                  ORDER BY COALESCE(salary.amount, 0) + COALESCE(salary.extra_pay, 0) ASC
                ) AS median_salary,
                department.id AS department_id
              FROM payroll_salary AS salary
              JOIN payroll_job AS job
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN taxonomy_members AS department
              ON position.employer_id = department.id
              WHERE department.universe_id = {universe}
              GROUP BY department.id
            ),
            salary_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY median_salary ASC) AS percentile,
                department_id
              FROM median_salaries_by_department
            )
            SELECT percentile
            FROM salary_percentiles
            WHERE department_id = {id}
            '''.format(taxonomy=obj.parent.taxonomy.id,
                       universe=obj.universe.id,
                       id=obj.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return format_percentile(result[0] * 100)


# /v1/people/SLUG/YEAR
class PersonSerializer(serializers.ModelSerializer, ChartHelperMixin):

    class Meta:
        model = Person
        fields = '__all__'

    current_job = serializers.SerializerMethodField()
    all_jobs = serializers.SerializerMethodField()
    current_salary = serializers.SerializerMethodField()
    change_in_salary = serializers.SerializerMethodField()
    current_employer = serializers.SerializerMethodField()
    employer_type = serializers.SerializerMethodField()
    employer_salary_json = serializers.SerializerMethodField()
    employee_salary_json = serializers.SerializerMethodField()
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
            employer = self.person_current_job.position.employer
            self._current_employer = (Department.objects.get(id=employer.id)
                                      if employer.is_department
                                      else Unit.objects.get(id=employer.id))
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
                                    .annotate(data_year=Max('vintage__standardized_file__reporting_year'))\
                                    .order_by('-vintage__standardized_file__reporting_year'):

            data.append({
                'position': salary.job.position.title,
                'employer': salary.job.position.employer.name,
                'employer_slug': salary.job.position.employer.slug,
                'amount': salary.amount,
                'extra_pay': salary.extra_pay,
                'start_date': salary.job.start_date,
                'data_year': salary.data_year,
            })

        return data

    def get_current_salary(self, obj):
        return self.person_current_salary.total_pay

    def get_current_employer(self, obj):
        employer = {
            'endpoint': self.person_current_employer.endpoint,
            'slug': self.person_current_employer.slug,
            'name': self.person_current_employer.name,
            'is_comparable': self.person_current_employer.is_comparable,
        }

        if self.person_current_employer.parent:
            parent = {
                'endpoint': self.person_current_employer.parent.endpoint,
                'slug': self.person_current_employer.parent.slug,
                'name': self.person_current_employer.parent.name,
            }

            employer['parent'] = parent

        return employer

    def get_employer_type(self, obj):
        if self.person_current_employer.is_unclassified:
            return None
        elif self.person_current_employer.is_department:
            return [str(self.person_current_employer.universe), str(self.person_current_employer.parent.taxonomy)]
        else:
            return [str(self.person_current_employer.taxonomy)]

    def get_employer_salary_json(self, obj):
        return self.bin_salary_data(
            self.person_current_employer.get_salaries(self.context['data_year'])
                                        .values_list('total_pay', flat=True),
            salary_amount=self.person_current_salary.total_pay
        )

    def get_employer_percentile(self, obj):
        return self.person_current_salary.employer_percentile

    def get_like_employer_percentile(self, obj):
        return self.person_current_salary.like_employer_percentile

    def get_salaries(self, obj):
        data = []

        for salary in Salary.objects.with_related_objects()\
                                    .filter(job__position=self.person_current_job.position, vintage__standardized_file__reporting_year=self.context['data_year'])\
                                    .exclude(job__person=obj)\
                                    .order_by('-total_pay')[:25]:

            data.append({
                'name': str(salary.job.person),
                'slug': salary.job.person.slug,
                'position': salary.job.position.title,
                'total_pay': salary.total_pay,
                'start_date': salary.job.start_date,
            })

        return data

    def get_source_link(self, obj):
        source_file = obj.source_file(self.context['data_year'])

        if source_file:
            return source_file.url

    def get_noindex(self, obj):
        return self.person_current_salary.amount < 30000 or obj.noindex

    def get_employee_salary_json(self, obj):
        base_pay = {
          'name': 'Base Pay',
          'data': []
        }
        extra_pay = {
          'name': 'Extra Pay',
          'data': []
        }

        for salary in Salary.objects.with_related_objects()\
                                    .filter(job__person=obj)\
                                    .annotate(data_year=Max('vintage__standardized_file__reporting_year'))\
                                    .order_by('vintage__standardized_file__reporting_year'):

            base_pay['data'].append({
                'name': str(salary.data_year),
                'y': float(salary.amount or 0),
            })

            extra_pay['data'].append({
                'name': str(salary.data_year),
                'y': float(salary.extra_pay or 0),
            })

        return [extra_pay, base_pay]

    def get_change_in_salary(self, obj):
        '''
        Salaries must have either base or extra pay, but are not required to
        have both. For that reason, total pay is never null. However, base or
        extra pay can be.

        Calculate the overall delta from the earliest and latest salaries.
        Calculate the base and extra pay deltas from the earliest salaries that
        have a value for each of them, respectively, and the latest salary,
        if the latest salary has a value.
        '''
        current_salary = self.person_current_salary

        ordered_salaries = list(Salary.objects.filter(job__person=obj)
                                              .order_by('vintage__standardized_file__reporting_year'))

        first_salary = ordered_salaries[0]

        change = {
            'total_pay_delta': current_salary.total_pay - first_salary.total_pay,
            'total_pay_percent_change': (current_salary.total_pay - first_salary.total_pay) / first_salary.total_pay,
        }

        salaries_with_amount = list(filter(lambda x: x.amount is not None, ordered_salaries))

        if len(salaries_with_amount) and salaries_with_amount[0] != current_salary and current_salary.amount:
            earliest_amount = salaries_with_amount[0].amount
            latest_amount = current_salary.amount

            change.update({
                'amount_delta': latest_amount - earliest_amount,
                'amount_percent_change': (latest_amount - earliest_amount) / earliest_amount,
            })

        salaries_with_extra_pay = list(filter(lambda x: x.extra_pay is not None, ordered_salaries))

        if len(salaries_with_extra_pay) and salaries_with_extra_pay[0] != current_salary and current_salary.extra_pay:
            earliest_amount = salaries_with_extra_pay[0].extra_pay
            latest_amount = current_salary.extra_pay

            change.update({
                'extra_pay_delta': latest_amount - earliest_amount,
                'extra_pay_percent_change': (latest_amount - earliest_amount) / earliest_amount,
            })

        return change
