from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse
from django.contrib import messages

from jinja2 import Environment, FileSystemLoader

from payroll.utils import format_ballpark_number, format_salary, \
    query_transform, format_percentile, url_from_facet, \
    param_from_index, format_range, pluralize, an_or_a, \
    format_exact_number


def environment(**options):
    env = Environment(**options)

    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
        'get_messages': messages.get_messages,
    })

    env.filters.update({
        'format_ballpark_number': format_ballpark_number,
        'format_exact_number': format_exact_number,
        'format_salary': format_salary,
        'query_transform': query_transform,
        'format_percentile': format_percentile,
        'url_from_facet': url_from_facet,
        'param_from_index': param_from_index,
        'format_range': format_range,
        'pluralize': pluralize,
        'an_or_a': an_or_a,
    })

    return env
