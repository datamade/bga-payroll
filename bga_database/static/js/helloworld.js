export function getYearData () {
	$('#index-data-year').change(async function(e) {
		const url = '/index/?data_year=' + e.currentTarget.value
		if (e.currentTarget.value !== "Select Year") {
			try {
				const result = await $.ajax({
					url: url,
					type: 'GET',
				})
				ChartHelper.make_salary_chart(result.salary_json, 'employee');
				$('#index-salary-count').text(result.salary_count)
				$('#index-unit-count').text(result.unit_count)
			} catch (error) {
				console.log("this is an error!")
				console.log(error)
			}
		}
		return
	})
}