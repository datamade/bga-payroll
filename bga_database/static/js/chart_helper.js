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

    Highcharts.setOptions({
      lang: {
        thousandsSep: ',',
      },
      chart: {
        style: {
          fontFamily: '"acumin-pro", "Arial", Helvetica, sans-serif',
        }
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
    const element = 'department-composition-chart';
    console.log(data)

    Highcharts.chart(element, {
      title: '',
      chart: {
        type: 'bar'
      },
      colors: ['#004c76', '#c84747', '#fd0', '#67488b', '#1a9b5b', '#343a40'],
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
    const element = 'payroll-expenditure-chart'
    console.log(data.series_data)

    data.series_data.data.colorByPoint = true
    // Create the chart
    Highcharts.chart(element, {
      chart: {
        type: 'pie'
      },
      title: {
        text: 'Test'
      },
      plotOptions: {
        series: {
          dataLabels: {
            enabled: true
          }
        }
      },
      series: [data.series_data]
    })
  }
};
