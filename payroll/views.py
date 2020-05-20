from itertools import chain
import json

from django.core.cache import cache
from django.db import connection
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.conf import settings

from bga_database.chart_settings import BAR_HIGHLIGHT
from data_import.models import StandardizedFile
from payroll.charts import ChartHelperMixin
from payroll.models import Person, Salary, Unit, Department
from payroll.search import PayrollSearchMixin, FacetingMixin, \
    DisallowedSearchException

from bga_database.local_settings import CACHE_SECRET_KEY


class IndexView(TemplateView, ChartHelperMixin):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        data_years = StandardizedFile.objects.distinct('reporting_year')\
                                             .order_by('-reporting_year')\
                                             .values_list('reporting_year', flat=True)

        context['data_years'] = list(data_years)

        return context


class UserGuideView(TemplateView):
    template_name = 'user_guide.html'


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


class EmployerView(DetailView, ChartHelperMixin):
    context_object_name = 'entity'


class UnitView(EmployerView):
    model = Unit
    template_name = 'unit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        data_years = self.object.responding_agencies.order_by('-reporting_year')\
                                                    .values_list('reporting_year', flat=True)

        context.update({
            'population_percentile': self.population_percentile(),
            'size_class': self.object.size_class,
            'data_years': list(data_years),
        })

        return context

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


class DepartmentView(EmployerView):
    model = Department
    template_name = 'department.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        data_years = self.object.get_salaries()\
            .distinct('vintage__standardized_file__reporting_year')\
            .values_list('vintage__standardized_file__reporting_year', flat=True)

        data_years = sorted(list(data_years), reverse=True)

        context['data_years'] = data_years

        return context


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
        current_job = self.object.most_recent_job
        current_salary = current_job.salaries.get()

        bp = Coalesce("amount", 0)
        ep = Coalesce("extra_pay", 0)

        fellow_job_holders = Salary.objects.exclude(job__person=self.object)\
                                           .select_related('job__person', 'job__position')\
                                           .filter(job__position=self.object.most_recent_job.position)\
                                           .annotate(total_pay=bp + ep)\
                                           .order_by('-total_pay')

        employer_percentile = current_salary.employer_percentile
        like_employer_percentile = current_salary.like_employer_percentile

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

        salary_data = current_job.position.employer.employee_salaries
        binned_salary_data = self.bin_salary_data(salary_data)

        source_file = self.object.source_file(settings.DATA_YEAR)

        if source_file:
            source_link = source_file.url
        else:
            source_link = None

        context.update({
            'data_year': settings.DATA_YEAR,
            'current_job': current_job,
            'all_jobs': all_jobs,
            'current_salary': self.salary_amount,
            'current_employer': current_employer,
            'employer_type': employer_type,
            'employer_salary_json': json.dumps(binned_salary_data),
            'employer_percentile': employer_percentile,
            'like_employer_percentile': like_employer_percentile,
            'salaries': fellow_job_holders,
            'source_link': source_link,
            'noindex': self.salary_amount < 30000 or self.object.noindex,
        })

        return context


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

        authenticated = self.request.COOKIES.get(settings.SALSA_AUTH_COOKIE_NAME)
        under_limit = self.request.session['search_count'] <= settings.SEARCH_LIMIT

        if authenticated or under_limit:
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


def flush_cache(request, secret_key):
    if secret_key == CACHE_SECRET_KEY:
        cache.clear()
        status_code = 200
    else:
        status_code = 403

    return HttpResponse(status_code)
