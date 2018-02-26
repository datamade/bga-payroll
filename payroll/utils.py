def format_salary(i):
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
