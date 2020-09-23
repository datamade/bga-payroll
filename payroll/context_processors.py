from django.conf import settings

from payroll.models import Unit


def inspiration_slugs(request):
    try:
        chicago_slug = Unit.objects.get(name__exact='City of Chicago').slug
    except:
        chicago_slug = None

    return {
        'chicago_slug': chicago_slug,
        'STATIC_URL': settings.STATIC_URL,
    }
