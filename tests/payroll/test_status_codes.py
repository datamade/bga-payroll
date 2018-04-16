import pytest

from payroll.models import Employer, Person


@pytest.mark.django_db(transaction=True)
def test_parent_employer(client, salary, transactional_db):
    # Build a Salary object, because it builds one of everything else,
    # so the queries in the view routes and the template code should
    # be able to function properly.
    salary.build()

    e = Employer.objects.first()

    rv = client.get('/employer/{}/'.format(e.slug))

    assert rv.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_child_employer(client,
                        employer,
                        salary,
                        transactional_db):

    # Create a parent employer, then give a child employer.
    parent_employer = employer.build()
    child_employer = employer.build(name='Brew Staff', parent=parent_employer)

    # Create a salary.
    salary = salary.build()

    # Make the job attached to the salary, a job of the child employer.
    child_employer.position_set.add(salary.job.position)
    child_employer.save()

    e = Employer.objects.get(name='Brew Staff')

    rv = client.get('/employer/{}/'.format(e.slug))

    assert rv.status_code == 200


@pytest.mark.dev
@pytest.mark.django_db(transaction=True)
def test_person(salary, client, transactional_db):
    salary.build()

    p = Person.objects.first()

    rv = client.get('/person/{}/'.format(p.slug))

    assert rv.status_code == 200
