var ChartHelper = ChartHelper || {};

var ChartHelper = {
    extract_values: function(data) {
        var values = Array();

        data.forEach(function(bin) {
            values.push(bin.value);
        });

        return values;
    },
    make_salary_chart: function(data, entity_type) {
        var values = ChartHelper.extract_values(data);

        var tooltip_format = function(point) {
            var edges = data[this.x];
            return this.y + ' ' + entity_type + 's earn between $' + edges.lower_edge + ' and $' + edges.upper_edge;
        };

        var axis_format = function() {
            var edges = data[this.value];

            if (this.value === data.length) {
              edges = data[this.value - 1];
              return '$' + edges.upper_edge;
            }

            return '$' + edges.lower_edge;
        };

        var element = entity_type + '-distribution-chart';

        Highcharts.chart(element, {
            title: {
                text: '', // Done in template
            },
            plotOptions: {
              column: {
                maxPointWidth: 80,
                minPointLength: 2,
                dataLabels: {
                  enabled: true
                },
                pointPlacement: 'between',
                pointPadding: 0,
                groupPadding: 0
              }
            },
            xAxis: {
                labels: {
                    enabled: true,
                    formatter: axis_format,
                },
                tickInterval: 0,
                endOnTick: true,
                title: {
                    text: 'Salary range',
                },
                allowDecimals: false
            },
            yAxis: {
                title: {
                    text: 'Number of ' + entity_type + 's',
                },
            },
            series: [{
                name: entity_type + 's',
                type: 'column',
                data: values,
                id: 'salaries',
                tooltip: {
                  headerFormat: '', // Remove header
                  pointFormatter: tooltip_format
                },
                color: '#6c757c',
            }],
            legend: {
                enabled: false,
            }
        });
    },
    make_composition_chart: function(data) {
      element = 'department-composition-chart';

      Highcharts.chart(element, {
        title: '',
        chart: {
          type: 'bar'
        },
        colors: ['#343a40', '#6c757c', '#007aff', '#ffc107', '#f8f9fa', '#28a845'],
        legend: {
          verticalAlign: 'top'
        },
        plotOptions: {
          series: {
            stacking: 'percent',
            dataLabels: {
              align: 'right',
              enabled: true,
              format: '{percentage:.1f}%'
            }
          }
        },
        xAxis: {
          title: {
            text: ''
          },
          labels: {
            enabled: false
          }
        },
        yAxis: {
          title: {
            text: 'Percent of total unit payroll expenditure',
            labels: {
              enabled: false
            },
          },
          reversedStacks: false
        },
        series: data
      });
    }
};
