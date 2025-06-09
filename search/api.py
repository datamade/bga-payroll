from django.contrib.postgres.search import SearchVector, SearchQuery, SearchRank
from django.db.models import Case, When, CharField, Value, Q

from rest_framework import filters
from rest_framework.generics import ListAPIView

from .serializers import EmployerSerializer, PersonSerializer
from payroll.models import Person
from .models import EmployerSearchIndex


class SearchView(ListAPIView):
    model = None
    search_fields = ()

    def get_queryset(self):
        return self.model.objects.all()
    
    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
        print(queryset)
        
        query = self.request.GET.get('name')
        year = self.request.GET.get("year", 2020)
        
        search_vector = None
        weights = ("A", "B", "C", "D")
        
        for weight_index, field in enumerate(self.search_fields):
            field_vector = SearchVector(field, weight=weights[weight_index])
            if search_vector is None:
                search_vector = field_vector
            else:
                search_vector.bitand(field_vector)
            
        search_query = SearchQuery(query)
        search_rank = SearchRank(search_vector, search_query)

        return queryset.annotate(
            search=search_vector,
            rank=search_rank,
        ).filter(search=search_query, reporting_year=year)


class EmployerSearchView(SearchView):
    model = EmployerSearchIndex
    serializer_class = EmployerSerializer
    search_fields = ("instance__search_name", "instance__aliases__name")

    def filter_queryset(self, queryset):
        queryset = super().filter_queryset(queryset)
                
        return queryset.annotate(
            entity_type=Case(
                When(
                    instance__parent__isnull=False, 
                    then=Value("department")
                ),
                When(
                    instance__parent__isnull=True,
                    then=Value("unit")
                ),
                output_field=CharField()
            )
        ).order_by( "-entity_type", "-expenditure", '-rank') 
    

class PersonSearchView(SearchView):
    model = Person
    serializer_class = PersonSerializer
    search_fields = ("last_name", "first_name",)
    
    def filter_queryset(self, queryset):        
        query = self.request.GET.get("name")
        employer = self.request.GET.get("employer")
        
        if not any([query, employer]):
            return []
        
        if query:
            search_vector = None
            weights = ("A", "B", "C", "D")
        
            for weight_index, field in enumerate(self.search_fields):
                field_vector = SearchVector(field, weight=weights[weight_index])
                if search_vector is None:
                    search_vector = field_vector
                else:
                    search_vector.bitand(field_vector)
                
                search_query = SearchQuery(query)
                search_rank = SearchRank(search_vector, search_query)
                
                queryset = queryset.annotate(
                    search=search_vector,
                    rank=search_rank,
                ).filter(search=search_query)

        if employer:
            queryset = queryset.filter(
                Q(jobs__position__employer__slug=employer) | Q(jobs__position__employer__parent__slug=employer)
            )

        return queryset
