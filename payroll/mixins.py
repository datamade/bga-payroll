import numpy as np

from django.core.cache import cache

from bga_database.chart_settings import BAR_DEFAULT, DISTRIBUTION_MAX, \
    DISTRIBUTION_BIN_NUM
from payroll.utils import format_ballpark_number


class CacheMixin(object):
    """
    Integrate a low-level cache to work with payroll.decorators.check_cache.

    Required attributes:

        cache_keys:
            The keys you're caching. Should be accessed via a class method of
            the same name.

    Optional attributes:

        cache_prefix:
            Prefix the cache key with a prefix unique to the view.

    """

    @property
    def _cache(self):
        if not hasattr(self, '_kache'):
            if hasattr(self, 'cache_prefix'):
                keys = [self.cache_prefix + '_' + k for k in self.cache_keys]
            else:
                keys = self.cache_keys

            self._kache = cache.get_many(keys)

        return self._kache


class ChartHelperMixin(object):
    def _get_bar_color(self, lower_edge, upper_edge):
        if lower_edge == DISTRIBUTION_MAX:
            return 'url(#highcharts-default-pattern-0)'
        return BAR_DEFAULT

    def bin_salary_data(self, data):
        float_data = np.asarray(data, dtype='float')
        max_value = np.amax(float_data)

        bin_size = DISTRIBUTION_MAX / DISTRIBUTION_BIN_NUM

        bin_edges = np.array(
            [i * bin_size for i in range(DISTRIBUTION_BIN_NUM + 1)],
            dtype='float'
        )

        if max_value > bin_edges[-1]:
            bin_edges = np.append(bin_edges, max_value)

        values, edges = np.histogram(float_data, bins=bin_edges)

        salary_json = []

        for i, value in enumerate(values):
            lower, upper = int(edges[i]), int(edges[i + 1])

            salary_json.append({
                'value': int(value),  # number of salaries in given bin
                'lower_edge': format_ballpark_number(lower),
                'upper_edge': format_ballpark_number(upper),
                'color': self._get_bar_color(lower, upper),
            })

        return salary_json
