function populateStoryFeed() {
    $.get('/story-feed/', function (data) {
        var container = $('#story-feed-stories');

        $.each(data.entries, function (idx, entry) {
            var storyItem = $('<div class="p-3" />');

            var title = $('<h5 />').append(
                $('<a />').attr('href', entry.link).text(entry.title)
            );

            var summary = $('<p class="text-serif my-2" />').text(entry.summary);
            var date = $('<p class="mb-0" />').text(entry.date);

            storyItem.append(title, summary, date);

            container.append(storyItem);

            if ( idx < data.entries.length - 1 ) {
                container.append($('<hr class="w-75 mx-auto" />'));
            }
        });
    });
};

populateStoryFeed();
