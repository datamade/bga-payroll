import json

from django.db import connection
from django.db.models import Q, FloatField, Prefetch
from django.http import JsonResponse
from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from postgres_stats.aggregates import Percentile

from payroll.charts import ChartHelperMixin
from payroll.models import Employer, Job, Person, Salary, Unit, Department
from payroll.search import PayrollSearchMixin, FacetingMixin


class IndexView(TemplateView, ChartHelperMixin):
    template_name = 'index.html'

    def get_context_data(self):
        context = super().get_context_data()

        salary_count = Salary.objects.all().count()
        unit_count = Unit.objects.all().count()
        department_count = Department.objects.all().count()

        # Note: These try/except blocks can be removed, once we import data into
        # this thing.

        try:
            illinois_slug = Unit.objects.get(name__iexact='Illinois').slug
        except Unit.DoesNotExist:
            illinois_slug = None

        try:
            chicago_slug = Unit.objects.get(name__iexact='Chicago').slug
        except:
            chicago_slug = None

        with connection.cursor() as cursor:
            cursor.execute('SELECT amount FROM payroll_salary')
            all_salaries = [x[0] for x in cursor]

        binned_salaries = self.bin_salary_data(all_salaries)

        context.update({
            'salary_count': salary_count,
            'unit_count': unit_count,
            'department_count': department_count,
            'illinois_slug': illinois_slug,
            'chicago_slug': chicago_slug,
            'salary_json': json.dumps(binned_salaries),
        })

        return context


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


class EmployerView(DetailView, ChartHelperMixin):
    model = Employer
    context_object_name = 'entity'

    # from_clause connects salaries and employers through a series of joins.
    from_clause = '''
        FROM payroll_job AS job
        JOIN payroll_salary AS salary
        ON salary.job_id = job.id
        JOIN payroll_position AS position
        ON job.position_id = position.id
        JOIN payroll_employer as employer
        ON position.employer_id = employer.id
    '''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        employee_salaries = self.object.employee_salaries
        binned_employee_salaries = self.bin_salary_data(employee_salaries)

        context.update({
            'jobs': Job.of_employer(self.object.id, n=5),
            'median_salary': self.median_entity_salary(),
            'headcount': len(employee_salaries),
            'total_expenditure': sum(employee_salaries),
            'salary_percentile': self.salary_percentile(),
            'expenditure_percentile': self.expenditure_percentile(),
            'employee_salary_json': json.dumps(binned_employee_salaries),
            'data_year': 2017,
        })
        return context

    def median_entity_salary(self):
        q = Salary.objects.filter(Q(job__position__employer__parent=self.object) | Q(job__position__employer=self.object))

        results = q.all().aggregate(median=Percentile('amount', 0.5, output_field=FloatField()))

        return results['median']


