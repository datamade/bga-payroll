import pytest
from django.db.utils import IntegrityError


@pytest.mark.django_db(transaction=True)
def test_null_salary(salary):
    with pytest.raises(IntegrityError):
        salary.build_null()


@pytest.mark.django_db(transaction=True)
def test_null_salary_amount(salary):
    with pytest.raises(IntegrityError):
        salary.build_null_amount_zero_extra_pay()


@pytest.mark.django_db(transaction=True)
def test_null_salary_extra_pay(salary):
    with pytest.raises(IntegrityError):
        salary.build_null_extra_pay_zero_amount()
