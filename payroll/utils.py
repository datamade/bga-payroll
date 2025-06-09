from decimal import Decimal, ROUND_HALF_UP
import math
import re
import urllib.parse

import inflect

from payroll.models import Unit, Department


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
    rounded_i = Decimal(i).quantize(0, ROUND_HALF_UP)

    if rounded_i < 0:
        return "-${:,.0f}".format(abs(rounded_i))

    return "${:,.0f}".format(rounded_i)


def order_of_magnitude(floating_point):
    '''
    If it's been a long time since high school math for you, too, the log,
    base 10, of a number is equal to the exponent to which 10 must be raised
    to equal that number. For example:

        math.log10(100) = 2.0
        math.log10(10) = 1.0
        math.log10(5) = 0.6989700043360189

    See also: https://davidhamann.de/2018/02/06/basics-of-logarithms-examples-python/
    '''
    return math.log10(floating_point)


def get_ballpark_parts(i):
    i = float(i)
    
    buckets = [
        (1000, 'k'),
        (1000000, ' million'),
        (1000000000, ' billion'),
        (1000000000000, ' trillion'),
    ]

    for bucket, suffix in buckets:
        ballpark = float(i / bucket)

        if ballpark >= 1000:
            # Move up to the next bucket.
            continue

        elif ballpark < 1:
            # Return numbers less than 1,000 as they are.
            return i, ''

        else:
            return ballpark, suffix


def format_ballpark_number(i):
    '''
    Given an integer, i, return a shortened form of the number, e.g.,
    10,000 = 10k, 2,000,000 = 2.0 million, etc. Return a string.
    '''
    ballpark, suffix = get_ballpark_parts(i)

    if suffix:
        if order_of_magnitude(ballpark) > 1:
            ballpark = Decimal(ballpark).quantize(0, ROUND_HALF_UP)
        else:
            # Include an extra digit of precision for ballparks with less
            # than one order of magnitude, e.g., 3.3 million instead of
            # 3 million.
            ballpark = Decimal(ballpark).quantize(1, ROUND_HALF_UP)

    return '{0}{1}'.format(ballpark, suffix)


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

            elif isinstance(value, Unit) or isinstance(value, Department):
                value = value.slug

            params[param] = value

    request_params = request.GET.dict()

    if 'page' in request_params:
        request_params.pop('page')

    request_params.update(params)

    return urllib.parse.urlencode(request_params)


def format_exact_number(i):
    return "{:,.0f}".format(int(i))


def format_range(range, salary=True):
    match = re.match(r'\[(?P<lower_bound>\d+),(?P<upper_bound>(\d+|\*))\)', range)
    lower_bound = match.group('lower_bound')
    upper_bound = match.group('upper_bound')

    if lower_bound == '0':
        return 'Less than {}'.format(format_exact_number(upper_bound))

    elif upper_bound != '*':
        return '{} to {}'.format(format_exact_number(lower_bound),
                                 format_exact_number(upper_bound))

    else:
        return 'More than {}'.format(format_exact_number(lower_bound))


def pluralize(singular):
    inf = inflect.engine()

    words = str(singular).split(' ')
    last_word = words.pop(-1)

    # For some reason, plural does not work for capitalized nouns, maybe
    # because it doesn't want to mess up proper nouns? That's not our use
    # case, so circumvent it.
    plural_last_word = inf.plural(last_word.lower())

    if last_word[0].isupper():
        plural_last_word = '{0}{1}'.format(plural_last_word[0].upper(),
                                           plural_last_word[1:])

    words.append(plural_last_word)

    return ' '.join(words)


def an_or_a(word, bold=False):
    if word[0].lower() in 'aeiou':
        phrase = 'an {}'
    else:
        phrase = 'a {}'

    if bold:
        word = '<strong>' + word + '</strong>'

    return phrase.format(word)


def employers_from_slugs(slugs):
    employers = {e.slug: e for e in Unit.objects.filter(slug__in=slugs)}

    employers.update(
        {e.slug: e for e in Department.objects.filter(slug__in=slugs)}
    )

    return employers
