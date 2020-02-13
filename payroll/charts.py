import numpy as np

from bga_database.chart_settings import BAR_DEFAULT, DISTRIBUTION_MAX, \
    DISTRIBUTION_BIN_NUM
from payroll.utils import format_ballpark_number


class ChartHelperMixin(object):
    def _get_bar_color(self, lower_edge, upper_edge):
        if lower_edge == DISTRIBUTION_MAX:
            return 'url(#highcharts-default-pattern-0)'
        return BAR_DEFAULT

    def bin_salary_data(self, data):
        float_data = np.asarray([d for d in data if d], dtype='float')
        max_value = np.amax(float_data)

        print(max_value)

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
