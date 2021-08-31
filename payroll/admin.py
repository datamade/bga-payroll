from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.core.cache import caches, InvalidCacheBackendError
from django.core.management import call_command
from django.db import transaction

from extra_settings.admin import SettingAdmin
from extra_settings.models import Setting

from payroll.models import Employer, EmployerUniverse, EmployerTaxonomy, \
    Person, EmployerAlias


class AdminEmployer(admin.ModelAdmin):
    ordering = ('name',)
    search_fields = ('name',)
    raw_id_fields = ('parent',)
    readonly_fields = ('slug', 'parent', 'vintage',)

    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            super().save_model(request, obj, form, change)

            if change:
                # Get or create an alias for the given employer. Don't filter
                # on preferred in case someone is changing the name to an alias
                # we already have on hand.
                alias, _ = EmployerAlias.objects.get_or_create(employer=obj, name=obj.name)

                # Mark the given alias as preferred, marking all other aliases
                # for the given employer as not preferred.
                alias.preferred = True
                alias.save()

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


class PersonAdmin(admin.ModelAdmin):
    search_fields = ('first_name', 'last_name')
    list_display = ('most_recent_job',)
    readonly_fields = ('first_name', 'last_name', 'most_recent_job', 'slug',)
    exclude = ('vintage',)

    def most_recent_job(self, obj):
        return obj.most_recent_job


class PayrollSettingAdmin(SettingAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)

        if change:
            try:
                cache = caches['vary_on_setting']

            except InvalidCacheBackendError:
                print('vary_on_setting cache does not exist')

            else:
                cache.clear()
                print('Cleared vary_on_setting cache')


admin.site.register(Person, PersonAdmin)
admin.site.register(Employer, AdminEmployer)
admin.site.register(EmployerUniverse, AdminEmployerUniverse)
admin.site.register(EmployerTaxonomy, AdminEmployerTaxonomy)
admin.site.register(LogEntry, LogEntryAdmin)

admin.site.unregister(Setting)
admin.site.register(Setting, PayrollSettingAdmin)