class UnitView(EmployerView):
    template_name = 'unit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department_statistics = self.aggregate_department_statistics()

        context.update({
            'department_salaries': department_statistics[:5],
            'population_percentile': self.population_percentile(),
            'highest_spending_department': self.highest_spending_department(),
            'composition_json': self.composition_data(),
            'size_class': self.object.size_class,
        })
        return context

    def aggregate_department_statistics(self):
        query = '''
            SELECT
              employer.name,
              AVG(salary.amount) AS average,
              SUM(salary.amount) AS budget,
              COUNT(*) AS headcount,
              employer.slug AS slug
            {from_clause}
            WHERE employer.parent_id = {id}
            GROUP BY employer.id, employer.name
            ORDER BY SUM(salary.amount) DESC
        '''.format(from_clause=self.from_clause,
                   id=self.object.id)

        total_expenditure = sum(self.object.employee_salaries)

        with connection.cursor() as cursor:
            cursor.execute(query)

            department_salaries = []
            for department, average, budget, headcount, slug in cursor:
                department_salaries.append({
                    'department': department,
                    'amount': average,
                    'total_budget': budget,
                    'headcount': headcount,
                    'slug': slug,
                    'percentage': (float(budget / total_expenditure) * 100)  # Percentage of total expenditure
                })

        return department_salaries

    def composition_data(self):
        '''
        Returns the data required to make the composition chart of top spending departments
        '''
        all_departments = self.aggregate_department_statistics()
        top_departments = all_departments[:5]

        composition_json = []
        percentage_tracker = 0

        for i, value in enumerate(top_departments):
            composition_json.append({
                'name': value['department'],
                'data': [value['percentage']],
                'index': i
            })
            percentage_tracker += value['percentage']

        composition_json.append({
            'name': 'All else',
            'data': [100 - percentage_tracker],
            'index': 5

        })

        return composition_json

    def population_percentile(self):
        if (self.object.get_population() is None):
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
        '''.format(taxonomy=self.object.taxonomy_id, id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def expenditure_percentile(self):
        if self.object.is_unclassified:
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
                SUM(salary.amount) AS total_budget,
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
        '''.format(taxonomy=self.object.taxonomy.id,
                   id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def salary_percentile(self):
        if self.object.is_unclassified:
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
                percentile_cont(0.5) WITHIN GROUP (ORDER BY salary.amount ASC) AS median_salary,
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
            '''.format(taxonomy=self.object.taxonomy.id,
                       id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def highest_spending_department(self):
        query = '''
          WITH all_department_expenditures AS (
            SELECT
              SUM(salary.amount) AS dept_budget,
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
            dept_budget
          FROM parent_department_expenditures
          JOIN payroll_employer as employer
          ON parent_department_expenditures.dept_id = employer.id
          ORDER BY dept_budget DESC
          LIMIT 1
        '''.format(id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        if result is None:
            name = 'N/A'
            amount = 'N/A'
        else:
            name = result[0]
            amount = result[1]

        highest_spending_department = {
            'name': name,
            'amount': amount
        }
        return highest_spending_department


class DepartmentView(EmployerView):
    template_name = 'department.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department_expenditure = sum(self.object.employee_salaries)
        parent_expediture = self.total_parent_expenditure()
        percentage = department_expenditure / parent_expediture
        context.update({
            'percent_of_total_expenditure': percentage * 100,  # MIGHT NEED TO HANDLE EXCEPTIONS
        })
        return context

    def total_parent_expenditure(self):
        query = '''
          SELECT
            sum(salary.amount)
          FROM payroll_job AS job
          JOIN payroll_salary AS salary
          ON salary.job_id = job.id
          JOIN payroll_position AS position
          ON job.position_id = position.id
          JOIN payroll_employer as employer
          ON position.employer_id = employer.id
          WHERE employer.parent_id = {parent_id}
        '''.format(parent_id=self.object.parent_id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0]

    def expenditure_percentile(self):
        if self.object.is_unclassified or self.object.parent.is_unclassified:
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
                SUM(salary.amount) AS total_budget,
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
        '''.format(taxonomy=self.object.parent.taxonomy.id,
                   universe=self.object.universe.id,
                   id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def salary_percentile(self):
        if self.object.is_unclassified or self.object.parent.is_unclassified:
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
                percentile_cont(0.5) WITHIN GROUP (ORDER BY salary.amount ASC) AS median_salary,
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
            '''.format(taxonomy=self.object.parent.taxonomy.id,
                       universe=self.object.universe.id,
                       id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100


class PersonView(DetailView, ChartHelperMixin):
    model = Person
    context_object_name = 'entity'
    template_name = 'person.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        all_jobs = self.object.jobs.all()
        current_job = self.object.most_recent_job
        current_salary = current_job.salaries.get()

        salary_prefetch = Prefetch('salaries', to_attr='salary')

        fellow_job_holders = Job.objects.filter(position=current_job.position)\
                                        .exclude(person=self.object)\
                                        .select_related('person', 'position')\
                                        .prefetch_related(salary_prefetch)\
                                        .order_by('-salaries__amount')

        employer_percentile = current_salary.employer_percentile
        like_employer_percentile = current_salary.like_employer_percentile

        current_employer = current_job.position.employer

        if not current_employer.is_unclassified:
            if current_employer.is_department:
                employer_type = '{0} {1}'.format(current_employer.parent.taxonomy,
                                                 current_employer.universe)

            else:
                employer_type = current_employer.taxonomy

        else:
            employer_type = None

        salary_amount = current_salary.amount

        salary_data = current_job.position.employer.employee_salaries
        binned_salary_data = self.bin_salary_data(salary_data)

        # Add colors to the binned data, so the bin in which the person falls
        # is highlighted.
        for salary_range in binned_salary_data:
            lower = int(salary_range['lower_edge'].rstrip('k')) * 1000
            upper = int(salary_range['upper_edge'].rstrip('k')) * 1000

            if lower < salary_amount < upper:
                salary_range['color'] = '#007aff'
            else:
                salary_range['color'] = '#6c757c'

        context.update({
            'data_year': 2017,
            'current_job': current_job,
            'all_jobs': all_jobs,
            'current_salary': salary_amount,
            'current_employer': current_employer,
            'employer_type': employer_type,
            'employer_salary_json': json.dumps(binned_salary_data),
            'employer_percentile': employer_percentile,
            'like_employer_percentile': like_employer_percentile,
            'fellow_job_holders': fellow_job_holders,
        })

        return context


class SearchView(ListView, PayrollSearchMixin, FacetingMixin):
    queryset = []
    template_name = 'search_results.html'
    context_object_name = 'results'
    paginate_by = 25

    def get_queryset(self, **kwargs):
        params = {k: v for k, v in self.request.GET.items() if k != 'page'}

        return list(self.search(params))

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        facets = self.parse_facets(self.facets)

        context['facets'] = facets

        return context


class EntityLookup(ListView, PayrollSearchMixin):
    def get_queryset(self, *args, **kwargs):
        params = {
            'entity_type': 'unit,person',
            'name': self.request.GET['term'],
        }

        extra_search_kwargs = {
            'expenditure_d': '[1000000 TO *]',
            'salary_d': '[100000 TO *]',
            'rows': '10',
        }

        entities = []

        for result in self.search(params, extra_search_kwargs):
            data = {
                'label': str(result),
                'value': str(result),
            }

            url = '{0}/{1}'.format(result.endpoint, result.slug)
            category = result.__class__.__name__

            data.update({
                'url': url,
                'category': category,
            })

            entities.append(data)

        return entities

    def render_to_response(self, *args, **kwargs):
        results = self.get_queryset(*args, **kwargs)

        return JsonResponse(results, safe=False)
