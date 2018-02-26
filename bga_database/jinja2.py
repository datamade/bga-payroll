from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

from jinja2 import Environment

from payroll.utils import format_ballpark_number, format_salary


def environment(**options):
    env = Environment(**options)

    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
    })

    env.filters.update({
        'format_ballpark_number': format_ballpark_number,
        'format_salary': format_salary,
    })

    return env
