from django.contrib.staticfiles.storage import staticfiles_storage
from django.urls import reverse

from jinja2 import Environment

from payroll.utils import format_ballpark_number, format_salary, \
    titlecase_standalone, query_transform, format_percentile, url_from_facet, \
    param_from_index, employer_from_slug, format_range, query_content


def environment(**options):
    env = Environment(**options)

    env.globals.update({
        'static': staticfiles_storage.url,
        'url': reverse,
    })

    env.filters.update({
        'format_ballpark_number': format_ballpark_number,
        'format_salary': format_salary,
        'titlecase_standalone': titlecase_standalone,
        'query_transform': query_transform,
        'format_percentile': format_percentile,
        'url_from_facet': url_from_facet,
        'param_from_index': param_from_index,
        'employer_from_slug': employer_from_slug,
        'format_range': format_range,
        'query_content': query_content,
    })

    return env
