import hashlib

from django.conf import settings
from django.contrib import admin
from django.contrib.admin.models import LogEntry
from django.core.management import call_command
from django.db import connection
from django.utils.encoding import iri_to_uri

from extra_settings.admin import SettingAdmin
from extra_settings.models import Setting

from payroll.models import Employer, EmployerUniverse, EmployerTaxonomy, \
    Person


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

        # Remove the homepage from the cache if the donate banner value has
        # changed.
        if obj.name == 'PAYROLL_SHOW_DONATE_BANNER' and change:
            try:
                cache_table = settings.CACHES['default']['LOCATION']
            except (TypeError, KeyError):
                # Don't do anything if there isn't a cache configured.
                return

            scheme = request.scheme
            host = request.get_host()
            homepage = '{0}://{1}/'.format(scheme, host)

            # Cache keys contain the hashed URL. Replicate that hash, so we can
            # delete keys containing the hash. See:
            # https://github.com/django/django/blob/12d6cae7c0401baa70c934f465bad856afecc847/django/utils/cache.py#L331
            homepage_hash = hashlib.md5(iri_to_uri(homepage).encode('ascii')).hexdigest()

            with connection.cursor() as cursor:
                delete = '''
                    DELETE FROM {cache_table}
                    WHERE cache_key LIKE '%{hash}%'
                    RETURNING cache_key
                '''.format(cache_table=cache_table, hash=homepage_hash)

                cursor.execute(delete)

                deleted_keys = [row[0] for row in cursor]

            if deleted_keys:
                print('Deleted keys "{}"'.format(deleted_keys))

            else:
                print('No keys corresponding to hash "{}"'.format(homepage_hash))


admin.site.register(Person, PersonAdmin)
admin.site.register(Employer, AdminEmployer)
admin.site.register(EmployerUniverse, AdminEmployerUniverse)
admin.site.register(EmployerTaxonomy, AdminEmployerTaxonomy)
admin.site.register(LogEntry, LogEntryAdmin)

admin.site.unregister(Setting)
admin.site.register(Setting, PayrollSettingAdmin)
