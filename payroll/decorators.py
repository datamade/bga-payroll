from functools import wraps, partial

from django.core.cache import cache


CACHE_TIMEOUT = 86400  # 60 * 60 * 24


def _get_cache_object(view):
    return view._cache


def check_cache(func=None, *, cache_object=_get_cache_object, cache_prefix=None, cache_timeout=CACHE_TIMEOUT):
    '''
    Function decorator to first try getting data from self._cache
    before executing.
    '''

    # Allow for optional decorator arguments
    # e.g. @check_cache OR @check_cache(cache_timeout=3600)
    # See: https://pybit.es/decorator-optional-argument.html
    if func is None:
        return partial(check_cache, cache_object=cache_object, cache_prefix=cache_prefix, cache_timeout=cache_timeout)

    @wraps(func)
    def _check_cache(self, *args, **kwargs):
        # set key
        if cache_prefix:
            key = cache_prefix + '_' + func.__name__
        elif getattr(self, 'cache_prefix'):
            # get cache_prefix from CacheMixin attribute
            key = getattr(self, 'cache_prefix') + '_' + func.__name__
        else:
            key = func.__name__

        # set _cache
        if callable(cache_object):
            _cache = cache_object(self)
        elif cache_object:
            _cache = cache_object

        data = _cache.get(key, None)

        if not data:
            data = func(self, *args, **kwargs)
            cache.set(key, data, cache_timeout)

        return data
    return _check_cache
