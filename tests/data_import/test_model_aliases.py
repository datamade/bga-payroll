import pytest
from django.core.exceptions import ValidationError

from data_import.models import RespondingAgencyAlias
from payroll.models import EmployerAlias


@pytest.mark.django_db
def test_responding_agency_preferred_alias(responding_agency):
    agency = responding_agency.build()

    old_alias = RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose', preferred=True)

    new_alias = RespondingAgencyAlias.objects.create(responding_agency=agency, name='by_any_other_name', preferred=True)

    old_alias.refresh_from_db()

    assert new_alias.preferred is True
    assert old_alias.preferred is False


@pytest.mark.django_db
def test_responding_agency_unique_alias(responding_agency):
    agency = responding_agency.build()

    with pytest.raises(ValidationError):

        RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose')
        RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose')


@pytest.mark.django_db
def test_department_preferred_alias(employer):
    unit = employer.build()
    department = employer.build(parent=unit, name='a_dept')

    old_alias = EmployerAlias.objects.create(employer=department, name='a_rose', preferred=True)

    new_alias = EmployerAlias.objects.create(employer=department, name='by_any_other_name', preferred=True)

    old_alias.refresh_from_db()

    assert new_alias.preferred is True
    assert old_alias.preferred is False


@pytest.mark.django_db
def test_department_unique_alias(employer):
    unit = employer.build()
    department = employer.build(parent=unit, name='a_dept')

    with pytest.raises(ValidationError):
        EmployerAlias.objects.create(employer=department, name='a_rose')
        EmployerAlias.objects.create(employer=department, name='a_rose')


@pytest.mark.django_db
def test_unit_preferred_alias(employer):
    unit = employer.build()

    old_alias = EmployerAlias.objects.create(employer=unit, name='a_rose', preferred=True)

    new_alias = EmployerAlias.objects.create(employer=unit, name='by_any_other_name', preferred=True)

    old_alias.refresh_from_db()

    assert new_alias.preferred is True
    assert old_alias.preferred is False


@pytest.mark.django_db
def test_unit_unique_alias(employer):
    unit = employer.build()

    with pytest.raises(ValidationError):
        EmployerAlias.objects.create(employer=unit, name='a_rose')
        EmployerAlias.objects.create(employer=unit, name='a_rose')


@pytest.mark.django_db
def test_dept_gets_unit_alias(employer):
    unit = employer.build()
    department = employer.build(parent=unit, name='a_dept')

    unit_alias = EmployerAlias.objects.create(employer=unit, name='a_rose')
    dept_alias = EmployerAlias.objects.create(employer=department, name='a_rose')

    assert unit_alias.name == 'a_rose'
    assert dept_alias.name == 'a_rose'


@pytest.mark.django_db
def test_unit_gets_dept_alias(employer):
    unit = employer.build()
    department = employer.build(parent=unit, name='a_dept')

    dept_alias = EmployerAlias.objects.create(employer=department, name='a_rose')
    unit_alias = EmployerAlias.objects.create(employer=unit, name='a_rose')

    assert dept_alias.name == 'a_rose'
    assert unit_alias.name == 'a_rose'
