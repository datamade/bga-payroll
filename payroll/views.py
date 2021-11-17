import datetime
from itertools import chain
import csv

from django.core.cache import caches
from django.core.exceptions import ObjectDoesNotExist, MultipleObjectsReturned
from django.db.models import Max
from django.http import JsonResponse, HttpResponse, \
    HttpResponsePermanentRedirect, HttpResponseGone, StreamingHttpResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.generic.base import TemplateView
from django.views.generic.detail import DetailView
from django.views.generic.list import ListView
from django.conf import settings
from extra_settings.models import Setting
import feedparser
import bleach

from bga_database.chart_settings import BAR_HIGHLIGHT
from bga_database.local_settings import CACHE_SECRET_KEY

from data_import.models import StandardizedFile

from payroll.charts import ChartHelperMixin
from payroll.models import Person, Unit, Department, Employer
from payroll.search import PayrollSearchMixin, FacetingMixin, \
    DisallowedSearchException
from payroll.serializers import PersonSerializer


class IndexView(TemplateView, ChartHelperMixin):
    template_name = 'index.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        data_years = StandardizedFile.objects.distinct('reporting_year')\
                                             .order_by('-reporting_year')\
                                             .values_list('reporting_year', flat=True)

        context['data_years'] = list(data_years)

        context['show_donate_banner'] = Setting.get('PAYROLL_SHOW_DONATE_BANNER', False)

        donate_text = Setting.get('DONATE_MESSAGE', '')
        context['donate_message'] = bleach.clean(donate_text,
                                                 tags=['p', 'strong', 'a'],
                                                 attributes={'a': ['href', 'target'], '*': ['class', 'style']})

        return context


class UserGuideView(TemplateView):
    template_name = 'user_guide.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        try:
            department_slug = Department.objects.get(name__iexact='city of chicago department of police').slug
        except Department.DoesNotExist:
            department_slug = Department.objects.first().slug

        context['department_slug'] = department_slug

        return context


def error(request, error_code):
    return render(request, '{}.html'.format(error_code))


class RedirectDispatchMixin:
    def dispatch(self, request, *args, **kwargs):
        slug = kwargs['slug']

        try:
            entity = self.model.objects.get(slug=slug)

        except ObjectDoesNotExist:
            entity = None

        else:
            response = super().dispatch(request, *args, **kwargs)

        if not entity:
            short_slug = '-'.join(slug.split('-')[:-1])

            try:
                entity = self.model.objects.get(slug__startswith=short_slug)

            except (ObjectDoesNotExist, MultipleObjectsReturned):
                response = HttpResponseGone()

            else:
                redirect_url = reverse(entity.endpoint, args=[entity.slug])
                response = HttpResponsePermanentRedirect(redirect_url)

        return response


class EmployerView(RedirectDispatchMixin, DetailView, ChartHelperMixin):
    context_object_name = 'entity'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        context['authenticated'] = self.request.COOKIES.get(settings.SALSA_AUTH_COOKIE_NAME)

        return context


class UnitView(EmployerView):
    model = Unit
    template_name = 'unit.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        data_years = list(self.data_years())

        context.update({
            'data_years': data_years,
            'size_class': self.object.size_class,
        })

        return context

    def data_years(self):
        return self.object.responding_agencies.order_by('-reporting_year')\
                                              .values_list('reporting_year', flat=True)


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


class PersonView(RedirectDispatchMixin, DetailView, ChartHelperMixin):
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


class PsuedoBuffer:
    """An object that implements just the write method of the file-like
    interface.
    """

    def write(self, value):
        """Write the value by returning it, instead of storing in a buffer."""
        return value


class DownloadView(TemplateView):
    def get(self, request, *args, **kwargs):
        slug = request.GET.get('employer')
        year = request.GET.get('year')
        employer = Employer.objects.get(slug=slug)
        employer_salaries = employer.get_salaries(year=year).select_related(
            'job',
            'job__person',
            'job__position',
            'job__position__employer',
            'job__position__employer__parent'
        )

        buffer = PsuedoBuffer()
        headers = ['name',
                   'unit',
                   'department',
                   'title',
                   'tenure',
                   'salary',
                   'other']
        dict_writer = csv.DictWriter(f=buffer, fieldnames=headers)

        def row_generator():
            for salary in employer_salaries:
                name_kwargs = {
                    'first_name': salary.job.person.first_name,
                    'last_name': salary.job.person.last_name
                }
                name = '{first_name} {last_name}'.format(**name_kwargs)

                start_date = salary.job.start_date.strftime('%m/%d/%Y') if salary.job.start_date else ''  # noqa

                yield {
                    'name': name,
                    'unit': salary.job.position.employer.parent,
                    'department': salary.job.position.employer,
                    'title': salary.job.position.title,
                    'tenure': start_date,
                    'salary': salary.amount,
                    'other': salary.extra_pay
                }

        # DictWriter.writeheader() doesn't work in python 3.5,
        # so this workaround adds the header from dict_writer.fieldnames.
        flat_writer = csv.writer(buffer)
        rows = chain([flat_writer.writerow(dict_writer.fieldnames)],
                     (dict_writer.writerow(row) for row in row_generator()))

        response = StreamingHttpResponse(
            rows,
            content_type='text/csv'
        )

        filename = '{employer}-{year}.csv'.format(employer=employer.name, year=year)  # noqa
        response['Content-Disposition'] = 'attachment; filename="{}"'.format(filename)  # noqa
        return response


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

        data_years = StandardizedFile.objects.distinct('reporting_year')\
                                             .order_by('-reporting_year')\
                                             .values_list('reporting_year', flat=True)

        context['data_years'] = list(data_years)

        context['captcha_site_key'] = getattr(settings, 'RECAPTCHA_PUBLIC_KEY')

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
        # results = self.get_queryset(*args, **kwargs)
        results = []

        return JsonResponse(results, safe=False)


class StoryFeed(ListView):

    response_class = JsonResponse
    rss_feed_url = 'https://www.bettergov.org/feed/1555/rss.xml'
    n_entries = 4

    def render_to_response(self, context, **response_kwargs):
        return JsonResponse(self.get_queryset())

    def _get_date(self, date_parts):
        date = datetime.date(*date_parts[:3])
        return datetime.datetime.strftime(date, '%B %d, %Y')

    def get_queryset(self):
        try:
            feed = feedparser.parse(self.rss_feed_url)

        except Exception as e:
            return {
                'status_code': 500,
                'message': str(e),
            }

        else:
            return {
                'status_code': 200,
                'entries': [{
                    'title': story['title'],
                    'summary': story['summary'],
                    'date': self._get_date(story['published_parsed']),
                    'link': story['link'],
                } for story in feed['entries'][:4]]
            }


def flush_cache(request, secret_key):
    if secret_key == CACHE_SECRET_KEY:
        for cache_label in settings.CACHES.keys():
            caches[cache_label].clear()

        status_code = 200
    else:
        status_code = 403

    return HttpResponse(status_code)
