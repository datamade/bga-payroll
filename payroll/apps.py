from django.apps import AppConfig


class PayrollConfig(AppConfig):
    name = 'payroll'

    def ready(self):
        import payroll.signals  # noqa
