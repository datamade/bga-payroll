function initDataYearToggle (endpoint, slug, initialYear, callback) {
    const cache = {};

    var getData = async function (year) {
        if ( cache[year] !== undefined ) {
            callback(year, cache[year]);
            $('#yearDropdownMenuButton').text(year);
        } else {
            var url;

            if ( slug === null ) {
                url = `/${endpoint}/?data_year=${year}`;
            } else {
                url = `/${endpoint}/${slug}/?data_year=${year}`;
            }

            try {
                const result = await $.ajax({
                    url: url,
                    type: 'GET',
                });
                callback(year, result);
                $('#yearDropdownMenuButton').text(year);

                // Store the result in the user's cache
                cache[year] = result;
            } catch (error) {
                console.error(error);
            }
        }
    };

    getData(initialYear);

    $('#data-year-select > .year-dropdown-item').on('click', function(e) {
        const year = e.currentTarget.textContent;
        getData(year);
    });
}

export { initDataYearToggle };