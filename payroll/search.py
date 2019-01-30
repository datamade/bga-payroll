from collections import OrderedDict
from functools import partialmethod
from itertools import chain
import re
import sys

from django.conf import settings
import pysolr

from payroll.models import Unit, Department, Person
from payroll.utils import employers_from_slugs


class DisallowedSearchException(Exception):
    pass


class EmployerSearch(object):
    search_kwargs = {
        'q.op': 'AND',
        'rows': '99999999',
        'facet': 'true',
        'facet.mincount': '3',
        'facet.interval': ['expenditure_d', 'headcount_i'],
        'f.expenditure_d.facet.interval.set': ['[0,500000)', '[500000,1500000)', '[1500000,5000000)', '[5000000,*)'],
        'f.headcount_i.facet.interval.set': ['[0,25)', '[25,100)', '[100,500)', '[500,*)'],
        'sort': 'expenditure_d desc',
    }


class UnitSearch(EmployerSearch):
    model = Unit
    search_kwargs = dict(EmployerSearch.search_kwargs, **{
        'facet.pivot': 'taxonomy_s_fct,size_class_s_fct',
    })


class DepartmentSearch(EmployerSearch):
    model = Department
    search_kwargs = dict(EmployerSearch.search_kwargs, **{
        'facet.field': ['parent_s_fct', 'universe_s_fct'],
    })


class PersonSearch(object):
    model = Person
    search_kwargs = {
        'q.op': 'AND',
        'rows': '99999999',
        'facet': 'true',
        'facet.mincount': '3',
        'facet.field': 'employer_ss_fct',
        'facet.interval': ['salary_d'],
        'f.salary_d.facet.interval.set': ['[0,25000)', '[25000,75000)', '[75000,150000)', '[150000,*)'],
        'sort': 'salary_d desc',
    }

    @classmethod
    def _format_results(cls, results):
        '''
        Return employer information as list of model objects, such that the
        last object is the person's employer and any preceding objects are the
        parents of that employer, e.g., [Unit, Department], [Unit].
        '''
        slugs = []

        for result in results.values():
            slugs += result['employer_ss']

        slug_map = employers_from_slugs(slugs)

        for result in results.values():
            result['employer_ss'] = [slug_map[e] for e in result['employer_ss']]

        return results


class PayrollSearchMixin(object):
    searcher = pysolr.Solr(settings.SOLR_URL)

    # Cross-walk of URL parameters to Solr index fields
    param_index_map = {
        'name': 'name',
        'entity_type': 'entity_type',
        'year': 'year',
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
        self.facets = {}

        required_params = {
            'name',
            'employer',
            'parent',
            'taxonomy',
            'universe',
        }

        if not set(params) & required_params:
            # we want to allow a search for top paid employees
            salary_above = params.get('salary_above')
            if not salary_above or int(salary_above) < 150000:
                raise DisallowedSearchException

        if params.get('name') and len(params['name']) < 3:
            raise DisallowedSearchException

        if params.get('entity_type'):
            entity_types = params.pop('entity_type').split(',')
        else:
            entity_types = ['unit', 'department', 'person']

        query_string = self._make_querystring(params)

        if query_string:
            for entity_type in entity_types:
                yield from getattr(self, '_search_{}'.format(entity_type))(query_string, *args)

        else:
            return None

    def _search(self, entity_type, *args):
        search_class = self._search_class(entity_type)

        # Don't edit the actual static attribute
        search_kwargs = search_class.search_kwargs.copy()

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

        if results:
            try:
                self.facets.update({entity_type: results.facets})
            except AttributeError:
                self.facets = {entity_type: results.facets}

        # Retain ordering from Solr results when filtering the model objects.
        sorted_results = OrderedDict([(self._id_from_result(r), r) for r in results])
        sort_order = list(sorted_results.keys())

        # If results contain Employer slugs, replace them with the appropriate
        # Unit and Department objects.
        try:
            sorted_results = search_class._format_results(sorted_results)
        except AttributeError:
            pass

        objects = []

        for o in sorted(search_class.model.objects.filter(id__in=sort_order),
                        key=lambda o: sort_order.index(o.id)):

            o.search_meta = sorted_results[o.id]
            objects.append(o)

        return objects

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
        return int(result['id'].split('.')[1])

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
            try:
                index_field = self.param_index_map[param]
            except KeyError:
                # Ignore invalid parameters
                continue

            if index_field == 'name':
                # Allow for terms to appear in any order
                value = '({})'.format(value)

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


class FacetingMixin(object):
    def parse_facets(self, facet_dict):
        '''
        Solr returns facets in a super weird way. This parses the various
        facet types into a standard [{'value': 'foo', 'count': 1}] format.
        '''
        out = {}

        for entity_type, facets in facet_dict.items():
            entity_facets = {}

            for facet_type, facet_values in facets.items():
                for facet, values in facet_values.items():
                    facet_counts = getattr(self, '_{}'.format(facet_type))(values)
                    formatted_facet_counts = self._format_facets(facet_counts)
                    entity_facets[facet] = sorted(formatted_facet_counts,
                                                  key=lambda x: x['count'],
                                                  reverse=True)

            out[entity_type] = entity_facets

        return out

    def _format_facets(self, facet_counts):
        '''
        When facet values are Unit or Department slugs, return the corresponding
        objects for use in the templates.

        :facet_counts is a list of dictionaries containing the values and
        counts for a given facet, e.g., [{'value': 'some-slug', 'count': 99},
        ...]. If one value is a slug, they are all slugs. Likewise, if one
        value is not a slug, none of them are.
        '''
        slugs = [f['value'] for f in facet_counts]

        # Match slugs formatted like 'winnetka-park-district-e8d69a12', i.e.,
        # lowercase letters joined by dashes, followed by the first chunk of a UUID
        if slugs and re.match('[a-z0-9_-]*-[0-9a-f]{8}', slugs[0]):
            employers = employers_from_slugs(slugs)

            for f in facet_counts:
                f['value'] = employers[f['value']]

        return facet_counts

    def _facet_fields(self, values):
        '''
        Parse facet formatted like ['foo', 1, 'bar', 2]
        '''
        out = []

        for i, value in enumerate(values):
            if i % 2 == 0:
                count = values[i + 1]
                out.append({
                    'value': value,
                    'count': count,
                })

        return out

    def _facet_intervals(self, values):
        '''
        Parse facet formatted like {'interval': 'count'}
        '''
        return [{'value': k, 'count': v} for k, v in values.items()]

    def _facet_pivot(self, values):
        '''
        Parse facet formatted like {
            'count': 'foo',
            'value': 'foo',
            'pivot': {
                'count': 'foo',
                'value': 'foo'
            }
        }

        N.b., currently only handles one level of pivoting.
        '''
        out = []

        for count in values:
            value = {
                'value': count['value'],
                'count': count['count'],
            }

            if count.get('pivot'):
                pivot = []

                for pivot_count in count['pivot']:
                    pivot.append({
                        'value': pivot_count['value'],
                        'count': pivot_count['count'],
                    })

                value['pivot'] = pivot

            out.append(value)

        return out
