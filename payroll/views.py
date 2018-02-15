from django.shortcuts import render

from payroll.models import Employer


def index(request):
    return render(request, 'base.html')


def governmental_unit(request, id=None):
    if id:
        units = [Employer.objects.get(id=id)]
    else:
        units = Employer.objects.filter(parent_id__isnull=True)

    return render(request, 'governmental_unit.html', {
        'units': units,
    })
