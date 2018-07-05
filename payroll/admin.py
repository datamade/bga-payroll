from django.contrib import admin
from payroll.models import Employer, EmployerUniverse


class AdminEmployer(admin.ModelAdmin):
    ordering = ('name',)
    search_fields = ('name',)
    raw_id_fields = ('parent',)
    readonly_fields = ('slug', 'parent', 'vintage',)


class AdminEmployerUniverse(admin.ModelAdmin):
    pass


admin.site.register(Employer, AdminEmployer)
admin.site.register(EmployerUniverse, AdminEmployerUniverse)
