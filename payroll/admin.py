from django.contrib import admin
from django.contrib.admin.models import LogEntry
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


class LogEntryAdmin(admin.ModelAdmin):
    readonly_fields = (
        'content_type',
        'user',
        'action_time',
        'object_id',
        'object_repr',
        'action_flag',
        'change_message'
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super(LogEntryAdmin, self).get_actions(request)
        del actions['delete_selected']
        return actions


admin.site.register(Employer, AdminEmployer)
admin.site.register(EmployerUniverse, AdminEmployerUniverse)
admin.site.register(EmployerTaxonomy, AdminEmployerTaxonomy)
admin.site.register(LogEntry, LogEntryAdmin)
