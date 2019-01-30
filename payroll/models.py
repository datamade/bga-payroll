from django.contrib.postgres.search import SearchVectorField
from django.core.exceptions import ValidationError
from django.db import models, connection
from django.utils.translation import gettext_lazy as _

from bga_database.base_models import SluggedModel
from data_import.models import Upload, RespondingAgency, SourceFile


class VintagedModel(models.Model):
    vintage = models.ForeignKey(Upload, on_delete=models.CASCADE)

    class Meta:
        abstract = True


class SourceFileMixin(object):
    '''
    This mixin provides a method to return a SourceFile if it exists for a
    given year. To use, inherit this class, and define a responding_agency
    method that accepts a year argument and returns a handle on the responding
    agency for that year. Responding agencies are associated with units for
    each reporting year; see `Person.responding_agency` for an example of
    getting a handle on the appropriate responding agency from a model further
    removed from the unit.
    '''
    def source_file(self, year):
        responding_agency = self.responding_agency(year)

        try:
            source_file = responding_agency.source_files\
                                           .get(reporting_year=year)\
                                           .source_file

        except SourceFile.DoesNotExist:
            source_file = None

        return source_file


class Employer(SluggedModel, VintagedModel):
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self',
                               null=True,
                               on_delete=models.CASCADE,
                               related_name='departments')
    taxonomy = models.ForeignKey('EmployerTaxonomy',
                                 null=True,
                                 blank=True,
                                 on_delete=models.SET_NULL,
                                 related_name='employers')
    universe = models.ForeignKey('EmployerUniverse',
                                 null=True,
                                 blank=True,
                                 on_delete=models.SET_NULL,
                                 related_name='employers')

    def __str__(self):
        name = self.name

        if self.parent and self.parent.name.lower() not in self.name.lower():
            name = '{} {}'.format(self.parent, self.name)

        return name

    def clean(self):
        if self.is_department:
            if self.taxonomy:
                raise ValidationError(_('Departments may not have a taxonomy. Did you mean to add a universe?'))

        else:
            if self.universe:
                raise ValidationError(_('Units may not have a universe. Did you mean to add a taxonomy?'))

    @property
    def is_department(self):
        return bool(self.parent)

    @property
    def is_unclassified(self):
        '''
        Whether there is a group for comparison.
        '''
        return (self.is_department and not self.universe) \
            or (not self.is_department and not self.taxonomy)

    @property
    def endpoint(self):
        if self.is_department:
            return 'department'
        else:
            return 'unit'

    @property
    def size_class(self):
        '''
        Small, medium, or large classification for the given employer, for the
        purpose of comparing similarly sized entities.

        Size cutoffs were generated with consideration for the average, minimum,
        and maximum populations, and distribution thereof, for a given entity
        type. We also considered the practical realities of scale: Government in
        a village of 200 is a different task from government in a city of 200k.

        Note that Chicago is its own special class, and it should always be
        large.
        '''
        # Create a size class lookup where the key is a unique tuple,
        # (entity type, is_special), and the value is a tuple, (lower size
        # class boundary, upper size class boundary), where the boundaries
        # are population in thousands, such that an entity with a population
        # greater than or equal to the upper boundary is Large; less than the
        # upper but greater than or equal to the lower boundary is Medium; or
        # less than the lower boundary is Small.
        class_lookup = {
            ('Municipal', True): (-1, -1),  # Chicago municipal (always large)
            ('Municipal', False): (10, 50),  # Non-Chicago municipal
            ('County', True): (500, 1000),  # Cook or collar county
            ('County', False): (25, 75),  # Downstate county
            ('Township', True): (25, 100),  # Cook or collar township
            ('Township', False): (10, 50),  # Downstate township
        }

        if self.taxonomy:
            lookup_key = (self.taxonomy.entity_type, self.taxonomy.is_special)

            bounds = class_lookup.get(lookup_key)

            if bounds:
                lower_bound, upper_bound = bounds
                population = self.get_population()

                if population:
                    if population >= upper_bound * 1000:
                        return 'Large'

                    elif population >= lower_bound * 1000:
                        return 'Medium'

                    else:
                        return 'Small'

        else:
            return None

    def get_population(self, year=None):
        '''
        If we have no population information, return None. Otherwise, return
        the population closest to the target year (reporting year by default,
        but configurable to support viewing data from previous years in the
        future).
        '''
        if self.population.all():
            if year:
                target_year = year
            else:
                source_file = self.vintage.standardized_file.get()
                target_year = source_file.reporting_year

            population_years = [p.data_year for p in self.population.all()]
            closest = min(population_years, key=lambda x: target_year - x)

            return self.population.get(data_year=closest).population

    @property
    def employee_salaries(self):
        query = '''
            SELECT
              salary.amount
            FROM payroll_job AS job
            JOIN payroll_salary AS salary
            ON salary.job_id = job.id
            JOIN payroll_position AS position
            ON job.position_id = position.id
            JOIN payroll_employer as employer
            ON position.employer_id = employer.id
            WHERE employer.id = {id}
            OR employer.parent_id = {id}
        '''.format(id=self.id)

        with connection.cursor() as cursor:
            cursor.execute(query)

            employee_salaries = [row[0] for row in cursor]

        return employee_salaries


class UnitManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(parent_id__isnull=True)


class Unit(Employer, SourceFileMixin):
    class Meta:
        proxy = True

    objects = UnitManager()

    def __str__(self):
        return self.name

    def responding_agency(self, year):
        return self.responding_agencies\
                   .get(reporting_year=year)\
                   .responding_agency

    @property
    def is_comparable(self):
        '''
        Whether there is more than one to compare within the group.
        '''
        if not self.is_unclassified:
            return self.taxonomy.employers.count() > 1
        else:
            return False


class DepartmentManager(models.Manager):
    def get_queryset(self):
        # Always select the related parent, so additional queries are not
        # needed for displaying the name.
        return super().get_queryset().filter(parent_id__isnull=False)\
                                     .select_related('parent')


class Department(Employer, SourceFileMixin):
    class Meta:
        proxy = True

    objects = DepartmentManager()

    def __str__(self):
        if self.parent.name.lower() not in self.name.lower():
            return '{} {}'.format(self.parent, self.name)

        else:
            return self.name

    def responding_agency(self, year):
        return self.parent\
                   .responding_agencies\
                   .get(reporting_year=year)\
                   .responding_agency

    @property
    def is_comparable(self):
        '''
        Whether there is more than one to compare within the group.
        '''
        if not self.is_unclassified and not self.parent.is_unclassified:
            return self.universe\
                       .employers\
                       .filter(parent__taxonomy=self.parent.taxonomy)\
                       .count() > 1

        else:
            return False


class UnitRespondingAgency(models.Model):
    '''
    Associate units and responding agencies for a given year, so data from
    that year can be linked to a specific source file.
    '''
    unit = models.ForeignKey(
        'Employer',
        related_name='responding_agencies',
        on_delete=models.CASCADE
    )
    responding_agency = models.ForeignKey(
        RespondingAgency,
        related_name='units',
        on_delete=models.CASCADE
    )
    reporting_year = models.IntegerField()


class EmployerTaxonomy(models.Model):
    '''
    Classification of unit, e.g., municipal.
    '''
    entity_type = models.CharField(max_length=255)
    chicago = models.BooleanField()
    cook_or_collar = models.BooleanField()

    api_param = 'taxonomy'

    def __str__(self):
        kwargs = {
            'type': self.entity_type,
        }

        if self.chicago:
            kwargs['special'] = 'Chicago'
        elif self.cook_or_collar:
            kwargs['special'] = 'Cook or Collar'

        if 'special' in kwargs:
            str_taxonomy = '{special} {type}'.format(**kwargs)
        else:
            str_taxonomy = '{type}'.format(**kwargs)

        return str_taxonomy

    @property
    def is_special(self):
        return self.chicago or self.cook_or_collar

    class Meta:
        verbose_name_plural = 'Employer taxonomies'


class EmployerPopulation(models.Model):
    employer = models.ForeignKey('Employer',
                                 related_name='population',
                                 on_delete=models.CASCADE)
    population = models.IntegerField()
    data_year = models.IntegerField()

    def __str__(self):
        return '{0} ({1})'.format(self.population, self.data_year)


