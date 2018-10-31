function makeQuerystring(params, term) {
    params.name = term;

    var entity_types = [];

    $('.entity-type-check').filter('input:checked').each(function entityTypes() {
        entity_types.push($(this).val());
    });

    // for the homepage
    if ( entity_types.length ) {
        params.entity_type = entity_types.join(',');
    }

    // for search results
    delete params.page;

    return $.param(params);
}

function initSearch(get_object) {
    $('#submit-button').click(function submitSearch(e) {
        e.preventDefault();

        var term = $.trim($('#entity-lookup').val());

        if ( term ) {
            var querystring = makeQuerystring(get_object, term);

            if (!sessionAuthenticated()) {
              incrementCounterCookie();
            }

            window.location = '/search/?' + querystring;
        } else {
            $('#name-warning').collapse('show');
        }
    });

    $('#entity-lookup').keyup(function checkTermLength(e) {
        // Enable the search button only if the term >= 3 characters in length
        var term = $.trim($('#entity-lookup').val());
        var searchDisabled = $('#submit-button').prop('disabled') == true;

        if ( term.length >= 3 ) {
            if ( searchDisabled ) {
                $('#submit-button').prop('disabled', false);
            }
        } else {
            if ( !searchDisabled ) {
                $('#submit-button').prop('disabled', true);
            }
        }
    });
}