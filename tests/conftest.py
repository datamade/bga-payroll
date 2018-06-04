from django.db import connection
import pytest
from pytest_django.fixtures import transactional_db

from data_import.models import Upload
from payroll.models import Employer


@pytest.fixture
@pytest.mark.django_db
def django_db_setup(django_db_setup,
                    transactional_db):
    table_name = 'illinois_places'

    columns = '''
        name VARCHAR,
        geoid VARCHAR
    '''

    create = 'CREATE TABLE {} ({})'.format(table_name, columns)

    with connection.cursor() as cursor:
        cursor.execute(create)

    with open('tests/data_import/fixtures/illinois_places.csv', 'r', encoding='utf-8') as f:
        with connection.cursor() as cursor:
            copy_fmt = 'COPY "{table}" ({cols}) FROM STDIN CSV HEADER'

            copy = copy_fmt.format(table=table_name,
                                   cols=columns.replace(' VARCHAR', '').replace(' BOOLEAN', ''))

            cursor.copy_expert(copy, f)


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
