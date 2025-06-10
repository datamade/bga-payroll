from django.db.models import Sum
from rest_framework import serializers

from .models import EmployerSearchIndex, PersonSearchIndex
from payroll.models import Person


class EmployerSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(source="instance.slug")
    name = serializers.CharField(source="instance.name")
    parent = serializers.SlugRelatedField(read_only=True, slug_field="slug", source="instance.parent")
    endpoint = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployerSearchIndex
        fields = ("slug", "name", "search_name", "expenditure", "headcount", "reporting_year", "parent", "endpoint",)
    
    def get_endpoint(self, obj):
        return "department" if obj.instance.parent_id else "unit"


class PersonSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="search_name", read_only=True)
    employer = serializers.SlugRelatedField(read_only=True, slug_field="slug")
    title = serializers.CharField(source="search_title", read_only=True)
    total_pay = serializers.CharField(read_only=True)
    endpoint = serializers.SerializerMethodField()
    
    class Meta:
        model = PersonSearchIndex
        fields = ("name", "employer", "title", "total_pay", "reporting_year", "endpoint")
        
    def get_endpoint(self, obj):
        return "person"