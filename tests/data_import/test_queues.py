from django.db import connection
import pytest

from data_import.models import RespondingAgency
from data_import.utils import RespondingAgencyQueue, ParentEmployerQueue, \
    ChildEmployerQueue, CsvMeta

from payroll.models import Employer


@pytest.mark.parametrize('queue,raw_field,model,model_kwargs', [
    (RespondingAgencyQueue, 'Responding Agency', RespondingAgency, {}),
    (ParentEmployerQueue, 'Employer', Employer, {'parent_id__isnull': True}),
    (ChildEmployerQueue, 'Department', Employer, {'parent_id__isnull': False}),
])
@pytest.mark.django_db(transaction=True)
def test_match_or_create_responding_agency(raw_table_setup,
                                           canned_data,
                                           employer,
                                           queue,
                                           raw_field,
                                           model,
                                           model_kwargs):
    s_file = raw_table_setup

    q = queue(s_file.id)

    name = canned_data[raw_field]

    item = {'id': None, 'name': name}

    if isinstance(q, ChildEmployerQueue):
        parent = canned_data['Employer']
        employer.build(name=parent, vintage=s_file.upload)
        item['parent'] = parent

    for match in (None, 'a matching agency'):
        q.match_or_create(item.copy(), match)

        with connection.cursor() as cursor:
            select = '''
                SELECT EXISTS(
                  SELECT 1
                  FROM {raw_payroll}
                  WHERE {processed_field} = '{item}'
                ),
                EXISTS(
                  SELECT 1
                  FROM {raw_payroll}
                  WHERE {processed_field} = '{match}'
                )
            '''.format(raw_payroll=s_file.raw_table_name,
                       processed_field=CsvMeta._clean_field(raw_field),
                       item=name,
                       match=match)

            cursor.execute(select)

            item_exists, match_exists = cursor.fetchone()

            if match:
                assert match_exists and not item_exists

            else:
                assert item_exists and not match_exists
                assert model.objects.get(name=name, **model_kwargs)
