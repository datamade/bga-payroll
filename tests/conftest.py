from django.core.management import call_command
from django.db import connection
import pytest
from pytest_django.fixtures import transactional_db

from data_import.models import Upload
from payroll.models import Employer


@pytest.fixture
@pytest.mark.django_db
def django_db_setup(django_db_setup,
                    transactional_db):
    call_command('import_metadata')


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
@pytest.mark.django_db(transaction=True)
def employer(upload, transactional_db):
    class EmployerFactory():
        def build(self, **kwargs):
            data = {
                'name': 'Half Acre',
                'vintage': upload.build(),
            }

            data.update(kwargs)

            if data.get('parent'):
                data['vintage'] = data['parent'].vintage

            return Employer.objects.create(**data)

    return EmployerFactory()
