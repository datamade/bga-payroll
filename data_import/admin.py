import datetime

from django.contrib import admin
from django.db.models import Q

from data_import.models import SourceFile, StandardizedFile, Upload, \
    RespondingAgency


class AdminRespondingAgency(admin.ModelAdmin):
    search_fields = ('name',)
    fields = ('name',)
    ordering = ('name',)

    def get_model_perms(self, request):
        '''
        A hack to hide the standalone RespondingAgency from the admin.
        '''
        return {}


class AdminSourceFile(admin.ModelAdmin):
    model = SourceFile

    fields = (
        'source_file',
        'responding_agency',
        'reporting_year',
        'reporting_period_start_date',
        'reporting_period_end_date',
    )

    autocomplete_fields = ['responding_agency']

    search_fields = ('responding_agency__name', 'reporting_year',)

    def get_readonly_fields(self, request, obj=None):
        '''
        Disable editing of responding agency for existing source files.
        '''
        if obj:
            return ['responding_agency']
        else:
            return []

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        '''
        Only show responding agencies without a source file.
        '''
        if db_field.name == 'responding_agency':
            kwargs['queryset'] = RespondingAgency.objects\
                                                 .exclude(source_files__reporting_year=2017)\
                                                 .order_by('name')

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        obj.upload = Upload.objects.create(created_by=request.user)

        # Auto-fill reporting period dates, if they were not provided
        if not obj.reporting_period_start_date:
            obj.reporting_period_start_date = datetime.datetime(obj.reporting_year, 1, 1)

        if not obj.reporting_period_end_date:
            obj.reporting_period_end_date = datetime.datetime(obj.reporting_year, 12, 31)

        obj = self._link_standardized_file(obj)

        super().save_model(request, obj, form, change)

    def _link_standardized_file(self, obj):
        '''
        Identify the StandardizedFile object for the given year and responding
        agency, if it exists. Note: Standardized data is linked to pre-existing
        source files on import.
        '''
        in_reporting_year = Q(reporting_year=obj.reporting_year)
        of_responding_agency = Q(responding_agencies=obj.responding_agency)

        s_file = StandardizedFile.objects.filter(in_reporting_year & of_responding_agency).get()

        if s_file:
            obj.standardized_file = s_file

        return obj


admin.site.register(SourceFile, AdminSourceFile)
admin.site.register(RespondingAgency, AdminRespondingAgency)
