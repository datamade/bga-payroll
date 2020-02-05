import pytest
from django.db.utils import IntegrityError


@pytest.mark.django_db
def test_null_salary(salary):
    with pytest.raises(IntegrityError):
        salary.build(amount=None, extra_pay=None)


@pytest.mark.django_db
def test_null_salary_amount(salary):
    s = salary.build(amount=None)

    assert s.extra_pay == '2500'


@pytest.mark.django_db
def test_null_salary_extra_pay(salary):
    s = salary.build(extra_pay=None)

    assert s.amount == '25000'
