# payroll/search_postgres.py
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


class PostgresSearchMixin:
    """Base search functionality using Postgres FTS"""
    
    def __init__(self):
        self.facets = {}
    
    def search(self, params, pagesize, **extra_kwargs):
        """Main search entry point"""
        if params.get('entity_type'):
            entity_types = params.pop('entity_type').split(',')
        else:
            entity_types = ['unit', 'department', 'person']
                    
        page = self._get_page_number(params)
        query_term = params.get('name', '')
        
        # Get latest year if not specified
        year = params.get('year')
        if not year:
            year = StandardizedFile.objects.aggregate(
                latest_year=models.Max('reporting_year')
            )['latest_year']
            params['year'] = year
        
        # Build search results for each entity type
        all_results = []
        total_count = 0
        
        for entity_type in entity_types:
            queryset = self._get_base_queryset(entity_type, params, query_term)
            count = queryset.count()
            total_count += count
            
            # Store facet data
            self._collect_facets(entity_type, queryset, params)
            
            all_results.append((entity_type, queryset, count))
        
        # Combine and paginate results
        combined_results = self._combine_results(all_results, page, pagesize)
        return combined_results
        
        print(all_results)
        
        return PostgresPaginatedResults(combined_results, total_count)
    
    def _get_page_number(self, params):
        """Extract and validate page number"""
        try:
            page = int(params.get('page', 1))
            if page < 1:
                raise ValueError
            return page
        except (ValueError, TypeError):
            return 1
    
    def _get_base_queryset(self, entity_type, params, query_term):
        """Get base queryset for an entity type with all filters applied"""
        if entity_type == 'unit':
            return self._search_units(params, query_term)
        elif entity_type == 'department':
            return self._search_departments(params, query_term)
        elif entity_type == 'person':
            return self._search_persons(params, query_term)
        else:
            return self._empty_queryset()
    
    def _search_units(self, params, query_term):
        """Search units with FTS and filters"""
        queryset = Unit.objects.select_related('taxonomy').prefetch_related('population')
        
        # Add year filter
        if params.get('year'):
            queryset = queryset.filter(
                vintage__standardized_file__reporting_year=params['year']
            )
        
        # Full text search on name
        if query_term:
            search_vector = SearchVector('name', weight='A') + \
                           SearchVector('aliases__name', weight='B')
            search_query = SearchQuery(query_term)
            
            queryset = queryset.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query).order_by('-rank', 'name')
        else:
            queryset = queryset.order_by('name')
        
        # Apply filters
        queryset = self._apply_unit_filters(queryset, params)
        
        return queryset.distinct()
    
    def _search_departments(self, params, query_term):
        """Search departments with FTS and filters"""
        queryset = Department.objects.select_related('parent', 'universe')
        
        # Add year filter
