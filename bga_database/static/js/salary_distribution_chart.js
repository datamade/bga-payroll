var make_distribution_chart = function(entity_name, data, type) {
  var salaries = Array();

  data.forEach(function(salary) {
    salaries.push(salary.amount);
  });

  if ( type == 'department' ) {
    var title = 'Average Salary by Department'
  } else {
    var title = 'Salary Distribution'
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
            headerFormat: '',
            pointFormatter: function(point) {
              if ( type == 'department' ) {
                var department = data[this.x].department;
                var average = this.y;
                return '<strong>' + department + '</strong><br />' + '<br />$' + average;
              } else {
                var employee = data[this.x];
                var name = employee.name;
                var position = employee.position;
                var salary = this.y;
                return '<strong>' + name + '</strong><br />' + position + '<br />$' + salary;
              }
            },
          },
          color: '#6c757c',
      }],

      legend: {
        enabled: false,
      }
  });
};