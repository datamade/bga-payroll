from itertools import chain
import json

from django.contrib.postgres.search import SearchVector
from django.db import connection
from django.db.models import Q, Sum, FloatField
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from postgres_stats.aggregates import Percentile

import numpy as np

from payroll.models import Employer, Job, Person, Salary
from payroll.utils import format_ballpark_number


def index(request):
    return render(request, 'index.html')


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


def person(request, slug):
    try:
        person = Person.objects.get(slug=slug)

    except Employer.DoesNotExist:
        error_page = reverse(error, kwargs={'error_code': 404})
        return redirect(error_page)

    return render(request, 'person.html', {
        'entity': person,
    })


class EmployerView(DetailView):
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

        employee_salaries = self.employee_salaries()
        binned_employee_salaries = self.bin_salary_data(employee_salaries)

        context.update({
            'jobs': Job.of_employer(self.object.id, n=5),
            'median_salary': self.median_entity_salary(),
            'headcount': len(employee_salaries),
            'total_expenditure': sum(employee_salaries),
            'salary_percentile': self.salary_percentile(),
            'expenditure_percentile': self.expenditure_percentile(),
            'employee_salary_json': json.dumps(binned_employee_salaries),
        })
        return context

    def median_entity_salary(self):
        q = Salary.objects.filter(Q(job__position__employer__parent=self.object) | Q(job__position__employer=self.object))

        results = q.all().aggregate(median=Percentile('amount', 0.5, output_field=FloatField()))

        return results['median']

    def employee_salaries(self):
        query = '''
            SELECT
              salary.amount
            {from_clause}
            WHERE employer.id = {id}
            OR employer.parent_id = {id}
        '''.format(from_clause=self.from_clause,
                   id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)

            employee_salaries = [row[0] for row in cursor]

        return employee_salaries

    def bin_salary_data(self, data):
        float_data = np.asarray(data, dtype='float')
        values, edges = np.histogram(float_data, bins=6)

        salary_json = []

        for i, value in enumerate(values):
            lower, upper = int(edges[i]), int(edges[i + 1])

            salary_json.append({
                'value': int(value),
                'lower_edge': format_ballpark_number(lower),
                'upper_edge': format_ballpark_number(upper),
            })

        return salary_json


class UnitView(EmployerView):
    template_name = 'unit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department_statistics = self.aggregate_department_statistics()
        department_salaries = [d['amount'] for d in department_statistics]
        binned_department_salaries = self.bin_salary_data(department_salaries)

        context.update({
            'department_salaries': department_statistics[:5],
            'department_salary_json': json.dumps(binned_department_salaries),
            'population_percentile': self.population_percentile(),
            'highest_spending_department': self.highest_spending_department(),
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
                })

        return department_salaries

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
        department_expenditure = sum(self.employee_salaries())
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


class SearchView(ListView):
    queryset = []
    template_name = 'search_results.html'
    context_object_name = 'results'
    paginate_by = 25

    def get_queryset(self, **kwargs):
        params = {k: v for k, v in self.request.GET.items() if k != 'page'}

        if params.get('entity_type'):
            if params.get('entity_type') == 'person':
                return self._get_person_queryset(params)

            elif params.get('entity_type') == 'employer':
                return self._get_employer_queryset(params)

        else:
            matching_employers = self._get_employer_queryset(params)
            matching_people = self._get_person_queryset(params)

            return list(matching_employers) + list(matching_people)

    def _get_person_queryset(self, params):
        condition = Q()

        if params:
            if params.get('name'):
                name = Q(search_vector=params.get('name'))
                condition &= name

            if params.get('employer'):
                child_employer = Q(jobs__position__employer__slug=params.get('employer'))
                parent_employer = Q(jobs__position__employer__parent__slug=params.get('employer'))
                condition &= child_employer | parent_employer

        return Person.objects.filter(condition)\
                             .order_by('-jobs__salaries__amount')

    def _get_employer_queryset(self, params):
        condition = Q()

        employers = Employer.objects.all()

        if params:
            if params.get('name'):
                employers = employers.annotate(search_vector=SearchVector('name'))
                name = Q(search_vector=params.get('name'))
                condition &= name

            if params.get('employer'):
                name = Q(slug=params.get('employer'))
                condition &= name

            if params.get('parent'):
                parent = Q(parent__slug=params.get('parent'))
                condition &= parent

        return employers.filter(condition)\
                        .select_related('parent')\
                        .annotate(budget=Sum('positions__jobs__salaries__amount'))\
                        .order_by('-budget')


def entity_lookup(request):
    q = request.GET['term']

    top_level = Q(parent_id__isnull=True)
    high_budget = Q(budget__gt=1000000)

    employers = Employer.objects\
                        .annotate(budget=Sum('position__job__salaries__amount'))\
                        .filter(top_level | high_budget)

    people = Person.objects.filter(jobs__salaries__amount__gt=100000)

    if q:
        employers = employers.filter(name__istartswith=q)[:10]

        last_token = q.split(' ')[-1]

        people = people.filter(
            Q(search_vector=q) | Q(last_name__istartswith=last_token)
        )[:10]

    entities = []

    for e in chain(employers, people):
        data = {
            'label': str(e),
            'value': str(e),
        }

        if isinstance(e, Person):
            url = '/person/{slug}'
            category = 'Person'

        else:
            url = '/employer/{slug}'
            category = 'Employer'

        data.update({
            'url': url.format(slug=e.slug),
            'category': category,
        })

        entities.append(data)

    return JsonResponse(entities, safe=False)
