import pytest


@pytest.mark.dev
@pytest.mark.django_db(transaction=True)
def test_responding_agency_review(transactional_db,
                                  review_setup):

    s_file = review_setup
    print(s_file)
