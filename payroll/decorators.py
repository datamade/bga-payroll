from functools import wraps, partial

from django.core.cache import cache


CACHE_TIMEOUT = 86400  # 60 * 60 * 24


def check_cache(func=None, *, cache_key='_cache', timeout=CACHE_TIMEOUT):
    '''
    Function decorator to first try getting data from self._cache
    before executing.
    '''

    # Allow for optional decorator arguments
    # e.g. @check_cache OR @check_cache(timeout=3600)
    # See: https://pybit.es/decorator-optional-argument.html
    if func is None:
        return partial(check_cache, cache_key=cache_key, timeout=timeout)

    @wraps(func)
    def _check_cache(self, *args, **kwargs):
        key = func.__name__
        data = getattr(self, cache_key).get(key, None)
        cache_timeout = timeout

        if not data:
            data = func(self, *args, **kwargs)
            cache.set(key, data, cache_timeout)

        return data
    return _check_cache
