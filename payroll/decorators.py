from functools import wraps, partial

from django.core.cache import cache


CACHE_TIMEOUT = 86400  # 60 * 60 * 24


def check_cache(func=None, *, cache_prefix=None, cache_key='_cache', cache_timeout=CACHE_TIMEOUT):
    '''
    Function decorator to first try getting data from self._cache
    before executing.
    '''

    # Allow for optional decorator arguments
    # e.g. @check_cache OR @check_cache(cache_timeout=3600)
    # See: https://pybit.es/decorator-optional-argument.html
    if func is None:
        return partial(check_cache, cache_prefix=cache_prefix, cache_key=cache_key, cache_timeout=cache_timeout)

    @wraps(func)
    def _check_cache(self, *args, **kwargs):
        key = func.__name__

        if cache_prefix:
            key = cache_prefix + '_' + key
        elif hasattr(self, 'object'):
            key = str(self.object.id) + '_' + key

        data = getattr(self, cache_key).get(key, None)

        if not data:
            data = func(self, *args, **kwargs)
            cache.set(key, data, cache_timeout)

        return data
    return _check_cache
