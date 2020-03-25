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
                                           responding_agency,
                                           queue,
                                           raw_field):
    s_file = raw_table_setup

    q = queue(s_file.id)

    item = {
        'id': None,
        'name': '{} Unseen'.format(canned_data[raw_field]),
    }

    if raw_field == 'Responding Agency':
        alias_model = RespondingAgencyAlias

        match_id = responding_agency.build(
            name='{} Match'.format(canned_data[raw_field]),
        ).id

        filter_kwargs = {'responding_agency_id': match_id}

    else:
        alias_model = EmployerAlias

        match_id = employer.build(
            name='{} Match'.format(canned_data[raw_field]),
            vintage=s_file.upload
        ).id

        filter_kwargs = {'employer_id': match_id}

    filter_kwargs['name'] = item['name']

    for match in (None, match_id):
        q.match_or_create(item.copy(), match)

        alias = alias_model.objects.filter(**filter_kwargs)

        if match:
            assert alias.exists()

        else:
            assert not alias.exists()
