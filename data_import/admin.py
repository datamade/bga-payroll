import datetime

from django import forms
from django.contrib import admin
from django.core.exceptions import ValidationError

from data_import.models import SourceFile, Upload, RespondingAgency, StandardizedFile
from data_import.forms import UploadForm


class AdminRespondingAgency(admin.ModelAdmin):
    search_fields = ('name',)
    fields = ('name',)
    ordering = ('name',)

    def get_model_perms(self, request):
        '''
        A hack to hide the standalone RespondingAgency from the admin.
        '''
        return {}


class SourceFileForm(forms.ModelForm):
    def clean(self):
        super().clean()

        try:
            source_file = SourceFile.objects.get(
                responding_agency=self.cleaned_data['responding_agency'],
                reporting_year=self.cleaned_data['reporting_year']
            )

        except SourceFile.DoesNotExist:
            pass

        else:
            message = '{0} already has a source file for {1}: {2}'.format(
                self.cleaned_data['responding_agency'],
                self.cleaned_data['reporting_year'],
                source_file.source_file
            )
            raise ValidationError(message)


class AdminSourceFile(admin.ModelAdmin):
    model = SourceFile
    form = SourceFileForm

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

    def save_model(self, request, obj, form, change):
        obj.upload = Upload.objects.create(created_by=request.user)

        # Auto-fill reporting period dates, if they were not provided
        if not obj.reporting_period_start_date:
            obj.reporting_period_start_date = datetime.datetime(obj.reporting_year, 1, 1)

        if not obj.reporting_period_end_date:
            obj.reporting_period_end_date = datetime.datetime(obj.reporting_year, 12, 31)

        super().save_model(request, obj, form, change)


class AdminStandardizedFile(admin.ModelAdmin):
    form = UploadForm
    change_form_template = 'data_import/change_form.html'

    def get_readonly_fields(self, request, obj=None):
        '''
        Disable editing of responding agency for existing source files.
        '''
        if obj:
            return ['standardized_file', 'reporting_year']
        else:
            return []

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}

        file = self.get_object(request, object_id)

        extra_context['task'] = file.get_task()
        extra_context['review_step'] = file.review_step
        extra_context['id'] = object_id

        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def save_model(self, request, obj, form, change):
        if change:
            super().save_model(request, obj, form, change)

        else:
            upload = Upload.objects.create()
            obj.upload = upload

            super().save_model(request, obj, form, change)

            obj.copy_to_database()


admin.site.register(SourceFile, AdminSourceFile)
admin.site.register(RespondingAgency, AdminRespondingAgency)
admin.site.register(StandardizedFile, AdminStandardizedFile)
