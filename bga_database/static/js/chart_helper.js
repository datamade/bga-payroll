var ChartHelper = ChartHelper || {};

var ChartHelper = {
    extract_values: function(data) {
        var values = Array();

        data.forEach(function(bin) {
          var bin_object = {};
          bin_object.y = bin.value;

          if ( bin.color ) {
            bin_object.color = bin.color;
          }

          values.push(bin_object);
        });

        return values;
    },
    make_salary_chart: function(data, entity_type) {
        var values = ChartHelper.extract_values(data);

        var tooltip_format = function(point) {
            var edges = data[this.x];
            return this.y.toLocaleString() + ' ' + entity_type + 's earn between $' + edges.lower_edge + ' and $' + edges.upper_edge;
        };

        var axis_format = function() {
            var edges = data[this.value];

            if (this.value === data.length) {
              edges = data[this.value - 1];
              return '$' + edges.upper_edge;
            }

            // Occurs when Highcharts wants to add an extra label
            try {
              return '$' + edges.lower_edge;
            } catch (err) {
              return '';
            }
        };

        var element = entity_type + '-distribution-chart';

        Highcharts.setOptions({
            lang: {
              thousandsSep: ',',
            }
        });

        Highcharts.chart(element, {
            title: {
              text: '', // Done in template
            },
            plotOptions: {
              column: {
                maxPointWidth: 80,
                minPointLength: 2,
                dataLabels: {
                  enabled: true,
                  color: '#000',
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
