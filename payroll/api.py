from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly
from rest_framework.response import Response

from payroll.models import Unit, Department, Person
from payroll import serializers


class IndexViewSet(viewsets.ViewSet):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    serializer_class = serializers.IndexSerializer

    @method_decorator(cache_page(60 * 60 * 72))
    def list(self, request):
        '''
        TODO: Should this be retrieve? Want to keep API consistent across Index
        and entity-related views.
        '''
        try:
            data_year = request.query_params['data_year']
        except KeyError:
            return Response({})
        else:
            serializer = serializers.IndexSerializer(instance=data_year)
            return Response(serializer.data)


class ReadOnlyModelViewSetWithDataYear(viewsets.ReadOnlyModelViewSet):
    permission_classes = (IsAuthenticatedOrReadOnly,)
    lookup_field = 'slug'

    @method_decorator(cache_page(60 * 60 * 72))
    def retrieve(self, request, slug=None):
        try:
            data_year = request.query_params['data_year']
        except KeyError:
            return Response({})
        else:
            serializer = self.serializer_class(instance=self.get_object(),
                                               context={'data_year': data_year})
            return Response(serializer.data)


class UnitViewSet(ReadOnlyModelViewSetWithDataYear):
    serializer_class = serializers.UnitSerializer
    queryset = Unit.objects.all()


class DepartmentViewSet(ReadOnlyModelViewSetWithDataYear):
    serializer_class = serializers.DepartmentSerializer
    queryset = Department.objects.all()


class PersonViewSet(ReadOnlyModelViewSetWithDataYear):
    serializer_class = serializers.PersonSerializer
    queryset = Person.objects.all()
