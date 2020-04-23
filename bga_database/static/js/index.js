function getYearData () {
    $('#index-data-year').on('change', async function(e) {
        const url = '/index/?data_year=' + e.currentTarget.value;
        try {
            const result = await $.ajax({
                url: url,
                type: 'GET',
            });
            ChartHelper.make_salary_chart(result.salary_json, 'employee');
            $('#index-salary-count').text(result.salary_count);
            $('#index-unit-count').text(result.unit_count);
            $('#index-year').text(e.currentTarget.value);
        } catch (error) {
            console.error(error);
        }
        return;
    });
}

getYearData();