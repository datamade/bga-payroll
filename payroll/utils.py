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
