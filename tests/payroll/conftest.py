import datetime

import pytest

from payroll.models import Person, Position, Job, Salary


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def person(standardized_file):
    class PersonFactory():
        def build(self, **kwargs):
            s_file = standardized_file.build()

            data = {
                'first_name': 'Joe',
                'last_name': 'Dirt',
                'vintage': s_file.upload,
            }
            data.update(kwargs)

            return Person.objects.create(**data)

    return PersonFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def position(standardized_file, employer):
    class PositionFactory():
        def build(self, **kwargs):
            s_file = standardized_file.build()

            data = {
                'employer': employer.build(),
                'title': 'Brewmaster',
                'vintage': s_file.upload,
            }
            data.update(kwargs)

            return Position.objects.create(**data)

    return PositionFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def job(standardized_file, person, position):
    class JobFactory():
        def build(self, **kwargs):
            s_file = standardized_file.build()

            data = {
                'person': person.build(),
                'position': position.build(),
                'start_date': datetime.datetime(2010, 5, 5),
                'vintage': s_file.upload,
            }
            data.update(kwargs)

            return Job.objects.create(**data)

    return JobFactory()


@pytest.fixture
@pytest.mark.django_db(transaction=True)
def salary(standardized_file, job):
    class SalaryFactory():
        def build(self, **kwargs):
            s_file = standardized_file.build()

            data = {
                'amount': '25000',
                'job': job.build(),
                'vintage': s_file.upload,
            }

            data.update(kwargs)

            return Salary.objects.create(**data)

    return SalaryFactory()
