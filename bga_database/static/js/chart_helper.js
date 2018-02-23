var ChartHelper = ChartHelper || {};

var ChartHelper = {
  extract_values: function(data) {
    var values = Array();

    data.forEach(function(bin) {
      values.push(bin.value);
    });

    return values;
  },
  make_salary_chart: function(entity_name, data, entity_type) {
    var values = ChartHelper.extract_values(data);
    var title;

    if (entity_type === 'department') {
      title = 'Average Department Salary Distribution';
    } else if (entity_type === 'employee') {
      title = 'Employee Salary Distribution';
    }

    Highcharts.chart('distribution-chart', {
      title: {
        text: entity_name + ' ' + title,
      },
      xAxis: {
        labels: {
          enabled: true,
          formatter: function() {
            return '$' + data[this.value].edge;
          },
        },
        tickColor: 'white',
      },
      yAxis: {
        title: {
          text: 'n ' + entity_type + 's',
        },
      },
      series: [{
        name: entity_type + 's',
        type: 'column',
        data: values,
        id: 'salaries',
        tooltip: {
          headerFormat: '', // Remove header
          pointFormatter: function(point) {
            var current_bin = data[this.x].edge;
            var next_bin = data[this.x + 1].edge; // TO-DO: Fix for min and max
            return this.y + ' ' + entity_type + 's earn between ' + current_bin + ' & ' + next_bin;
          },
        },
        color: '#6c757c',
      }],
      legend: {
        enabled: false,
      }
    });
  },
};
