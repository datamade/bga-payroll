var make_distribution_chart = function(entity_name, data) {
  var salaries = Array();

  data.forEach(function(salary) {
    salaries.push(salary.amount);
  });

  Highcharts.chart('distribution-chart', {
      title: {
          text: entity_name + ' Salary Distribution',
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
          type: 'column',
          data: salaries,
          zIndex: -1,
          tooltip: {
            headerFormat: '',
            pointFormatter: function(point) {
              var employee = data[this.x];
              var name = employee.name;
              var position = employee.position;
              var salary = this.y;
              return '<strong>' + name + '</strong><br />' + position + '<br />$' + salary;
            }
          },
          color: '#6c757c',
      }],

      legend: {
        enabled: false,
      }
  });
};