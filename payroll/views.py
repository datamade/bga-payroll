from itertools import chain

from django.core.cache import cache
from django.db import connection
from django.db.models import Max
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.conf import settings

from bga_database.chart_settings import BAR_HIGHLIGHT
from data_import.models import StandardizedFile
from payroll.charts import ChartHelperMixin
from payroll.models import Person, Unit, Department
from payroll.search import PayrollSearchMixin, FacetingMixin, \
    DisallowedSearchException
from payroll.serializers import PersonSerializer

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

    def get(self, request, *args, **kwargs):
        # Django creates a different cache entry for every combination of path
        # and URL parameters. To keep the number of cache entries low, redirect
        # requests without a data_year parameter to the URL with a parameter
        # for the latest year available. This will prevent duplicate entries
        # for effectively the same page (an employer page without a data_year
        # parameter, which would show the most recent year, and an employer
        # page with a data_year parameter for the most recent year).
        if not self.request.GET.get('data_year'):
            self.object = self.get_object()
            latest_year = self.data_years()[0]
            return redirect('{0}?data_year={1}'.format(request.path, latest_year))

        return super().get(request, *args, **kwargs)


class UnitView(EmployerView):
    model = Unit
    template_name = 'unit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        data_years = list(self.data_years())
        population_percentile = self.population_percentile()

        context.update({
            'data_years': data_years,
            'population_percentile': population_percentile,
            'size_class': self.object.size_class,
        })

        return context

    def data_years(self):
        return self.object.responding_agencies.order_by('-reporting_year')\
                                              .values_list('reporting_year', flat=True)

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

        data_years = self.data_years()
        context['data_years'] = data_years

        return context

    def data_years(self):
        data_years = self.object.get_salaries()\
            .distinct('vintage__standardized_file__reporting_year')\
            .values_list('vintage__standardized_file__reporting_year', flat=True)

        return sorted(list(data_years), reverse=True)


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

        most_recent_year = self.object.jobs.aggregate(
            most_recent_year=Max('salaries__vintage__standardized_file__reporting_year')
        )['most_recent_year']

        serializer = PersonSerializer(self.object, context={
            'data_year': most_recent_year
        })
        context.update(serializer.data)

        context['data_year'] = most_recent_year

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

    def _endpoint_from_result(self, result):
        return result['id'].split('.')[0]

    def get_queryset(self, *args, **kwargs):
        self.facets = {}

        base_params = {'name': self.request.GET['term']}

        extra_search_kwargs = {
            'expenditure_d': '[1000000 TO *]',
            'salary_d': '[100000 TO *]',
            'group': 'true',
            'group.field': 'slug',
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
                'label': result['name'],
                'value': result['name'],
            }

            result_type = self._endpoint_from_result(result)

            url = '{0}/{1}'.format(result_type, result['slug'])
            category = result_type.title()

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
