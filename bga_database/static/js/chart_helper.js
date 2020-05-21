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

    var tooltip_format = function() {
      var edges = data[this.x];
      return this.y.toLocaleString() + ' ' + entity_type + 's earn between $' + edges.lower_edge + ' and $' + edges.upper_edge;
    };

    var axis_format = function() {
      var penultimate_bin = this.value === data.length - 1;
      var last_bin = this.value === data.length;

      var edges;

      if ( last_bin ) {
        edges = data[this.value - 1];
      } else {
        edges = data[this.value];
      }

      var composite_last_bin = edges.upper_edge !== '200k';

      if ( last_bin ) {
        if ( composite_last_bin ) {
          return null;
        } else {
          return '$' + edges.upper_edge;
        }
      } else if ( penultimate_bin ) {
        if ( composite_last_bin ) {
          return '$' + edges.lower_edge + '+';
        } else {
          return '$' + edges.lower_edge;
        }
      } else {
        try {
          return '$' + edges.lower_edge;
        } catch (err) {
          // Occurs when Highcharts wants to add an extra label
          return '';
        }
      }
    };

    // Hide the last tick, if the chart includes a column for 200k+, i.e.,
    // the last tick is not "200k"
    var end_on_tick;

    if ( data[data.length - 1].upper_edge !== '200k' ) {
        end_on_tick = false;
    } else {
        end_on_tick = true;
    }

    var element = entity_type + '-distribution-chart';

    Highcharts.setOptions({ // jshint ignore:line
      lang: {
        thousandsSep: ',',
      },
      chart: {
        style: {
          fontFamily: '"acumin-pro", "Arial", Helvetica, sans-serif',
        }
      }
    });

    Highcharts.chart(element, { // jshint ignore:line
      title: {
        text: '', // Done in template
      },
      plotOptions: {
        column: {
          maxPointWidth: 80,
          minPointLength: 2,
          dataLabels: {
            enabled: true,
            color: '#333',
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
        endOnTick: end_on_tick,
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
        color: '#294d71',
      }],
      legend: {
        enabled: false,
      }
    });
  },
  make_composition_chart: function(data) {
    var element = 'department-composition-chart';

    Highcharts.chart(element, { // jshint ignore:line
      title: '',
      chart: {
        type: 'bar'
      },
      tooltip: {
        formatter: function() {
          return this.series.name;
        }
      },
      legend: {
        floating: true,
        verticalAlign: 'top',
        y: 30
      },
      colors: ['#0B2F42', '#023f62', '#245D8C', '#538BC2', '#82BEED', '#758892'],
      xAxis: {
        labels: {
          enabled: false
        }
      },
      yAxis: {
        reversedStacks: false,
        title: {
          text: 'Percent of total unit payroll expenditure'
        }
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
      series: data
    });
  },
  make_payroll_expenditure_chart: function(data) {
    var element = 'payroll-expenditure-chart';

    // Create the chart
    Highcharts.chart(element, { // jshint ignore:line
      chart: {
        type: 'pie'
      },
      colors: ['#004C76', '#538BC2'],
      title: {
        text: ''
      },
      tooltip: {
        formatter: function() {
          return this.key + ": $" +  this.y.toLocaleString();
        }
      },
      plotOptions: {
        series: {
          dataLabels: {
            enabled: true
          }
        }
      },
      series: [data.series_data]
    });
  },
  make_salary_over_time_chart: function(data) {
    var element = 'salary-over-time-chart';

    Highcharts.chart(element, { // jshint ignore:line
      chart: {
        type: 'column'
      },
      colors: ['#538BC2', '#004C76'],
      title: {
        text: ''
      },
      tooltip: {
        formatter: function() {
          return this.key + " " + this.series.name + ": $" +  this.y.toLocaleString();
        }
      },
      series: data,
      xAxis: {
        type: 'category',
      },
      yAxis: {
        title: {
            text: 'Total pay ($)'
        }
      },
      plotOptions: {
        series: {
          stacking: 'normal'
        }
      },
      legend: {
        reversed: true
      }
    });
  }
};

export { ChartHelper };
