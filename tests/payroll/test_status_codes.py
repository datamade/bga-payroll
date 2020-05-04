import pytest

from payroll.models import Employer, Person


@pytest.mark.django_db(transaction=True)
def test_parent_employer(client, salary, transactional_db):
    # Build a Salary object, because it builds one of everything else,
    # so the queries in the view routes and the template code should
    # be able to function properly.
    salary.build()

    e = Employer.objects.first()

    rv = client.get('/unit/{}/'.format(e.slug))

    assert rv.status_code == 200

    rv = client.get('/units/{}/'.format(e.slug))

    assert rv.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_child_employer(client,
                        employer,
                        salary,
                        transactional_db):

    # Create a salary.
    salary = salary.build()

    # Grab the parent employer, then give it a child employer.
    parent_employer = salary.job.position.employer
    child_employer = employer.build(name='Brew Staff', parent=parent_employer)

    child_employer.refresh_from_db()  # Get slug generated on insert

    # Make the job attached to the salary, a job of the child employer.
    child_employer.positions.add(salary.job.position)
    child_employer.save()

    e = Employer.objects.get(name='Brew Staff')

    rv = client.get('/department/{}/'.format(e.slug))

    assert rv.status_code == 200

    rv = client.get('/departments/{}/'.format(e.slug))

    assert rv.status_code == 200


@pytest.mark.django_db(transaction=True)
def test_person(salary, client, transactional_db):
    salary.build()

    p = Person.objects.first()

    rv = client.get('/person/{}/'.format(p.slug))

    assert rv.status_code == 200

    rv = client.get('/people/{}/'.format(p.slug))

    assert rv.status_code == 200
