from itertools import chain
import json

from django.db import connection
from django.db.models import Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.views import View

import numpy as np

from payroll.models import Employer, Salary, Person
from payroll.utils import format_ballpark_number


def index(request):
    return render(request, 'index.html')


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


def person(request, slug):
    try:
        person = Person.objects.prefetch_related('salaries').get(slug=slug)

    except Employer.DoesNotExist:
        error_page = reverse(error, kwargs={'error_code': 404})
        return redirect(error_page)

    return render(request, 'person.html', {
        'entity': person,
    })


class EmployerView(View):
    from_clause = '''
        FROM payroll_salary AS salary
        JOIN payroll_position AS position
        ON salary.position_id = position.id
        JOIN payroll_employer AS employer
        ON position.employer_id = employer.id
    '''

    def get(self, request, *args, **kwargs):
        slug = self.kwargs['slug']

        try:
            entity = Employer.objects.get(slug=slug)

        except Employer.DoesNotExist:
            error_page = reverse(error, kwargs={'error_code': 404})
            return redirect(error_page)

        self.where_clause = self._make_where_clause(entity)

        employee_salaries = self.employee_salaries()
        binned_employee_salaries = self.bin_salary_data(employee_salaries)

        context = {
            'entity': entity,
            'salaries': Salary.of_employer(entity.id, n=5),
            'mean_salary': self.mean_entity_salary(),
            'headcount': len(employee_salaries),
            'total_expenditure': sum(employee_salaries),
            'employee_salary_json': json.dumps(binned_employee_salaries),
        }

        if not entity.is_department:
            department_statistics = self.aggregate_department_statistics()
            department_salaries = [d['amount'] for d in department_statistics]
            binned_department_salaries = self.bin_salary_data(department_salaries)

            context.update({
                'department_salaries': department_statistics,
                'department_salary_json': json.dumps(binned_department_salaries),
            })

        return render(request, 'employer.html', context)

    def _make_where_clause(self, entity):
        if entity.is_department:
            return '''
                WHERE employer.id = {id}
            '''.format(id=entity.id)

        else:
            return '''
                WHERE employer.id = {id}
                OR employer.parent_id = {id}
            '''.format(id=entity.id)

    def _make_query(self, query_fmt):
        return query_fmt.format(
            from_clause=self.from_clause,
            where_clause=self.where_clause,
        )

    def mean_entity_salary(self):
        query = self._make_query('''
            SELECT
                AVG(salary.amount) AS average
            {from_clause}
            {where_clause}
        ''')

        with connection.cursor() as cursor:
            cursor.execute(query)

            result, = cursor
            mean_salary, = result

        return mean_salary

    def aggregate_department_statistics(self):
        query = self._make_query('''
            SELECT
                employer.name,
                AVG(salary.amount) AS average,
                SUM(salary.amount) AS budget,
                COUNT(*) AS headcount,
                employer.slug AS slug
            {from_clause}
            {where_clause}
            GROUP BY employer.id, employer.name
            ORDER BY SUM(salary.amount) DESC
        ''')

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

    def employee_salaries(self):
        query = self._make_query('''
            SELECT
                salary.amount
            {from_clause}
            {where_clause}
        ''')

        with connection.cursor() as cursor:
            cursor.execute(query)

            employee_salaries = [row[0] for row in cursor]

        return employee_salaries

    def bin_salary_data(self, data):
        values, edges = np.histogram(data, bins=6)

        salary_json = []

        for i, value in enumerate(values):
            lower, upper = int(edges[i]), int(edges[i + 1])

            salary_json.append({
                'value': int(value),
                'lower_edge': format_ballpark_number(lower),
                'upper_edge': format_ballpark_number(upper),
            })

        return salary_json


def entity_lookup(request):
    q = request.GET['term']

    top_level = Q(parent_id__isnull=True)
    high_budget = Q(budget__gt=1000000)

    employers = Employer.objects\
                        .annotate(budget=Sum('position__salary'))\
                        .filter(top_level | high_budget)

    people = Person.objects.filter(salaries__amount__gt=100000)

    if q:
        # Show exacts first
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
