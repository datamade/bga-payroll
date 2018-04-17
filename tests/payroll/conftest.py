import datetime

import pytest

from payroll.models import Employer, Person, Position, Job, Salary


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

            return Employer.objects.create(**data)

    return EmployerFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def person(upload):
    class PersonFactory():
        def build(self, **kwargs):
            data = {
                'first_name': 'Joe',
                'last_name': 'Dirt',
                'vintage': upload.build(),
            }
            data.update(kwargs)

            return Person.objects.create(**data)

    return PersonFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def position(upload, employer):
    class PositionFactory():
        def build(self, **kwargs):
            data = {
                'employer': employer.build(),
                'title': 'Brewmaster',
                'vintage': upload.build(),
            }
            data.update(kwargs)

            return Position.objects.create(**data)

    return PositionFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def job(upload, person, position):
    class JobFactory():
        def build(self, **kwargs):
            data = {
                'person': person.build(),
                'position': position.build(),
                'start_date': datetime.datetime(2010, 5, 5),
                'vintage': upload.build(),
            }
            data.update(kwargs)

            return Job.objects.create(**data)

    return JobFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def salary(upload, job):
    class SalaryFactory():
        def build(self, **kwargs):
            data = {
                'amount': '25000',
                'job': job.build(),
                'vintage': upload.build(),
            }
            data.update(kwargs)

            return Salary.objects.create(**data)

    return SalaryFactory()
