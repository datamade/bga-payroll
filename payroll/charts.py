import math

import numpy as np

from payroll.utils import format_ballpark_number


class ChartHelperMixin(object):
    def _get_bar_color(self, lower_edge, upper_edge):
        return '#004c76'

    def bin_salary_data(self, data):
        float_data = np.asarray(data, dtype='float')

        # Size of the bins
        multiplier = 25000

        # This is to make the appropriate number of bins
        max_value = np.amax(float_data)
        bin_num = math.ceil(max_value / multiplier)  # rounding up to capture max value
        bin_edges = np.array([], dtype='float')

        for i in range(bin_num + 1):  # adding 1 to get appropriate number of bins
            bin_edges = np.append(bin_edges, i * multiplier)

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
