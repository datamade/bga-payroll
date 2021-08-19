import pytest


@pytest.mark.django_db
def test_malicious_input(client, show_donate, donate_message):
    donate_message.value = "<script>console.log('oh no!')</script>"
    donate_message.save()

    request = client.get('/')

    # test to see if the script was sanitized
    sanitized = "&lt;script&gt;console.log('oh no!')&lt;/script&gt;"
    assert sanitized in request.rendered_content

    # double check this isn't lurking in the html somewhere
    assert donate_message.value not in request.rendered_content


@pytest.mark.django_db
def test_valid_user_input(client, show_donate, donate_message, allowed_input):
    donate_message.value = allowed_input
    donate_message.save()

    request = client.get('/')

    assert '<strong>Dear BGA readers,</strong>' in request.rendered_content
    assert donate_message.value in request.rendered_content


@pytest.mark.django_db
def test_no_message(client, show_donate, donate_message):
    # turn off the banner
    show_donate.value = False
    show_donate.save()

    # write and save a draft message
    donate_message.value = '<p>draft: donate message</p>'
    donate_message.save()

    # whoops!
    request = client.get('/')

    # whew, glad i turned it off.
    assert donate_message.value not in request.rendered_content
