import pytest

from data_import.models import RespondingAgencyAlias
from data_import.utils import RespondingAgencyQueue, ParentEmployerQueue, \
    ChildEmployerQueue

from payroll.models import EmployerAlias


@pytest.mark.parametrize('queue,raw_field', [
    (RespondingAgencyQueue, 'Responding Agency'),
    (ParentEmployerQueue, 'Employer'),
    (ChildEmployerQueue, 'Department'),
])
@pytest.mark.django_db(transaction=True)
def test_match_or_create_responding_agency(raw_table_setup,
                                           canned_data,
                                           employer,
                                           queue,
                                           raw_field):
    s_file = raw_table_setup

    q = queue(s_file.id)

    item = {
        'id': None,
        'name': '{} Unseen'.format(canned_data[raw_field]),
    }

    match = employer.build(
        name='{} Match'.format(canned_data['Employer']),
        vintage=s_file.upload
    )

    for match in (None, match.id):
        q.match_or_create(item.copy(), match)

        if raw_field == 'Responding Agency':
            alias_model = RespondingAgencyAlias
            filter_kwargs = {'responding_agency_id': match}

        else:
            alias_model = EmployerAlias
            filter_kwargs = {'employer_id': match}

        filter_kwargs['name'] = item['name']

        alias = alias_model.objects.filter(**filter_kwargs)

        if match:
            assert alias.exists()

        else:
            assert not alias.exists()
