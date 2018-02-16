import json

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

    salaries = Salary.objects.filter(
        Q(position__employer_id=uid) | Q(position__employer__parent_id=uid)
    ).order_by('-amount')

    average_salary = salaries.aggregate(Avg('amount'))['amount__avg']

    # Make the data for the distribution chart
    salary_json = []

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
