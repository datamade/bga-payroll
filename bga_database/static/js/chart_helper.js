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
            return '$' + edges.lower_edge + ' – $' + edges.upper_edge;
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
                }
              }
            },
            xAxis: {
                labels: {
                    enabled: true,
                    formatter: axis_format,
                },
                title: {
                    text: 'Salary range',
                },
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
-                 pointFormatter: tooltip_format,
                },
                color: '#6c757c',
            }],
            legend: {
                enabled: false,
            }
        });
    },
};
