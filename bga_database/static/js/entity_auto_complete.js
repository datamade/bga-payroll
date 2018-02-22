$(document).ready(function() {
    var input = $('#entity-lookup');

    input.autocomplete({
        source: '/entity-lookup/' + input.val(),
        minLength: 3,
        select: function(event, ui) {
            event.preventDefault();
            input.val(ui.item.label);
            $('#entity-form').attr('action', ui.item.value);
        },
    });
});