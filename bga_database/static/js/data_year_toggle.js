function initDataYearToggle (endpoint, slug, initialYear, callback) {
    const cache = {};

    var getData = async function (year) {
        if ( cache[year] !== undefined ) {
            $('#selected-year').addClass('d-none');
            $('.year-loading').removeClass('d-none');

            callback(year, cache[year]);

            $('#selected-year').text(year);

            $('.year-loading').addClass('d-none');
            $('#selected-year').removeClass('d-none');
        } else {
            var url;

            if ( slug === null ) {
                url = `/${endpoint}/?data_year=${year}`;
            } else {
                url = `/${endpoint}/${slug}/?data_year=${year}`;
            }

            try {
                $('#selected-year').addClass('d-none');
                $('.year-loading').removeClass('d-none');

                const result = await $.ajax({
                    url: url,
                    type: 'GET',
                });
                callback(year, result);
                $('#selected-year').text(year);

                // Store the result in the user's cache
                cache[year] = result;
            } catch (error) {
                console.error(error);
            }

            $('.year-loading').addClass('d-none');
            $('#selected-year').removeClass('d-none');
        }
    };

    getData(initialYear);

    $('#data-year-select > .year-dropdown-item').on('click', function(e) {
        const year = e.currentTarget.textContent;
        getData(year);
    });
}

export { initDataYearToggle };
