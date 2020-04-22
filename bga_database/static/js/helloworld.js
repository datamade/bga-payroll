export function getYearData () {
	$('#index-data-year').change(async function(e) {
		const url = '/index/?data_year=' + e.currentTarget.value
		try {
			const result = await $.ajax({
				url: url,
				type: 'GET',
			})
			console.log(result)
		} catch (error) {
			console.log(error)
		}
	})
}