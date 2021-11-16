var Employer = {
  commonUpdate: function (year, result) {
    Employer.updateDataYear(year);
    Employer.updateBaseBallStats(result);
    Employer.updateSourceLink(result);
  },

  makeLink: function (href, text) {
    var link = $('<a>').attr('href', href);
    link.text(text);
    return link;
  },

  updateSearchLink: function (linkId, year) {
    var searchLink = $(linkId);
    var urlParts = searchLink.attr('href').split('?');
    var url = urlParts[0];
    var querystring = urlParts[1];
    var searchParams = new URLSearchParams(querystring);
    searchParams.set('year', year);
    searchLink.attr('href', url + '?' + searchParams.toString());
  },

  updateDataYear: function (year) { $('.entity-data-year').text(year); },

  updateBaseBallStats: function (result) {
    $('.entity-headcount').text(result.headcount);
    $('#entity-total-expenditure').text('$' + result.total_expenditure);
    $('.entity-median-tp').text(result.median_tp);
  },

  updateSourceLink: function (result) {
    if ( result.source_link ) {
      $.each($('.source-span > a'), function (idx, el) {
        $(el).attr('href', result.source_link);
      });

      $('.no-source-span').hide();
      $('.source-span').show();
    } else {
      $('.source-span').hide();
      $('.no-source-span').show();
    }
  }
};

var Unit = {
  update: function(year, result) {
    Employer.commonUpdate(year, result);

    Unit.updateSummaryCard(year, result);
    Unit.updateEmployeeCard(year, result);
    Unit.updateDepartmentCard(year, result);
  },

  updateSummaryCard: function (year, result) {
    try {
      $('#entity-salary-percentile').text(result.salary_percentile);
      $('#entity-expenditure-percentile').text(result.expenditure_percentile);
    } catch (err) {
      console.log('Entity is not comparable');
    }

    if ( result.highest_spending_department === null ) {
      $('#entity-department-statistics').hide();
    } else {
      $('#entity-highest-spending-department').attr('href', '/department/' + result.highest_spending_department.slug + '/?data_year=' + year);
      $('#entity-highest-spending-department').text(result.highest_spending_department.name);
      $('#entity-highest-spending-department-expenditure').text(result.highest_spending_department.amount);
      $('#entity-department-statistics').show();
    }

    ChartHelper.make_salary_chart(result.employee_salary_json, 'employee');
  },

  updateEmployeeCard: function (year, result) {
    $('#entity-salaries').empty();

    $.each(result.salaries, function (idx, salary) {
      var tRow = $('<tr>');

      var personLink = Employer.makeLink(
        '/person/' + salary.slug,
        salary.name
      );

      var employerLink = Employer.makeLink(
        '/' + salary.employer_endpoint + '/' + salary.employer_slug + '/?data_year=' + year,
        salary.employer
      );

      tRow.append($('<td>').html(personLink));
      tRow.append($('<td>').html(salary.position));
      tRow.append($('<td>').html(employerLink));
      tRow.append($('<td>').html(salary.amount).addClass('text-right'));
      tRow.append($('<td>').html(salary.extra_pay).addClass('text-right'));

      $('#entity-salaries').append(tRow);
    });

    ChartHelper.make_payroll_expenditure_chart(result.payroll_expenditure);

    Employer.updateSearchLink('#employee-search-link', year);
    Employer.updateSearchLink('#employee-download-link', year);

    $('.entity-median-tp').text(result.median_tp);
    $('#entity-median-bp').text(result.median_bp);
    $('#entity-median-ep').text(result.median_ep);
  },

  updateDepartmentCard: function (year, result) {
    $('#department-salaries').empty();

    if ( result.department_salaries.length > 0 ) {
      $.each(result.department_salaries, function (idx, salary) {
        var tRow = $('<tr>');
        var departmentLink = Employer.makeLink(
          '/department/' + salary.slug + '/?data_year=' + year,
          salary.name
        );

        tRow.append($('<td>').html(departmentLink));
        tRow.append($('<td>').html(salary.headcount).addClass('text-right'));
        tRow.append($('<td>').html(salary.median_tp).addClass('text-right'));
        tRow.append($('<td>').html('$' + salary.entity_bp).addClass('text-right'));
        tRow.append($('<td>').html('$' + salary.entity_ep).addClass('text-right'));
        tRow.append($('<td>').html('$' + salary.total_expenditure).addClass('text-right'));

        $('#department-salaries').append(tRow);
      });

      ChartHelper.make_composition_chart(result.composition_json);

      Employer.updateSearchLink('#department-search-link', year);

      $('.entity-department-statistics').removeClass('d-none');
    } else {
      $('.entity-department-statistics').addClass('d-none');
    }
  }
};

var Department = {
  update: function (year, result) {
    Employer.commonUpdate(year, result);

    Department.updateSummaryCard(result);
    Department.updateEmployeeCard(year, result);
  },

  updateSummaryCard: function (result) {
    try {
      $('#entity-salary-percentile').text(result.salary_percentile);
      $('#entity-expenditure-percentile').text(result.expenditure_percentile);
    } catch (err) {
      console.log('Entity is not comparable');
    }

    $('#entity-percent-of-expenditure').text(result.percent_of_total_expenditure);

    ChartHelper.make_salary_chart(result.employee_salary_json, 'employee');
  },

  updateEmployeeCard: function (year, result) {
    $('#entity-salaries').empty();

    $.each(result.salaries, function (idx, salary) {
      var tRow = $('<tr>');

      var personLink = Employer.makeLink(
        '/person/' + salary.slug,
        salary.name
      );

      tRow.append($('<td>').html(personLink));
      tRow.append($('<td>').html(salary.position));
      tRow.append($('<td>').html(salary.amount).addClass('text-right'));
      tRow.append($('<td>').html(salary.extra_pay).addClass('text-right'));

      $('#entity-salaries').append(tRow);
    });

    ChartHelper.make_payroll_expenditure_chart(result.payroll_expenditure);

    Employer.updateSearchLink('#employee-search-link', year);
    Employer.updateSearchLink('#employee-download-link', year);

    $('.entity-median-tp').text(result.median_tp);
    $('#entity-median-bp').text(result.median_bp);
    $('#entity-median-ep').text(result.median_ep);
  }
};
