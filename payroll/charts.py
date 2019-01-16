import math

import numpy as np

from bga_database.chart_settings import BAR_DEFAULT
from payroll.utils import format_ballpark_number


class ChartHelperMixin(object):
    def _get_bar_color(self, lower_edge, upper_edge):
        return BAR_DEFAULT

    def bin_salary_data(self, data):
        float_data = np.asarray(data, dtype='float')
        max_value = np.amax(float_data)

        bin_size = 10000
        bin_num = 20
        bin_edges = np.array([i * bin_size for i in range(bin_num + 1)], dtype='float')
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
