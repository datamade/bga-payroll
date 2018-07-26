import datetime

from django.contrib import admin
from django.db.models import Q

from data_import.models import SourceFile
from payroll.models import Salary


class AdminSourceFile(admin.ModelAdmin):
    exclude = (
        'response_date',
        'upload',
        'google_drive_file_id',
        'standardized_file',
        'reporting_period_start_date',
        'reporting_period_end_date',
    )

    def save_model(self, request, obj, form, change):
        obj.reporting_period_start_date = (obj.reporting_year, 1, 1)
        obj.reporting_period_end_date = (obj.reporting_year, 12, 31)

        obj = self._link_standardized_file(obj)

        super().save_model(request, obj, form, change)

    def _link_standardized_file(self, obj):
        in_reporting_year = Q(vintage__standardized_file__reporting_year=obj.reporting_year)
        of_responding_agency = Q(vintage__standardized_file__responding_agency=obj.responding_agency)

        salary = Salary.objects.filter(in_reporting_year & of_responding_agency).first()

        if salary:
            obj.standardized_file = salary.vintage.standardized_file

        else:
            raise



admin.site.register(SourceFile, AdminSourceFile)
