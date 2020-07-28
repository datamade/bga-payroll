from django.contrib.sitemaps import Sitemap

from payroll.models import Unit, Department


class PayrollSitemap(Sitemap):

    def location(self, obj):
        return '/{0}/{1}/'.format(obj.endpoint, obj.slug)


class UnitSitemap(PayrollSitemap):

    def items(self):
        return Unit.objects.all()


class DepartmentSitemap(PayrollSitemap):

    def items(self):
        return Department.objects.all()
