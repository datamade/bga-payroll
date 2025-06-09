from django.db.models import Sum
from rest_framework import serializers

from .models import EmployerSearchIndex, PersonSearchIndex
from payroll.models import Person


class EmployerSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(source="instance.slug")
    name = serializers.CharField(source="instance.name")
    search_name = serializers.CharField(source="instance.search_name")
    parent = serializers.SlugRelatedField(read_only=True, slug_field="slug", source="instance.parent")
    endpoint = serializers.SerializerMethodField()
    
    class Meta:
        model = EmployerSearchIndex
        fields = ("slug", "name", "search_name", "expenditure", "headcount", "reporting_year", "parent", "endpoint",)
    
    def get_endpoint(self, obj):
        return "department" if obj.instance.parent_id else "unit"


class PersonSerializer(serializers.ModelSerializer):
    employer = serializers.CharField(source="most_recent_job.position.employer", read_only=True)
    title = serializers.CharField(source="most_recent_job.position.title", read_only=True)
    salary = serializers.CharField(source="most_recent_job.salaries.last.amount", read_only=True)
    endpoint = serializers.SerializerMethodField()
    
    class Meta:
        model = Person
        fields = ("slug", "first_name", "last_name", "employer", "title", "salary", "endpoint")
        
    def get_endpoint(self, obj):
        return "person"