class EmployerUniverse(models.Model):
    '''
    Classification of a department, e.g., police department.
    '''
    name = models.CharField(max_length=255)

    api_param = 'universe'

    def __str__(self):
        return self.name


class Person(SluggedModel, VintagedModel, SourceFileMixin):
    first_name = models.CharField(max_length=255, null=True)
    last_name = models.CharField(max_length=255, null=True)
    search_vector = SearchVectorField(max_length=255, null=True)

    def __str__(self):
        name = '{0} {1}'.format(self.first_name, self.last_name)\
                        .lstrip('-')

        return name

    @property
    def endpoint(self):
        return 'person'

    @property
    def most_recent_job(self):
        '''
        Get the fully loaded job object for the most recent reporting year of
        the given Person.
        '''
        return self.jobs\
                   .select_related('position', 'position__employer', 'position__employer__parent')\
                   .order_by('-vintage__standardized_file__reporting_year')\
                   .first()

    def responding_agency(self, year):
        employer = self.jobs\
                       .get(vintage__standardized_file__reporting_year=year)\
                       .position\
                       .employer

        if employer.is_department:
            unit = employer.parent

        else:
            unit = employer

        return unit.responding_agencies\
                   .get(reporting_year=year)\
                   .responding_agency


class Job(VintagedModel):
    person = models.ForeignKey('Person',
                               related_name='jobs',
                               on_delete=models.CASCADE)
    position = models.ForeignKey('Position', on_delete=models.CASCADE, related_name='jobs')
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
    employer = models.ForeignKey('Employer', on_delete=models.CASCADE, related_name='positions')
    title = models.CharField(max_length=255, null=True)

    def __str__(self):
        position = '{0} {1}'.format(self.employer, self.title)
        return position


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

    @property
    def employer_percentile(self):
        employer = self.job.position.employer

        query = '''
            WITH salary_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY amount ASC) AS percentile,
                job.person_id
              FROM payroll_job AS job
              JOIN payroll_salary AS salary
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN payroll_employer as employer
              ON position.employer_id = employer.id
              WHERE employer.id = {employer_id}
              OR employer.parent_id = {employer_id}
            )
            SELECT percentile
            FROM salary_percentiles
            WHERE person_id = {id}
        '''.format(employer_id=employer.id,
                   id=self.job.person.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    @property
    def like_employer_percentile(self):
        employer = self.job.position.employer

        if employer.is_unclassified:
            return 'N/A'

        elif employer.is_department:
            return self._like_department_percentile(employer)

        else:
            return self._like_unit_percentile(employer)

    def _like_unit_percentile(self, employer):
        query = '''
            WITH employer_parent_lookup AS (
              SELECT
                id,
                COALESCE(parent_id, id) AS parent_id
              FROM payroll_employer
            ), salary_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY amount ASC) AS percentile,
                job.person_id
              FROM payroll_job AS job
              JOIN payroll_salary AS salary
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN employer_parent_lookup AS lookup
              ON position.employer_id = lookup.id
              JOIN payroll_employer AS employer
              ON lookup.parent_id = employer.id
              WHERE employer.taxonomy_id = {taxonomy}
            )
            SELECT percentile
            FROM salary_percentiles
            WHERE person_id = {id}
        '''.format(taxonomy=employer.taxonomy.id,
                   id=self.job.person.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def _like_department_percentile(self, employer):
        query = '''
            WITH taxonomy_members AS (
              SELECT
                department.id,
                department.universe_id
              FROM payroll_employer AS unit
              JOIN payroll_employer AS department
              ON unit.id = department.parent_id
              WHERE unit.taxonomy_id = {taxonomy}
            ),
            salary_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY amount ASC) AS percentile,
                job.person_id
              FROM payroll_job AS job
              JOIN payroll_salary AS salary
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN taxonomy_members AS department
              ON position.employer_id = department.id
              WHERE department.universe_id = {universe}
            )
            SELECT percentile
            FROM salary_percentiles
            WHERE person_id = {id}
        '''.format(taxonomy=employer.parent.taxonomy.id,
                   universe=employer.universe.id,
                   id=self.job.person.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100
