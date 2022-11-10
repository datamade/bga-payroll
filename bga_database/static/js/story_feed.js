function populateStoryFeed() {
    $.get('/story-feed/', function (data) {
        var container = $('#story-feed-stories');

        $.each(data.entries, function (idx, entry) {
            var storyItem = $('<div class="p-3 story-item" />');
            
            var itemLeft = $('<div class="story-img col-md-4"/>');
            var itemRight = $('<div />');

            var summary = $('<p class="text-serif my-2" />').html(entry.summary);
            var summaryEl = document.createElement('div');
            summaryEl.innerHTML = entry.summary;

            imgSrc = summaryEl.querySelectorAll('img')[0].src;

            var image = $('<a />').attr({
                'href': entry.link,
                'target': '_blank'
            });
            
            image.append(
                $('<img />').attr({
                    'src': imgSrc
                })
            );

            var type = $('<div class="text-uppercase story-detail mb-2"/>').text(
                    entry.tags[entry.tags.length - 1].term
                );

            // Giving this a class of h3 applies size
            var title = $('<h5 class="h3 text-black"/>').append(
                $('<a />').attr({
                    'href': entry.link,
                    'target': '_blank'
                }).text(entry.title)
            );

            var brief = summaryEl.querySelectorAll('p')[0].innerText;

            var details = $('<p class="mb-0 mt-2 story-detail" />').text(
                entry.date + " - By " + entry.author
            );

            itemLeft.append(image);
            itemRight.append(type, title, brief, details);
            storyItem.append(itemLeft, itemRight);

            container.append(storyItem);
        });
    });
}

populateStoryFeed();
