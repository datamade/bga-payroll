import re
import urllib.parse


def query_transform(request, drop_keys=['page']):
    updated = request.GET.copy()

    for k in drop_keys:
        if k in updated:
            updated.pop(k)

    return updated.urlencode()


def format_salary(i):
    '''
    Strip cents off salary figures.
    '''
    if isinstance(i, str):
        return i
    return "${:,.0f}".format(i)


def format_ballpark_number(i):
    '''
    Given an integer, i, return a shortened form of the number, i.e.,
    10,000 = 10k, 2,000,000 = 2.0 million, etc. Return a string.
    '''
    buckets = [
        (1000, 'k'),
        (1000000, ' million'),
        (1000000000, ' billion'),
        (1000000000000, ' trillion'),
    ]

    def n_sig_figs(floating_point):
        integer = int(floating_point)
        return len(str(integer))

    for b, suffix in buckets:
        quotient = float(i / b)

        if quotient >= 1000:
            continue

        elif quotient < 1:
            return str(i)

        else:
            if n_sig_figs(quotient) > 1:
                number = int(quotient)
            else:
                number = round(quotient, 1)

            return '{0}{1}'.format(number, suffix)


def format_percentile(i):
    if isinstance(i, str):
        return i

    return "{:,.2f}".format(i) + '%'


def param_from_index(index_field):
    from payroll.search import PayrollSearchMixin

    index_param_map = {v: k for k, v in PayrollSearchMixin.param_index_map.items()}

    return index_param_map[index_field]


def url_from_facet(facet_data, request):
    from payroll.search import PayrollSearchMixin

    params = {}

    for index_field, value in facet_data:
        param = param_from_index(index_field)

        if param in PayrollSearchMixin.range_fields:
            match = re.match(r'\[(?P<lower_bound>\d+),(?P<upper_bound>(\d+|\*))\)', value)
            params.update({
                '{}_above'.format(param): match.group('lower_bound'),
                '{}_below'.format(param): match.group('upper_bound'),
            })

        else:
            if param in ('universe', 'taxonomy'):
                value = '"{}"'.format(value)

            params[param] = value

    request_params = request.GET.dict()

    if 'page' in request_params:
        request_params.pop('page')

    request_params.update(params)

    return urllib.parse.urlencode(request_params)


def employer_from_slug(slug):
    from payroll.models import Employer

    return Employer.objects.get(slug=slug)


def format_range(range, salary=True):
    match = re.match(r'\[(?P<lower_bound>\d+),(?P<upper_bound>(\d+|\*))\)', range)
    lower_bound = match.group('lower_bound')
    upper_bound = match.group('upper_bound')

    if lower_bound == '0':
        return 'Less than {}'.format(upper_bound)
    elif upper_bound != '*':
        return '{} to {}'.format(lower_bound, upper_bound)
    else:
        return 'More than {}'.format(lower_bound)
