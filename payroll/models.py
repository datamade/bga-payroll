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
    start_date = models.DateField(null=True)
    position = models.ForeignKey('Position', on_delete=models.CASCADE)


class Position(VintagedModel):
    employer = models.ForeignKey('Employer', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)

    def __repr__(self):
        position = '{0} – {1}'.format(self.employer, self.title)
        return titlecase(position.lower())

    def __str__(self):
        return titlecase(self.title.lower(), callback=format_numeral)


class Salary(VintagedModel):
    job = models.ForeignKey('Job',
                            related_name='salaries',
                            on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return '{0} {1}'.format(self.amount, self.position)

    @property
    def person(self):
        # Force Django to use the cached person objects, if they exist
        if hasattr(self, '_prefetched_objects_cache') and 'person' in self._prefetched_objects_cache:
            return self._prefetched_objects_cache['person'][0]

        else:
            return self.person_set.get()

    @property
    def is_wage(self):
        '''
        Some salary data is hourly, or per appearance. This isn't explicit in
        the source, but we can intuit based on the amount. Return True if the
        salary amount is less than 1000, False otherwise.
        '''
        return self.amount < 1000

    @classmethod
    def of_employer(cls, employer_id, n=None):
        '''
        Return Salary objects for given employer.
        '''
        employer = models.Q(position__employer_id=employer_id)
        parent_employer = models.Q(position__employer__parent_id=employer_id)

        # Return only salaries of the given employer, if that employer is a
        # department. Otherwise, return salaries of the given employer, as
        # well as its child employers.

        if Employer.objects.select_related('parent').get(id=employer_id).is_department:
            criterion = employer

        else:
            criterion = employer | parent_employer

        salaries = cls.objects.filter(criterion)\
                              .order_by('-amount')\
                              .select_related('position', 'position__employer', 'position__employer__parent')\
                              .prefetch_related('person_set')[:n]

        return salaries