#        if params.get('year'):
#            queryset = queryset.filter(
#                vintage__standardized_file__reporting_year=params['year']
#            )
        
        # Full text search
        if query_term:
            # Search in department name and parent name
            search_vector = SearchVector('search_name', weight='A') + \
                            SearchVector('aliases__name', weight='B')
            search_query = SearchQuery(query_term)
            
            queryset = queryset.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query).order_by('-rank', 'name')
        else:
            queryset = queryset.order_by('parent__name', 'name')
        
        # Apply filters
        queryset = self._apply_department_filters(queryset, params)
        
        return queryset.distinct()
    
    def _search_persons(self, params, query_term):
        """Search persons with FTS and filters"""
        queryset = Person.objects#.select_related('most_recent_job__position__employer')
        
        # Add year filter
        if params.get('year'):
            queryset = queryset.filter(
                jobs__vintage__standardized_file__reporting_year=params['year']
            )
        
        # Full text search on name
        if query_term:
            search_vector = SearchVector('first_name', weight='A') + \
                           SearchVector('last_name', weight='A')
            search_query = SearchQuery(query_term)
            
            queryset = queryset.annotate(
                search=search_vector,
                rank=SearchRank(search_vector, search_query)
            ).filter(search=search_query).order_by('-rank', 'last_name', 'first_name')
        else:
            queryset = queryset.order_by('last_name', 'first_name')
        
        # Apply filters
        queryset = self._apply_person_filters(queryset, params)
        
        return queryset.distinct()
    
    def _apply_unit_filters(self, queryset, params):
        """Apply unit-specific filters"""
        if params.get('taxonomy'):
            queryset = queryset.filter(taxonomy__entity_type=params['taxonomy'])
        
        if params.get('size'):
            # You'll need to implement size_class as a property or computed field
            # This is a simplified version - you might want to annotate this
            pass
        
        # Expenditure and headcount ranges
        queryset = self._apply_range_filters(queryset, params, 'unit')
        
        return queryset
    
    def _apply_department_filters(self, queryset, params):
        """Apply department-specific filters"""
        if params.get('parent'):
            queryset = queryset.filter(parent__slug=params['parent'])
        
        if params.get('universe'):
            queryset = queryset.filter(universe__name=params['universe'])
        
        queryset = self._apply_range_filters(queryset, params, 'department')
        
        return queryset
    
    def _apply_person_filters(self, queryset, params):
        """Apply person-specific filters"""
        if params.get('employer'):
            employer_slugs = params['employer'].split(',')
            queryset = queryset.filter(
                Q(jobs__position__employer__slug__in=employer_slugs) |
                Q(jobs__position__employer__parent__slug__in=employer_slugs)
            )
        
        # Salary range filter
        if params.get('salary_above') or params.get('salary_below'):
            salary_filter = Q()
            
            if params.get('salary_above'):
                salary_filter &= Q(
                    jobs__salaries__amount__gte=params['salary_above']
                )
            
            if params.get('salary_below'):
                salary_filter &= Q(
                    jobs__salaries__amount__lte=params['salary_below']
                )
            
            queryset = queryset.filter(salary_filter)
        
        return queryset
    
    def _apply_range_filters(self, queryset, params, entity_type):
        """Apply numeric range filters (expenditure, headcount, etc.)"""
        # This would need to be implemented based on your specific data structure
        # You might need to add computed fields or annotations for these
        return queryset
    
    def _combine_results(self, all_results, page, pagesize):
        """Combine results from different entity types and paginate"""
        # Flatten all results maintaining the order
        combined = []
        
        for entity_type, queryset, count in all_results:
            for item in queryset:
                combined.append(item)
                
        return [{"id": ".".join([type(r).__name__.lower(), str(r.id)]), "name": r.search_name, "slug": r.slug, "year": r.reporting_year, "expenditure_d": 10, "headcount_i": 10} for r in combined]
        
        # Simple pagination - you might want something more sophisticated
        paginator = Paginator(combined, pagesize)
        return paginator.get_page(page)
    
    def _collect_facets(self, entity_type, queryset, params):
        """Collect facet data for search results"""
        if entity_type == 'unit':
            self._collect_unit_facets(queryset)
        elif entity_type == 'department':
            self._collect_department_facets(queryset)
        elif entity_type == 'person':
            self._collect_person_facets(queryset)
    
    def _collect_unit_facets(self, queryset):
        """Collect facets for unit search"""
        # Taxonomy facets
        taxonomy_facets = queryset.values('taxonomy__entity_type')\
                                 .annotate(count=models.Count('id'))\
                                 .order_by('-count')
        
        self.facets.setdefault('unit', {})['taxonomy_s_fct'] = [
            {'value': item['taxonomy__entity_type'], 'count': item['count']}
            for item in taxonomy_facets if item['taxonomy__entity_type']
        ]
    
    def _collect_department_facets(self, queryset):
        """Collect facets for department search"""
        # Parent unit facets
        parent_facets = queryset.values('parent__name', 'parent__slug')\
                               .annotate(count=models.Count('id'))\
                               .order_by('-count')
        
        self.facets.setdefault('department', {})['parent_s_fct'] = [
            {'value': item['parent__slug'], 'count': item['count'], 'name': item['parent__name']}
            for item in parent_facets if item['parent__name']
        ]
        
        # Universe facets
        universe_facets = queryset.values('universe__name')\
                                 .annotate(count=models.Count('id'))\
                                 .order_by('-count')
        
        self.facets.setdefault('department', {})['universe_s_fct'] = [
            {'value': item['universe__name'], 'count': item['count']}
            for item in universe_facets if item['universe__name']
        ]
    
    def _collect_person_facets(self, queryset):
        """Collect facets for person search"""
        # Employer facets
        employer_facets = queryset.values(
            'jobs__position__employer__name',
            'jobs__position__employer__slug'
        ).annotate(count=models.Count('id')).order_by('-count')
        
        self.facets.setdefault('person', {})['employer_ss_fct'] = [
            {
                'value': item['jobs__position__employer__slug'], 
                'count': item['count'],
                'name': item['jobs__position__employer__name']
            }
            for item in employer_facets if item['jobs__position__employer__name']
        ]
    
    def _empty_queryset(self):
        """Return empty queryset for invalid entity types"""
        return Unit.objects.none()


class PostgresPaginatedResults(Paginator):
    """Replacement for LazyPaginatedResults that works with Django querysets"""
    
    def __init__(self, page_obj, total_count):
        self.page_obj = page_obj
        self.total_count = total_count
    
    def __iter__(self):
        return iter(self.page_obj)
    
    def __len__(self):
        return self.total_count
    
    def count(self):
        return self.total_count
