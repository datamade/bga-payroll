from django.contrib.postgres.search import SearchVectorField
from django.db import models
from django.utils.text import slugify


class Employer(models.Model):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self',
                               null=True,
                               on_delete=models.CASCADE,
                               related_name='departments')
    slug = models.SlugField(max_length=255, unique=True, null=True)

    def __str__(self):
        if self.parent:
            return '{} {}'.format(self.parent, self.name).title()

        else:
            return self.name.title()

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._make_slug()

        super().save()

    def _make_slug(self):
        if self.parent:
            slug = slugify('{0} {1}'.format(self.parent, self.name))
        else:
            slug = slugify(self.name)

        i = 1
        unique_slug = slug

        while Employer.objects.filter(slug=unique_slug).exists():
            unique_slug = '{0}-{1}'.format(slug, str(i))
            i += 1

        return unique_slug

    @property
    def is_department(self):
        '''
        Return True if employer has parent, False otherwise.
        '''
        return bool(self.parent)


class Person(models.Model):
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    salaries = models.ManyToManyField('Salary')
    search_vector = SearchVectorField(max_length=255, null=True)

    def __str__(self):
        return '{0} {1}'.format(self.first_name, self.last_name)


class Position(models.Model):
    employer = models.ForeignKey('Employer', on_delete=models.CASCADE)
    title = models.CharField(max_length=255, null=True)

    def __str__(self):
        return '{0} {1}'.format(self.employer.name, self.title)


class Salary(models.Model):
    position = models.ForeignKey('Position', on_delete=models.CASCADE)
    amount = models.FloatField()
    start_date = models.DateField(null=True)
    vintage = models.IntegerField()

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
    def of_employer(cls, employer_id):
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
                              .prefetch_related('person_set')

        return salaries
