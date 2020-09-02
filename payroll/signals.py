from django.core.cache import cache
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.http import HttpRequest
from django.utils.cache import get_cache_key

from extra_settings.models import Setting


@receiver(post_save, sender=Setting, dispatch_uid='post_save_refresh_cache')
def post_save_refresh_cache(sender, instance, **kwargs):
    if instance.name == 'PAYROLL_SHOW_DONATE_BANNER':
        request = HttpRequest()
        request.path = '/'

        # TODO: Does this need to vary in a deployment environment?
        request.META = {
            'SERVER_NAME': 'localhost',
            'SERVER_PORT': 8000,
        }

        key = get_cache_key(request)

        if cache.has_key(key):
            cache.delete(key)
            print('Deleted key "{}"'.format(key))

        else:
            print('Key "{}" does not exist'.format(key))
