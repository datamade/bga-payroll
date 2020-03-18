import os

from django.core.files import File
import pytest

from data_import.models import Upload, RespondingAgency, StandardizedFile, \
    RespondingAgencyAlias
from payroll.models import Employer, UnitRespondingAgency, EmployerTaxonomy, \
    EmployerUniverse


@pytest.fixture
def project_directory():
    test_directory = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(test_directory, '..')


@pytest.fixture
def mock_file(mocker):
    mock_file = mocker.MagicMock(spec=File)
    mock_file.name = 'mock_file.csv'

    return mock_file


@pytest.fixture
@pytest.mark.django_db
def upload():
    class UploadFactory():
        def build(self, **kwargs):
            data = {}
            data.update(kwargs)

            return Upload.objects.create(**data)

    return UploadFactory()


@pytest.fixture
@pytest.mark.django_db
def standardized_file(mock_file, upload):
    class StandardizedFileFactory():
        def build(self, **kwargs):
            data = {
                'reporting_year': 2017,
                'standardized_file': mock_file,
                'upload': upload.build(),
            }
            data.update(kwargs)

            return StandardizedFile.objects.create(**data)

    return StandardizedFileFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def responding_agency(transactional_db):
    class RespondingAgencyFactory():
        def build(self, **kwargs):
            data = {
                'name': 'Half Acre Beer Co',
            }
            data.update(kwargs)

            agency = RespondingAgency.objects.create(**data)
            alias = RespondingAgencyAlias.objects.create(name=data['name'], responding_agency=agency)

            return agency

    return RespondingAgencyFactory()


@pytest.fixture
@pytest.mark.django_db
def employer_taxonomy():
    class TaxonomyFactory():
        def build(self, **kwargs):
            data = {
                'entity_type': 'Brewery',
                'chicago': True,
                'cook_or_collar': False,
            }
            data.update(kwargs)

            return EmployerTaxonomy.objects.create(**data)

    return TaxonomyFactory()


@pytest.fixture
@pytest.mark.django_db
def employer_universe():
    class UniverseFactory():
        def build(self, **kwargs):
            data = {
                'name': 'Brewery',
            }
            data.update(kwargs)

            return EmployerUniverse.objects.create(**data)

    return UniverseFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def employer(standardized_file,
             responding_agency,
             employer_taxonomy,
             employer_universe,
             transactional_db):

    class EmployerFactory():
        def build(self, **kwargs):
            s_file = standardized_file.build()

            data = {
                'name': 'Half Acre',
                'vintage': s_file.upload,
            }

            data.update(kwargs)

            if data.get('parent'):
                data['vintage'] = data['parent'].vintage
                data['universe'] = employer_universe.build()

            else:
                data['taxonomy'] = employer_taxonomy.build()

            employer = Employer.objects.create(**data)

            if not employer.is_department:
                agency = responding_agency.build()
                UnitRespondingAgency.objects.create(unit=employer,
                                                    responding_agency=agency,
                                                    reporting_year=2017)

            return employer

    return EmployerFactory()
