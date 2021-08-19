import datetime

import pytest
from extra_settings.models import Setting

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
                'extra_pay': '2500',
                'job': job.build(),
                'vintage': s_file.upload,
            }

            data.update(kwargs)

            return Salary.objects.create(**data)

    return SalaryFactory()


@pytest.fixture
def show_donate():
    show_donate, _ = Setting.objects.get_or_create(name='PAYROLL_SHOW_DONATE_BANNER',  # noqa
                                                   defaults={'value_type': Setting.TYPE_BOOL})  # noqa
    show_donate.value = True
    show_donate.save()

    return show_donate


@pytest.fixture
def donate_message():
    message, _ = Setting.objects.get_or_create(name='DONATE_MESSAGE',
                                               defaults={'value_type': Setting.TYPE_TEXT})
    return message


# flake8: noqa
@pytest.fixture
def allowed_input(): 
    return """<p class="lead"><strong>Dear BGA readers,</strong></p>
        <p>First, thanks very much for visiting our Salary Database site. We know hundreds of thousands of people use it throughout the year and find it useful.</p>
        <p><strong>But we need your help to keep this important source of information going.</strong> This database costs money and time to complete. We contract with outside organizations, and BGA staffers spend more than a year requesting, compiling, organizing and checking data from hundreds of government bodies across Illinois to bring this site to you for free. We don't run ads and we are a small nonprofit.</p>
        <p>If every person who visited this site gave us $1, we could complete our fundraising for the year right now. If you find this database valuable, please take just a few minutes to support it. Thank you.</p>
        <p class="text-center"><a class="btn btn-primary btn-lg" href="https://donate.bettergov.org" target="_blank">Please support this work today!</a></p>
      """
