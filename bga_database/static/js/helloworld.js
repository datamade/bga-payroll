export function getYearData () {
	$('#index-data-year').change(async function(e) {
		const url = '/index/?data_year=' + e.currentTarget.value
		if (e.currentTarget.value !== "Select Year") {
			try {
				const result = await $.ajax({
					url: url,
					type: 'GET',
				})
				ChartHelper.make_salary_chart(result.salary_json, 'employee')
				console.log(result.salary_json)
			} catch (error) {
				console.log("this is an error!")
				console.log(error)
			}
		}
		return
	})
}