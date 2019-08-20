from itertools import chain
import json

from django.core.cache import cache
from django.db import connection
from django.db.models import Q, FloatField, Prefetch
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.views.generic import FormView
from postgres_stats.aggregates import Percentile
from django.contrib.auth.views import LoginView, PasswordResetView, \
    PasswordResetDoneView, PasswordResetConfirmView
from django.contrib.auth import login as auth_login
from django.conf import settings
from django.urls import reverse_lazy
from django.contrib import messages

from bga_database.chart_settings import BAR_HIGHLIGHT
from payroll.charts import ChartHelperMixin
from payroll.decorators import check_cache, check_detail_cache
from payroll.models import Job, Person, Salary, Unit, Department
from payroll.forms import SignupForm
from payroll.search import PayrollSearchMixin, FacetingMixin, \
    DisallowedSearchException

from bga_database.local_settings import CACHE_SECRET_KEY


class IndexView(TemplateView, ChartHelperMixin):
    template_name = 'index.html'

    def get_context_data(self):
        context = super().get_context_data()

        salary_count = self.salary_count
        unit_count = Unit.objects.all().count()
        department_count = Department.objects.all().count()

        binned_salaries = self.binned_salaries

        context.update({
            'salary_count': salary_count,
            'unit_count': unit_count,
            'department_count': department_count,
            'salary_json': json.dumps(binned_salaries),
        })

        return context

    @property
    def _cache(self):
        cached_keys = [
            'binned_salaries',
            'salary_count',
        ]
        cache_prefix = 'index'
        keys = [cache_prefix + '_' + k for k in cached_keys]

        if not hasattr(self, '_kache'):
            self._kache = cache.get_many(keys)

        return self._kache

    @property
    @check_cache(cache_prefix='index')
    def binned_salaries(self):
        with connection.cursor() as cursor:
            cursor.execute('SELECT amount FROM payroll_salary')
            all_salaries = [x[0] for x in cursor]

        return self.bin_salary_data(all_salaries)

    @property
    @check_cache(cache_prefix='index')
    def salary_count(self):
        return Salary.objects.all().count()


class UserGuideView(TemplateView):
    template_name = 'user_guide.html'


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


class EmployerView(DetailView, ChartHelperMixin):
    context_object_name = 'entity'

    # from_clause connects salaries and employers through a series of joins.
    from_clause = '''
        FROM payroll_job AS job
        JOIN payroll_salary AS salary
        ON salary.job_id = job.id
        JOIN payroll_position AS position
        ON job.position_id = position.id
        JOIN payroll_employer as employer
        ON position.employer_id = employer.id
    '''

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        employee_salaries = self.employee_salaries
        binned_employee_salaries = self.bin_salary_data(employee_salaries)

        source_file = self.object.source_file(2017)

        if source_file:
            source_link = source_file.url
        else:
            source_link = None

        context.update({
            'jobs': self.jobs,
            'median_salary': self.median_entity_salary,
            'headcount': len(employee_salaries),
            'total_expenditure': sum(employee_salaries),
            'salary_percentile': self.salary_percentile,
            'expenditure_percentile': self.expenditure_percentile,
            'employee_salary_json': json.dumps(binned_employee_salaries),
            'data_year': 2017,
            'source_link': source_link,
        })

        return context

    def get_median_entity_salary(self):
        q = Salary.objects.filter(Q(job__position__employer__parent=self.object) | Q(job__position__employer=self.object))

        results = q.all().aggregate(median=Percentile('amount', 0.5, output_field=FloatField()))

        return results['median']

    @property
    def _cache(self):
        cached_keys = [
            'employee_salaries',
            'expenditure_percentile',
            'jobs',
            'median_entity_salary',
            'salary_percentile',
        ]
        cache_prefix = str(self.object.id)
        keys = [cache_prefix + '_' + k for k in cached_keys]

        if not hasattr(self, '_kache'):
            self._kache = cache.get_many(keys)

        return self._kache

    @property
    @check_detail_cache
    def employee_salaries(self):
        return self.object.employee_salaries

    @property
    @check_detail_cache
    def expenditure_percentile(self):
        return self.get_expenditure_percentile()

    @property
    @check_detail_cache
    def jobs(self):
        return Job.of_employer(self.object.id, n=5)

    @property
    @check_detail_cache
    def median_entity_salary(self):
        return self.get_median_entity_salary()

    @property
    @check_detail_cache
    def salary_percentile(self):
        return self.get_salary_percentile()


