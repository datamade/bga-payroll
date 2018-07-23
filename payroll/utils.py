import re
import urllib.parse

from titlecase import titlecase


def format_name(word, **kwargs):
    '''
    Callback for titlecase lib. Capitalize initials and numeral suffixes.
    '''
    if len(word) == 1 or format_numeral(word):
        return word.upper()


def format_numeral(word, **kwargs):
    '''
    Callback for titlecase lib. Capitalize numeral suffix.
    '''
    numerals = ['i', 'ii', 'iii', 'iv', 'v', 'vi', 'vii', 'viii', 'ix', 'x']

    if word.lower() in numerals:
        return word.upper()


def titlecase_standalone(entity):
    return titlecase(entity)


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
    1,000 = 1k, 2,000,000 = 2 million, etc.
    '''
    try:
        i = int(i)

    except TypeError:
        raise TypeError('i must be coerceable to an integer')

    def truncate(i):
        return str(i)[:-3]

    if len(truncate(i)) < 1:
        return str(i)
    else:
        truncated_i = truncate(i)

    truncate_count = 1

    while len(truncated_i) > 3:
        truncated_i = truncate(truncated_i)
        truncate_count += 1

    suffix_map = {
        1: 'k',
        2: ' million',
        3: ' billion',
        4: ' trillion',
    }

    return truncated_i + suffix_map[truncate_count]


def format_percentile(i):
    if isinstance(i, str):
        return i

    return "{:,.2f}".format(i) + '%'


def param_from_index(index_field):
    from payroll.search import PayrollSearchMixin

    index_param_map = {v: k for k, v in PayrollSearchMixin.param_index_map.items()}

    return index_param_map[index_field]


def url_from_facet(value, index_field):
    from payroll.search import PayrollSearchMixin

    param = param_from_index(index_field)

    if param in PayrollSearchMixin.range_fields:
        match = re.match(r'\[(?P<lower_bound>\d+),(?P<upper_bound>(\d+|\*))\)', value)
        params = {
            '{}_above'.format(param): match.group('lower_bound'),
            '{}_below'.format(param): match.group('upper_bound'),
        }

    else:
        params = {param: value}

    return '?' + urllib.parse.urlencode(params)


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

def query_content(request):
    query_parts = []

    for param in request.keys():
        value = request[param]

        if param in ('name', 'entity_type'):
            query_parts.append(value)

        elif param == 'employer':
            query_parts.append('employees of ' + str(employer_from_slug(value)))

        elif param == 'parent':
            query_parts.append('departments in ' + str(employer_from_slug(value)))

        else:
            for p in ('expenditure', 'headcount'):
                p_keys = [k for k in request.keys() if k.startswith(p)]
                if p_keys:
                    lower, upper = '{}_above'.format(p), '{}_below'.format(p)

                    if len(p_keys) == 2:
                        part = '{0} between {1} and {2}'.format(p,
                                                                request.get(lower),
                                                                request.get(upper))

                    elif request.get(upper):
                        part = '{0} below {1}'.format(p, request.get(upper))

                    elif request.get(lower):
                        part = '{0} above {1}'.format(p, request.get(lower))

                    query_parts.append(part)

    return set(query_parts)
