from django.contrib import admin
from payroll.models import Employer


class AdminEmployer(admin.ModelAdmin):
    ordering = ('name',)
    search_fields = ('name',)
    raw_id_fields = ('parent',)
    readonly_fields = ('slug', 'parent', 'vintage',)


admin.site.register(Employer, AdminEmployer)