class UnitView(EmployerView):
    model = Unit
    template_name = 'unit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        department_statistics = self.aggregate_department_statistics

        context.update({
            'department_salaries': department_statistics[:5],
            'population_percentile': self.population_percentile(),
            'highest_spending_department': self.highest_spending_department,
            'composition_json': self.composition_data(),
            'size_class': self.object.size_class,
        })

        return context

    def get_aggregate_department_statistics(self):
        query = '''
            SELECT
              employer.name,
              AVG(salary.amount) AS average,
              SUM(salary.amount) AS budget,
              COUNT(*) AS headcount,
              employer.slug AS slug
            {from_clause}
            WHERE employer.parent_id = {id}
            GROUP BY employer.id, employer.name
            ORDER BY SUM(salary.amount) DESC
        '''.format(from_clause=self.from_clause,
                   id=self.object.id)

        total_expenditure = sum(self.object.employee_salaries)

        with connection.cursor() as cursor:
            cursor.execute(query)

            department_salaries = []
            for department, average, budget, headcount, slug in cursor:
                department_salaries.append({
                    'department': department,
                    'amount': average,
                    'total_budget': budget,
                    'headcount': headcount,
                    'slug': slug,
                    'percentage': (float(budget / total_expenditure) * 100)  # Percentage of total expenditure
                })

        return department_salaries

    def composition_data(self):
        '''
        Returns the data required to make the composition chart of top spending departments
        '''
        all_departments = self.aggregate_department_statistics
        top_departments = all_departments[:5]

        composition_json = []
        percentage_tracker = 0

        for i, value in enumerate(top_departments):
            composition_json.append({
                'name': value['department'],
                'data': [value['percentage']],
                'index': i
            })
            percentage_tracker += value['percentage']

        composition_json.append({
            'name': 'All else',
            'data': [100 - percentage_tracker],
            'index': 5

        })

        return composition_json

    def population_percentile(self):
        if (self.object.get_population() is None):
            return 'N/A'

        query = '''
            WITH pop_percentile AS (
              SELECT
                percent_rank() OVER (ORDER BY pop.population ASC) AS percentile,
                pop.employer_id AS unit_id
              FROM payroll_employerpopulation AS pop
              JOIN payroll_employer AS emp
              ON pop.employer_id = emp.id
              JOIN payroll_employertaxonomy AS tax
              ON emp.taxonomy_id = tax.id
              WHERE tax.id = {taxonomy}
            )
            SELECT percentile FROM pop_percentile
            WHERE unit_id = {id}
        '''.format(taxonomy=self.object.taxonomy_id, id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def get_expenditure_percentile(self):
        if self.object.is_unclassified:
            return 'N/A'

        query = '''
            WITH employer_parent_lookup AS (
              SELECT
                id,
                COALESCE(parent_id, id) AS parent_id
              FROM payroll_employer
            ),
            expenditure_by_unit AS (
              SELECT
                SUM(salary.amount) AS total_budget,
                lookup.parent_id AS unit_id
              FROM payroll_salary AS salary
              JOIN payroll_job AS job
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN employer_parent_lookup AS lookup
              ON position.employer_id = lookup.id
              JOIN payroll_employer AS employer
              ON lookup.parent_id = employer.id
              WHERE employer.taxonomy_id = {taxonomy}
              GROUP BY lookup.parent_id
            ),
            exp_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY total_budget ASC) AS percentile,
                unit_id
              FROM expenditure_by_unit
            )
            SELECT
              percentile
            FROM exp_percentiles
            WHERE unit_id = {id}
        '''.format(taxonomy=self.object.taxonomy.id,
                   id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def get_salary_percentile(self):
        if self.object.is_unclassified:
            return 'N/A'

        query = '''
            WITH employer_parent_lookup AS (
              SELECT
                id,
                COALESCE(parent_id, id) AS parent_id
              FROM payroll_employer
            ),
            median_salaries_by_unit AS (
              SELECT
                percentile_cont(0.5) WITHIN GROUP (ORDER BY salary.amount ASC) AS median_salary,
                lookup.parent_id AS unit_id
              FROM payroll_salary AS salary
              JOIN payroll_job AS job
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN employer_parent_lookup AS lookup
              ON position.employer_id = lookup.id
              JOIN payroll_employer AS employer
              ON lookup.parent_id = employer.id
              WHERE employer.taxonomy_id = {taxonomy}
              GROUP BY lookup.parent_id
            ),
            salary_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY median_salary ASC) AS percentile,
                unit_id
              FROM median_salaries_by_unit
            )
            SELECT percentile
            FROM salary_percentiles
            WHERE unit_id = {id}
            '''.format(taxonomy=self.object.taxonomy.id,
                       id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def get_highest_spending_department(self):
        query = '''
          WITH all_department_expenditures AS (
            SELECT
              SUM(salary.amount) AS dept_budget,
              employer.id as dept_id
            FROM payroll_salary AS salary
            JOIN payroll_job AS job
            ON salary.job_id = job.id
            JOIN payroll_position AS positions
            ON job.position_id = positions.id
            JOIN payroll_employer AS employer
            ON positions.employer_id = employer.id
            GROUP BY employer.id
          ),
          parent_department_expenditures AS (
            SELECT
              *
            FROM all_department_expenditures as ade
            JOIN payroll_employer AS employer
            ON ade.dept_id = employer.id
            WHERE employer.parent_id = {id}
          )
          SELECT
            employer.name,
            dept_budget,
            employer.slug
          FROM parent_department_expenditures
          JOIN payroll_employer as employer
          ON parent_department_expenditures.dept_id = employer.id
          ORDER BY dept_budget DESC
          LIMIT 1
        '''.format(id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        if result is None:
            name, amount, slug = ['N/A'] * 3

        else:
            name, amount, slug = result

        highest_spending_department = {
            'name': name,
            'amount': amount,
            'slug': slug,
        }
        return highest_spending_department

    @property
    def _cache(self):
        cached_keys = [
            'aggregate_department_statistics',
            'highest_spending_department',
        ]
        cache_prefix = str(self.object.id)
        keys = [cache_prefix + '_' + k for k in cached_keys]

        if not hasattr(self, '_kache'):
            self._kache = super()._cache
            self._kache.update(cache.get_many(keys))

        return self._kache

    @property
    @check_detail_cache
    def aggregate_department_statistics(self):
        return self.get_aggregate_department_statistics()

    @property
    @check_detail_cache
    def highest_spending_department(self):
        return self.get_highest_spending_department()


class DepartmentView(EmployerView):
    model = Department
    template_name = 'department.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        department_expenditure = self.department_expenditure
        parent_expediture = self.parent_expenditure
        percentage = department_expenditure / parent_expediture

        context.update({
            'percent_of_total_expenditure': percentage * 100,
        })

        return context

    def get_expenditure_percentile(self):
        if self.object.is_unclassified or self.object.parent.is_unclassified:
            return 'N/A'

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
            expenditure_by_department AS (
              SELECT
                SUM(salary.amount) AS total_budget,
                department.id AS department_id
              FROM payroll_salary AS salary
              JOIN payroll_job AS job
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN taxonomy_members AS department
              ON position.employer_id = department.id
              WHERE department.universe_id = {universe}
              GROUP BY department.id
            ),
            exp_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY total_budget ASC) AS percentile,
                department_id
              FROM expenditure_by_department
            )
            SELECT
              percentile
            FROM exp_percentiles
            WHERE department_id = {id}
        '''.format(taxonomy=self.object.parent.taxonomy.id,
                   universe=self.object.universe.id,
                   id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    def get_salary_percentile(self):
        if self.object.is_unclassified or self.object.parent.is_unclassified:
            return 'N/A'

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
            median_salaries_by_department AS (
              SELECT
                percentile_cont(0.5) WITHIN GROUP (ORDER BY salary.amount ASC) AS median_salary,
                department.id AS department_id
              FROM payroll_salary AS salary
              JOIN payroll_job AS job
              ON salary.job_id = job.id
              JOIN payroll_position AS position
              ON job.position_id = position.id
              JOIN taxonomy_members AS department
              ON position.employer_id = department.id
              WHERE department.universe_id = {universe}
              GROUP BY department.id
            ),
            salary_percentiles AS (
              SELECT
                percent_rank() OVER (ORDER BY median_salary ASC) AS percentile,
                department_id
              FROM median_salaries_by_department
            )
            SELECT percentile
            FROM salary_percentiles
            WHERE department_id = {id}
            '''.format(taxonomy=self.object.parent.taxonomy.id,
                       universe=self.object.universe.id,
                       id=self.object.id)

        with connection.cursor() as cursor:
            cursor.execute(query)
            result = cursor.fetchone()

        return result[0] * 100

    @property
    def _cache(self):
        cached_keys = [
            'department_expenditure',
            'expenditure_percentile',
            'parent_expenditure',
            'salary_percentile',
        ]
        cache_prefix = str(self.object.id)
        keys = [cache_prefix + '_' + k for k in cached_keys]

        if not hasattr(self, '_kache'):
            self._kache = super()._cache
            self._kache.update(cache.get_many(keys))

        return self._kache

    @property
    @check_detail_cache
    def department_expenditure(self):
        return sum(self.object.employee_salaries)

    @property
    @check_detail_cache
    def expenditure_percentile(self):
        return self.get_expenditure_percentile()

    @property
    @check_detail_cache
    def parent_expenditure(self):
        return sum(self.object.parent.employee_salaries)

    @property
    @check_detail_cache
    def salary_percentile(self):
        return self.get_salary_percentile()


class PersonView(DetailView, ChartHelperMixin):
    model = Person
    context_object_name = 'entity'
    template_name = 'person.html'

    def _get_bar_color(self, lower, upper):
        if lower < int(self.salary_amount) <= upper:
            return BAR_HIGHLIGHT
        else:
            return super()._get_bar_color(lower, upper)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        all_jobs = self.object.jobs.all()
        current_job = self.current_job
        current_salary = self.current_salary

        salary_prefetch = Prefetch('salaries', to_attr='salary')

        fellow_job_holders = Job.objects.filter(position=current_job.position)\
                                        .exclude(person=self.object)\
                                        .select_related('person', 'position')\
                                        .prefetch_related(salary_prefetch)\
                                        .order_by('-salaries__amount')

        employer_percentile = self.employer_percentile
        like_employer_percentile = self.like_employer_percentile

        current_employer = current_job.position.employer

        if not current_employer.is_unclassified:
            if current_employer.is_department:
                employer_type = [current_employer.universe, current_employer.parent.taxonomy]

            else:
                employer_type = [current_employer.taxonomy]

        else:
            employer_type = None

        # Must be set for salary binning to work
        self.salary_amount = current_salary.amount

        salary_data = self.salary_data
        binned_salary_data = self.bin_salary_data(salary_data)

        source_file = self.object.source_file(2017)

        if source_file:
            source_link = source_file.url
        else:
            source_link = None

        context.update({
            'data_year': 2017,
            'current_job': current_job,
            'all_jobs': all_jobs,
            'current_salary': self.salary_amount,
            'current_employer': current_employer,
            'employer_type': employer_type,
            'employer_salary_json': json.dumps(binned_salary_data),
            'employer_percentile': employer_percentile,
            'like_employer_percentile': like_employer_percentile,
            'fellow_job_holders': fellow_job_holders,
            'source_link': source_link,
            'noindex': self.salary_amount < 30000 or self.object.noindex,
        })

        return context

    @property
    def _cache(self):
        cached_keys = [
            'employer_percentile',
            'like_employer_percentile',
            'salary_data',
        ]
        cache_prefix = str(self.object.id)
        keys = [cache_prefix + '_' + k for k in cached_keys]

        if not hasattr(self, '_kache'):
            self._kache = cache.get_many(keys)

        return self._kache

    @property
    def current_job(self):
        return self.object.most_recent_job

    @property
    def current_salary(self):
        return self.current_job.salaries.get()

    @property
    @check_detail_cache
    def employer_percentile(self):
        return self.current_salary.employer_percentile

    @property
    @check_detail_cache
    def like_employer_percentile(self):
        return self.current_salary.like_employer_percentile

    @property
    @check_detail_cache
    def salary_data(self):
        return self.current_job.position.employer.employee_salaries


class SearchView(ListView, PayrollSearchMixin, FacetingMixin):
    queryset = []
    template_name = 'search_results.html'
    context_object_name = 'results'
    paginate_by = 25

    def get_queryset(self, **kwargs):
        '''
        For efficiency, we only want to return `pagesize` results at a time.

        This is accomplished by passing the number of results per page and the
        ordinal page number to the `search` method. The search method, in turn,
        uses the page size and number to query Solr for the appropriate number
        of results, from the appropriate page offset.

        The return value of this method is passed to Django's Pagination class,
        which uses count/len methods and slice functionality. Because we're only
        querying for `pagesize` results, this method returns a instance of
        LazyPaginatedResults, which provides a mocked inteface for count/len
        and slicing to facilitate returning partial result sets.
        '''
        params = self.request.GET.dict()  # contains page number as URL param

        if self.request.session.get('search_count'):
            self.request.session['search_count'] += 1

        else:
            self.request.session['search_count'] = 1

        self.facets = {}

        if self.request.user.is_authenticated or self.request.session['search_count'] <= settings.SEARCH_LIMIT:
            try:
                self.allowed = True
                results = self.search(params, pagesize=self.paginate_by)

            except DisallowedSearchException:
                self.allowed = False
                results = []
        else:
            self.allowed = False
            results = []

        return results

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['allowed'] = self.allowed

        facets = self.parse_facets(self.facets)
        context['facets'] = facets
        context['search_limit'] = settings.SEARCH_LIMIT

        return context


class EntityLookup(ListView, PayrollSearchMixin):
    def get_queryset(self, *args, **kwargs):
        self.facets = {}

        base_params = {'name': self.request.GET['term']}

        extra_search_kwargs = {
            'expenditure_d': '[1000000 TO *]',
            'salary_d': '[100000 TO *]',
        }

        units = self.search(
            dict(base_params, **{'entity_type': 'unit'}),
            pagesize=5,
            **extra_search_kwargs
        )

        people = self.search(
            dict(base_params, **{'entity_type': 'person'}),
            pagesize=5,
            **extra_search_kwargs
        )

        entities = []

        for result in chain(units, people):
            data = {
                'label': str(result),
                'value': str(result),
            }

            url = '{0}/{1}'.format(result.endpoint, result.slug)
            category = result.__class__.__name__

            data.update({
                'url': url,
                'category': category,
            })

            entities.append(data)

        return entities

    def render_to_response(self, *args, **kwargs):
        results = self.get_queryset(*args, **kwargs)

        return JsonResponse(results, safe=False)


class UserLoginView(LoginView):
    def form_valid(self, form):
        auth_login(self.request, form.get_user())

        context = self.get_context_data(form=form)

        return self.render_to_response(context)

    def render_to_response(self, context, **kwargs):
        response = {}

        errors = context['form'].errors

        if errors:
            response['redirect_url'] = None
            response['errors'] = errors['__all__']
        else:
            response['redirect_url'] = context['next']

            user = context['form'].get_user()

            messages.add_message(self.request,
                                 messages.INFO,
                                 'Welcome back {}!'.format(user.first_name),
                                 extra_tags='font-weight-bold')

            messages.add_message(self.request,
                                 messages.INFO,
                                 "We've logged you in so you can continue using the database.")

        return JsonResponse(response)


class UserSignupView(FormView):

    form_class = SignupForm

    def form_valid(self, form):
        user = form.make_user()

        auth_login(self.request, user)

        context = self.get_context_data(form=form)

        return self.render_to_response(context)

    def render_to_response(self, context, **kwargs):
        response = {}

        errors = context['form'].errors

        if errors:
            response['redirect_url'] = None
            response['errors'] = errors
        else:
            response['redirect_url'] = self.request.POST['next']

            messages.add_message(self.request,
                                 messages.INFO,
                                 'Thanks for signing up!',
                                 extra_tags='font-weight-bold')

            messages.add_message(self.request,
                                 messages.INFO,
                                 'Use the your email address and the password you just created to login next time you visit.')

        return JsonResponse(response)


class UserPasswordResetView(PasswordResetView):
    template_name = 'user-management/password-reset.html'
    email_template_name = 'user-management/password-reset-email.txt'
    subject_template_name = 'user-management/password-reset-email-subject.txt'
    html_email_template_name = 'user-management/password-reset-email.html'
    success_url = reverse_lazy('done')


class UserPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'user-management/password-reset-confirm.html'
    success_url = reverse_lazy('complete')
    post_reset_login = True
    success_url = reverse_lazy('home')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user'] = self.user

        return context


class UserPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'user-management/password-reset-done.html'


def flush_cache(request, secret_key):
    if secret_key == CACHE_SECRET_KEY:
        cache.clear()
        status_code = 200
    else:
        status_code = 403

    return HttpResponse(status_code)
