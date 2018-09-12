from django.contrib import admin
from django.core.management import call_command

from payroll.models import Employer, EmployerUniverse, EmployerTaxonomy


class AdminEmployer(admin.ModelAdmin):
    ordering = ('name',)
    search_fields = ('name',)
    raw_id_fields = ('parent',)
    readonly_fields = ('slug', 'parent', 'vintage',)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        call_command('build_solr_index', employer=obj.id)


class AdminEmployerUniverse(admin.ModelAdmin):
    pass


class AdminEmployerTaxonomy(admin.ModelAdmin):
    pass


admin.site.register(Employer, AdminEmployer)
admin.site.register(EmployerUniverse, AdminEmployerUniverse)
admin.site.register(EmployerTaxonomy, AdminEmployerTaxonomy)
