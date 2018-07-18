from functools import partialmethod
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
        'facet.field': 'parent_s',
    })

class PersonSearch(object):
    model = Person
    search_kwargs = {
        'rows': '99999999',
        'facet': 'true',
        'facet.field': 'employer_ss',  # TO-DO: Is this the right way to facet multi-valued fields?
        'facet.interval': ['salary_d'],
        'f.salary_d.facet.interval.set': ['[0,25000)', '[25000,75000)', '[75000,150000)', '[150000,*)'],
    }

class PayrollSearchMixin(object):
    searcher = pysolr.Solr(settings.SOLR_URL)
    facets = {}

    def search(self, params):
        if params.get('entity_type'):
            entity_types = params.pop('entity_type').split(',')
        else:
            entity_types = ['unit', 'department', 'person']

        query_string = self._make_querystring(params)

        for entity_type in entity_types:
            yield from getattr(self, '_search_{}'.format(entity_type))(query_string)

    def _search(self, entity_type, *args):
        search_kwargs = getattr(self._search_class(entity_type), 'search_kwargs')

        query_string, = args

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
        cls = '{}Search'.format(entity_type.title())
        return getattr(sys.modules[__name__], cls)

    def _id_from_result(self, result):
        '''
        Return model object ID from result id like "unit.<ID>.<REPORTING YEAR>"
        '''
        return result['id'].split('.')[1]

    def _make_querystring(self, params):
        query_parts = []

        param_index_map = {
            'parent': 'parent_s_fct',
            'employer': 'employer_ss_fct',
        }

        for param, value in params.items():
            if param == 'expenditure':
                match = re.match(r'\[(?P<lower_bound>\d+),(?P<upper_bound>\d+)\)', params['expenditure'])

                interval = 'expenditure_d:[{0} TO {1}]'.format(match.group('lower_bound'),
                                                               match.group('upper_bound'))
                query_parts.append(interval)

            else:
                index_field = param_index_map.get(param, param)
                query_parts.append('{0}:{1}'.format(index_field, value))

        return ' AND '.join(query_parts)
