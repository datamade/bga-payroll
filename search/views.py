from django.shortcuts import render
import re
from django.contrib.postgres.search import (
    SearchVector, SearchQuery, SearchRank,
    TrigramSimilarity
)
from django.contrib.postgres.aggregates import StringAgg
from django.db.models import Q, F, Value, CharField, DecimalField, IntegerField
from django.db.models.functions import Cast, Coalesce
from django.core.paginator import Paginator
from django.db import models

from data_import.models import StandardizedFile
from payroll.models import Unit, Department, Person, Salary

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
from payroll.search_postgres import PostgresSearchMixin
from payroll.serializers import PersonSerializer


class SearchView(ListView):
    template_name = 'search_results.html'
    context_object_name = 'results'

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

        authenticated = self.request.COOKIES.get(settings.MAILCHIMP_AUTH_COOKIE_NAME)
        under_limit = self.request.session['search_count'] <= settings.SEARCH_LIMIT
        
        entity_type = self.request.GET.get("entity_type", "unit")
        from .api import EmployerSearchView, PersonSearchView

        if authenticated or under_limit:
            try:
                self.allowed = True
                view_cls = PersonSearchView if entity_type == "person" else EmployerSearchView
                results = view_cls.as_view()(self.request).data

            except Exception as e:
                self.allowed = True
                results = []
        else:
            self.allowed = False
            results = []

        return results

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)

        context['allowed'] = self.allowed
        context['facets'] = {}
        context['search_limit'] = settings.SEARCH_LIMIT

        data_years = StandardizedFile.objects.distinct('reporting_year')\
                                             .order_by('-reporting_year')\
                                             .values_list('reporting_year', flat=True)

        context['data_years'] = list(data_years)

        context['captcha_site_key'] = getattr(settings, 'RECAPTCHA_PUBLIC_KEY')

        return context


class EntityLookup(ListView, PostgresSearchMixin):
    """
    TODO: Fix this
    """

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
