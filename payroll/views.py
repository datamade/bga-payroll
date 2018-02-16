import json

from django.db import connection
from django.db.models import Avg, Q
from django.shortcuts import render, redirect
from django.urls import reverse

from payroll.models import Employer, Salary


def index(request):
    return render(request, 'base.html')


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


def governmental_unit(request, uid=None):
    try:
        unit = Employer.objects.filter(parent_id__isnull=True).get(id=uid)

    except Employer.DoesNotExist:
        error_page = reverse(error, kwargs={'error_code': 404})
        return redirect(error_page)

#            SELECT
#                CONCAT_WS(' ', person.first_name, person.last_name),
#                position.title,
#                salary.amount
#            FROM payroll_salary AS salary
#            JOIN payroll_person_salaries AS ps
#            ON ps.salary_id = salary.id
#            JOIN payroll_person as person
#            ON ps.person_id = person.id
#            JOIN payroll_position AS position
#            ON salary.position_id = position.id
#            JOIN payroll_employer AS employer
#            ON position.employer_id = employer.id
#            WHERE employer.parent_id = {id}
#            OR employer.id = {id}
#            ORDER BY salary.amount

    salaries = Salary.objects.filter(
        Q(position__employer_id=uid) | Q(position__employer__parent_id=uid)
    ).order_by('-amount')

    average_salary = salaries.aggregate(Avg('amount'))['amount__avg']

    salary_json = []

    if unit.departments:
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
                salary_json.append({
                    'amount': round(average, 2),
                    'department': department.title(),
                })

    else:
        for salary in salaries:
            salary_json.append({
                'name': str(salary.person).title(),
                'position': str(salary.position).title(),
                'amount': salary.amount,
            })

    return render(request, 'governmental_unit.html', {
        'unit': unit,
        'salaries': salaries,
        'salary_json': json.dumps(salary_json),
        'average_salary': average_salary,
    })
