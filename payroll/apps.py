from django.apps import AppConfig
from django.conf import settings

class PayrollConfig(AppConfig):
    name = 'payroll'

    def ready(self):
        from bga_database.jinja2 import environment

        settings.COMPRESS_JINJA2_GET_ENVIRONMENT = lambda: environment()
