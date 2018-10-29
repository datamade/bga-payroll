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

            window.location = '/search/?' + querystring;
        } else {
            $('#name-warning').collapse('show');
        }
    });
}