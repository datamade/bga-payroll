from itertools import chain
import json

from django.db import connection
from django.db.models import Avg, Q, Sum
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse

import numpy as np

from payroll.models import Employer, Salary, Person
from payroll.utils import format_ballpark_number


def index(request):
    return render(request, 'index.html')


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


def employer(request, slug):
    try:
        entity = Employer.objects.get(slug=slug)

    except Employer.DoesNotExist:
        error_page = reverse(error, kwargs={'error_code': 404})
        return redirect(error_page)

    if entity.is_department or not entity.departments.all():
        context = get_department_context(entity)
        return render(request, 'department.html', context)

    else:
        context = get_unit_context(entity)
        return render(request, 'governmental_unit.html', context)


def person(request, slug):
    try:
        person = Person.objects.prefetch_related('salaries').get(slug=slug)

    except Employer.DoesNotExist:
        error_page = reverse(error, kwargs={'error_code': 404})
        return redirect(error_page)

    return render(request, 'person.html', {
        'entity': person,
    })


def get_unit_context(unit):
    person_salaries = Salary.of_employer(unit.id)[:5]

    department_salaries = []

    with connection.cursor() as cursor:
        query = '''
            SELECT
                e.name,
                AVG(s.amount) AS average,
                SUM(s.amount) AS budget,
                COUNT(*) AS headcount,
                e.slug AS slug
            FROM payroll_salary AS s
            JOIN payroll_position AS p
            ON s.position_id = p.id
            JOIN payroll_employer AS e
            ON p.employer_id = e.id
            WHERE e.parent_id = {id}
            OR e.id = {id}
            GROUP BY e.id, e.name
            ORDER BY SUM(s.amount) DESC
        '''.format(id=unit.id)

        cursor.execute(query)

        for department, average, budget, headcount, slug in cursor:
            department_salaries.append({
                'department': department.title(),
                'amount': round(average, 2),
                'total_budget': budget,
                'headcount': headcount,
                'slug': slug,
            })

        query = '''
            SELECT AVG(s.amount) AS average
            FROM payroll_salary AS s
            JOIN payroll_position AS p
            ON s.position_id = p.id
            JOIN payroll_employer AS e
            ON p.employer_id = e.id
            WHERE e.parent_id = {id}
            OR e.id = {id}
        '''.format(id=unit.id)

        cursor.execute(query)

        result, = cursor
        average_salary, = result

    salary_json = bin_salary_data([d['amount'] for d in department_salaries])

    return {
        'entity': unit,
        'salaries': person_salaries,
        'average_salary': average_salary,
        'department_salaries': department_salaries,
        'salary_json': json.dumps(salary_json),
    }


def get_department_context(department):
    person_salaries = Salary.of_employer(department.id)
    average_salary = person_salaries.aggregate(Avg('amount'))['amount__avg']
    salary_json = bin_salary_data([s.amount for s in person_salaries])

    return {
        'entity': department,
        'salaries': person_salaries,
        'average_salary': average_salary,
        'salary_json': json.dumps(salary_json),
    }


def bin_salary_data(data):
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
