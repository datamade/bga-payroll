from itertools import chain
import json

from django.db import connection
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse

from payroll.models import Employer, Salary, Person


def index(request):
    return render(request, 'index.html')


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


def governmental_unit(request, slug):
    try:
        unit = Employer.objects.filter(parent_id__isnull=True).get(slug=slug)

    except Employer.DoesNotExist:
        error_page = reverse(error, kwargs={'error_code': 404})
        return redirect(error_page)

    if not unit.departments:
        department_page = reverse('department', kwargs={'slug': slug})
        return redirect(department_page)

    else:
        person_salaries = Salary.of_employer(unit.id)
        average_salary = person_salaries.aggregate(Avg('amount'))['amount__avg']

        department_salaries = []

        with connection.cursor() as cursor:
            query = '''
                SELECT
                    e.name,
                    AVG(s.amount)
                FROM payroll_salary AS s
                JOIN payroll_position AS p
                ON s.position_id = p.id
                JOIN payroll_employer AS e
                ON p.employer_id = e.id
                WHERE e.parent_id = {id}
                OR e.id = {id}
                GROUP BY e.id, e.name
                ORDER BY AVG(s.amount) DESC
            '''.format(id=unit.id)

            cursor.execute(query)

            for department, average in cursor:
                department_salaries.append({
                    'amount': round(average, 2),
                    'department': department.title(),
                })

    return render(request, 'governmental_unit.html', {
        'entity': unit,
        'salaries': person_salaries,
        'average_salary': average_salary,
        'salary_json': json.dumps(department_salaries),
    })


def department(request, slug):
    try:
        department = Employer.objects.filter(parent_id__isnull=False).get(slug=slug)

    except Employer.DoesNotExist:
        error_page = reverse(error, kwargs={'error_code': 404})
        return redirect(error_page)

    person_salaries = Salary.of_employer(department.id)
    average_salary = person_salaries.aggregate(Avg('amount'))['amount__avg']

    salary_json = []

    for salary in person_salaries:
        salary_json.append({
            'name': str(salary.person).title(),
            'position': str(salary.position).title(),
            'amount': salary.amount,
        })

    return render(request, 'department.html', {
        'entity': department,
        'salaries': person_salaries,
        'average_salary': average_salary,
        'salary_json': json.dumps(salary_json),
    })


def entity_lookup(request):
    q = request.GET['term']

    employers = Employer.objects.all()
    people = Person.objects.all()

    if q:
        employers = employers.filter(name__istartswith=q)[:10]
        people = people.filter(
            Q(first_name__istartswith=q) | Q(last_name__istartswith=q)
        )[:10]

    entities = []

    for e in chain(people, employers):
        data = {'label': str(e)}

        if isinstance(e, Person):
            url = '/person/{}'.format(e.id)

        else:
            if e.parent_id:
                url = '/department/{}'.format(e.slug)
            else:
                url = '/governmental-unit/{}'.format(e.slug)

        data['value'] = url

        entities.append(data)

    return JsonResponse(entities, safe=False)
