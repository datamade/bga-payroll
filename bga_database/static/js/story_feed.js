function populateStoryFeed() {
    $.get('/story-feed/', function (data) {
        var container = $('#story-feed-stories');

        $.each(data.entries, function (idx, entry) {
            var storyItem = $('<div class="p-3 story-item" />');
            
            var itemLeft = $('<div class="story-img col-md-4"/>');
            var itemRight = $('<div />');

            var image = $('<a />').attr({
                'href': entry.link,
                'target': '_blank'
            });
            
            image.append(
                $('<img />').attr({
                    'src': '/static/img/newsroom-placeholder.png'
                })
            );

            var type = $('<div class="text-uppercase"/>').text(
                    // TODO: see if there is a category for 
                    // each story to display
                    'Investigations'
                );

            var title = $('<h5 />').append(
                $('<a />').attr({
                    'href': entry.link,
                    'target': '_blank'
                }).text(entry.title)
            );

            var summary = $('<p class="text-serif my-2" />').text(entry.summary);
            var date = $('<p class="mb-0" />').text(entry.date);

            itemLeft.append(image)
            itemRight.append(type, title, summary, date)
            storyItem.append(itemLeft, itemRight);

            container.append(storyItem);
        });
    });
}

populateStoryFeed();
