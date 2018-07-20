from functools import partialmethod
from itertools import chain
import sys

from django.conf import settings
import pysolr

from payroll.models import Employer, Person


class EmployerSearch(object):
    model = Employer
    search_kwargs = {
        'rows': '99999999',
        'facet': 'true',
        'facet.interval': ['expenditure_d', 'headcount_i'],
        'f.expenditure_d.facet.interval.set': ['[0,500000)', '[500000,1500000)', '[1500000,5000000)', '[5000000,*)'],
        'f.headcount_i.facet.interval.set': ['[0,25)', '[25,100)', '[100,500)', '[500,*)'],
        'sort': 'expenditure_d desc',
    }


class UnitSearch(EmployerSearch):
    model = Employer
    search_kwargs = dict(EmployerSearch.search_kwargs, **{
        'facet.pivot': 'taxonomy_s_fct,size_class_s_fct',
    })


class DepartmentSearch(EmployerSearch):
    model = Employer
    search_kwargs = dict(EmployerSearch.search_kwargs, **{
        'facet.field': ['parent_s', 'universe_s'],
    })


class PersonSearch(object):
    model = Person
    search_kwargs = {
        'q.op': 'AND',
        'rows': '99999999',
        'facet': 'true',
        'facet.field': 'employer_ss',  # TO-DO: Is this the right way to facet multi-valued fields?
        'facet.interval': ['salary_d'],
        'f.salary_d.facet.interval.set': ['[0,25000)', '[25000,75000)', '[75000,150000)', '[150000,*)'],
    }


class PayrollSearchMixin(object):
    searcher = pysolr.Solr(settings.SOLR_URL)
    facets = {}

    # Cross-walk of URL parameters to Solr index fields
    param_index_map = {
            'expenditure': 'expenditure_d',
            'headcount': 'headcount_i',
            'taxonomy': 'taxonomy_s_fct',
            'size': 'size_class_s_fct',
            'parent': 'parent_s_fct',
            'universe': 'universe_s_fct',
            'employer': 'employer_ss_fct',
            'salary': 'salary_d',
        }

    # Fields to query as a numeric range
    range_fields = [
        'salary',
        'expenditure',
        'headcount'
    ]

    def search(self, params, *args):
        if params.get('entity_type'):
            entity_types = params.pop('entity_type').split(',')
        else:
            entity_types = ['unit', 'department', 'person']

        query_string = self._make_querystring(params)

        for entity_type in entity_types:
            yield from getattr(self, '_search_{}'.format(entity_type))(query_string, *args)

    def _search(self, entity_type, *args):
        search_kwargs = getattr(self._search_class(entity_type), 'search_kwargs')

        try:
            query_string, = args
        except ValueError:
            query_string, extra_search_kwargs = args
            search_kwargs.update(extra_search_kwargs)

        entity_filter = 'id:{}*'.format(entity_type)

        if query_string:
            query_string += ' AND {}'.format(entity_filter)
        else:
            query_string = entity_filter

        results = self.searcher.search(query_string, **search_kwargs)

        self.facets.update({entity_type: results.facets})

        # Retain ordering from Solr results when filtering the model objects.
        sort_order = [self._id_from_result(result) for result in results]

        model = getattr(self._search_class(entity_type), 'model')

        return sorted(model.objects.filter(id__in=sort_order),
                      key=lambda x: sort_order.index(str(x.id)))

    _search_unit = partialmethod(_search, 'unit')
    _search_department = partialmethod(_search, 'department')
    _search_person = partialmethod(_search, 'person')

    def _search_class(self, entity_type):
        '''
        Get a handle on the appropriate *Search class from a string of the
        class name.
        '''
        cls = '{}Search'.format(entity_type.title())
        return getattr(sys.modules[__name__], cls)

    def _id_from_result(self, result):
        '''
        Return model object ID from result id like "unit.<ID>.<REPORTING YEAR>"
        '''
        return result['id'].split('.')[1]

    def _make_querystring(self, params):
        range_params = {k: v for k, v in params.items()
                        if k.split('_')[0] in self.range_fields}

        value_params = {k: v for k, v in params.items()
                        if k not in range_params}

        query_parts = chain(self._value_q(value_params), self._range_q(range_params))

        return ' AND '.join(query_parts)

    def _value_q(self, params):
        query_parts = []

        for param, value in params.items():
            index_field = self.param_index_map.get(param, param)
            query_parts.append('{0}:{1}'.format(index_field, value))

        return query_parts

    def _range_q(self, params):
        query_parts = []

        range_format = '{field}:[{lower} TO {upper}]'

        for field in self.range_fields:
            # Only issue a range query if it at least one boundary came as a
            # parameter. Do this, because issuing both salary and expenditure
            # queries, even with asterisks, leads to 0 results, since none of
            # our documents include both a salary and an expenditure.
            if any(p.startswith(field) for p in params):
                fmt_kwargs = {
                    'field': self.param_index_map[field],
                    'lower': params.get('{}_above'.format(field), '*'),
                    'upper': params.get('{}_below'.format(field), '*'),
                }

                range_q = range_format.format(**fmt_kwargs)

                query_parts.append(range_q)

        return query_parts
