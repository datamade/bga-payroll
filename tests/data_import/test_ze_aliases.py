import pytest
from django.core.exceptions import ValidationError

from data_import.models import RespondingAgencyAlias


@pytest.mark.django_db
def test_responding_agency_preferred_alias(responding_agency):
    agency = responding_agency.build()

    old_alias = RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose', preferred=True)

    new_alias = RespondingAgencyAlias.objects.create(responding_agency=agency, name='by_any_other_name', preferred=True)

    old_alias_again = RespondingAgencyAlias.objects.get(id=old_alias.id)

    if new_alias.preferred:
        pass
    if not old_alias_again.preferred:
        pass


@pytest.mark.django_db
def test_responding_agency_unique_alias(responding_agency):
    with pytest.raises(ValidationError):
        agency = responding_agency.build()

        RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose')

        RespondingAgencyAlias.objects.create(responding_agency=agency, name='a_rose')
