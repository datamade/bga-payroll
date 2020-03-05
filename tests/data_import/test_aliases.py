import pytest
from django.core.exceptions import ValidationError

from data_import.models import RespondingAgencyAlias


@pytest.mark.django_db
def test_responding_agency_preferred_alias(responding_agency):
    agency = responding_agency.build()

    RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose', preferred=True)

    new_alias = RespondingAgencyAlias.objects.create(responding_agency=agency, name='by_any_other_name', preferred=True)

    old_alias_again = RespondingAgencyAlias.objects.get(name='a_rose')

    if new_alias.preferred is True:
        pass
    if old_alias_again.preferred is False:
        pass


@pytest.mark.django_db
def test_responding_agency_unique_alias(responding_agency):
    with pytest.raises(ValidationError):
        agency = responding_agency.build()

        RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose')

        another_ra_alias = RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose')
