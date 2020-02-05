import pytest
from django.db.utils import IntegrityError


@pytest.mark.django_db(transaction=True)
def test_null_salary(salary):
    with pytest.raises(IntegrityError):
        salary.build(amount=None, extra_pay=None)
