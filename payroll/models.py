from django.contrib.postgres.search import SearchVectorField
from django.db import models

from titlecase import titlecase

from bga_database.base_models import SluggedModel
from data_import.models import Upload
from payroll.utils import format_name, format_numeral


class VintagedModel(models.Model):
    vintage = models.ForeignKey(Upload, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class Employer(SluggedModel, VintagedModel):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self',
                               null=True,
                               on_delete=models.CASCADE,
                               related_name='departments')
    taxonomy = models.ForeignKey('EmployerTaxonomy',
                                 null=True,
                                 on_delete=models.SET_NULL,
                                 related_name='employers')

    def __str__(self):
        name = self.name

        if self.parent and self.parent.name.lower() not in self.name.lower():
            name = '{} {}'.format(self.parent, self.name)

        return titlecase(name.lower())

    @property
    def is_department(self):
        '''
        Return True if employer has parent, False otherwise.
        '''
        return bool(self.parent)


class EmployerTaxonomy(models.Model):
    entity_type = models.CharField(max_length=255)
    chicago = models.BooleanField()
    cook_or_collar = models.BooleanField()

    def __str__(self):
        kwargs = {
            'type': self.entity_type,
        }

        if self.chicago:
            kwargs['special'] = 'Chicago'
        elif self.cook_or_collar:
            kwargs['special'] = 'Cook or Collar'

        return '{special} {type}'.format(**kwargs).strip()


class Person(SluggedModel, VintagedModel):
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    search_vector = SearchVectorField(max_length=255, null=True)

    def __str__(self):
        name = '{0} {1}'.format(self.first_name, self.last_name)\
                        .lstrip('-')

        return titlecase(name.lower(), callback=format_name)


class Job(VintagedModel):
    person = models.ForeignKey('Person',
                               related_name='jobs',
                               on_delete=models.CASCADE)
    position = models.ForeignKey('Position', on_delete=models.CASCADE)
    start_date = models.DateField(null=True)

    def __str__(self):
        return '{0} – {1}'.format(self.person, self.position)

    @classmethod
    def of_employer(cls, employer_id, n=None):
        '''
        Return Job objects for given employer.
        '''
        employer = models.Q(position__employer_id=employer_id)
        parent_employer = models.Q(position__employer__parent_id=employer_id)

        # Return only jobs of the given employer, if that employer is a
        # department. Otherwise, return jobs of the given employer, as
        # well as its child employers.

        if Employer.objects.select_related('parent').get(id=employer_id).is_department:
            criterion = employer

        else:
            criterion = employer | parent_employer

        jobs = cls.objects.filter(criterion)\
                          .order_by('-salaries__amount')\
                          .select_related('person', 'position', 'position__employer', 'position__employer__parent')\
                          .prefetch_related('salaries')[:n]

        return jobs


class Position(VintagedModel):
    employer = models.ForeignKey('Employer', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)

    def __repr__(self):
        position = '{0} {1}'.format(self.employer, self.title)
        return titlecase(position.lower())

    def __str__(self):
        return titlecase(self.title.lower(), callback=format_numeral)


class Salary(VintagedModel):
    '''
    The Salary object is a representation of prospective, annual salary. The
    provided amount is not a measure of actual pay, i.e., it does not include
    additional income, such as overtime or bonus pay. The provided amount is
    instead the amount an employer anticipates paying an employee for a given
    calendar (not fiscal) year.

    While most salary amounts represent an annual rate, some salaries are
    reported at hourly or per-appearance rates. This can be inferred, but is
    not explicitly specified in the source data.
    '''
    job = models.ForeignKey('Job',
                            related_name='salaries',
                            on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return '{0} {1}'.format(self.amount, self.job)

    @property
    def is_wage(self):
        '''
        Some salary data is hourly, or per appearance. This isn't explicit in
        the source, but we can intuit based on the amount. Return True if the
        salary amount is less than 1000, False otherwise.
        '''
        return self.amount < 1000
