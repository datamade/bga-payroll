import pytest

from data_import.tasks import select_unseen_responding_agency
from data_import.utils import RespondingAgencyQueue


@pytest.mark.dev
@pytest.mark.django_db(transaction=True)
def test_responding_agency_review(transactional_db,
                                  review_setup,
                                  responding_agency,
                                  queue_teardown):

    # Couple this to fixture data, rather than hard-coding
    ra = responding_agency.build()

    s_file = review_setup

    work = select_unseen_responding_agency.delay(s_file_id=s_file.id)
    work.get()

    queue = RespondingAgencyQueue(s_file.id)

    # Ditto coupling
    assert queue.remaining == 2

    remaining = True
    items = []

    while remaining:
        uid, item = queue.checkout()

        if item:
            items.append(item['name'])
        else:
            remaining = False

    assert ra.name not in items
