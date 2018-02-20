var ChartHelper = ChartHelper || {};

var ChartHelper = {
  extract_salaries: function(data) {
    var salaries = Array();

    data.forEach(function(salary) {
      salaries.push(salary.amount);
    });

    return salaries;
  },
  make_salary_chart: function(entity_name, data, entity_type) {
    var salaries = ChartHelper.extract_salaries(data);
    var title;
    var tooltip_func;

    if (entity_type === 'department') {
      title = 'Average Salary by Department';
      tooltip_func = function(point) {
        var department = data[this.x].department;
        var average = this.y;
        return '<strong>' + department + '</strong><br />' + '<br />$' + average;
      };
    } else if (entity_type === 'employee') {
      title = 'Salary Distribution';
      tooltip_func = function(point) {
        var employee = data[this.x];
        var name = employee.name;
        var position = employee.position;
        var salary = this.y;
        return '<strong>' + name + '</strong><br />' + position + '<br />$' + salary;
      };
    }

    Highcharts.chart('distribution-chart', {
      title: {
        text: entity_name + ' ' + title,
      },
      xAxis: {
        reversed: true,
        labels: {
          enabled: false,
        },
        tickColor: 'white',
      },
      yAxis: {
        title: {
          text: 'Salary ($)',
        },
      },
      series: [{
        name: 'Salary',
        type: 'area',
        data: salaries,
        id: 'salaries',
        tooltip: {
          headerFormat: '', // Remove header
          pointFormatter: tooltip_func,
        },
        color: '#6c757c',
      }],
      legend: {
        enabled: false,
      }
    });
  },
};
