var AUTHENTICATION_COOKIE = 'sessionAuthenticated';
var COUNTER_COOKIE = 'searchCount';

var SIGNUP_FORM_ID = '#fbf1d375-61ec-433d-943f-8d4e6e3ae35a';
var SUBMIT_BUTTON_SELECTOR = SIGNUP_FORM_ID + ' button';
var $target;

function setCookie(cname, cvalue, exdays) {
  var d = new Date();
  d.setTime(d.getTime() + exdays * 24 * 60 * 60 * 1000);
  var expires = 'expires=' + d.toUTCString();
  document.cookie = cname + '=' + cvalue + ';' + expires + ';path=/';
}

function readCookie(name) {
  var nameEQ = name + "=";
  var ca = document.cookie.split(';');
  for(var i=0;i < ca.length;i++) {
    var c = ca[i];
    while (c.charAt(0)==' ') c = c.substring(1,c.length);
    if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length,c.length);
  }
  return null;
}

function incrementCounterCookie() {
  var search_count = readCookie(COUNTER_COOKIE);

  if (search_count === null) {
    search_count = 0;
  }

  search_count++;
  setCookie(COUNTER_COOKIE, search_count, 3000);
}

function showEmailModal(settings) {
  $('#emailModal').modal({
      'backdrop': 'static'  // Disallow close on click
  });

  $('body').addClass('modal-open');
}

function hideEmailModal(settings) {
  $('#emailModal').modal('hide');
  $('body').removeClass('modal-open');
}

function checkExistsThen(selector, callback) {
  var checkExist = setInterval(function() {
    $target = $(selector);

    if ($target.length) {
      clearInterval(checkExist);
      callback();
    }
  }, 1000);
}

function sessionAuthenticated() {
  return readCookie(AUTHENTICATION_COOKIE);
}

function unauthenticatedSearchExceeded(n=3) {
  return parseInt(readCookie(COUNTER_COOKIE)) > n;
}

if (!sessionAuthenticated() & unauthenticatedSearchExceeded()) {
  showEmailModal();

  // When the submit button is shown, extend its click function to add an
  // authentication cookie and hide the modal, given a successful email
  // submission.
  checkExistsThen(SUBMIT_BUTTON_SELECTOR, function overrideClickEvent() {
    var $button = $target;
    var submitFunc = $button.attr('onclick');

    $button.attr('onclick', null);

    $button.on('click', function(event) {
      event.preventDefault();

      var validSubmission = eval(submitFunc) != false;

      if (validSubmission) {
        setCookie(AUTHENTICATION_COOKIE, '1', 3000);

        setTimeout(function() {
          hideEmailModal();
        }, 3000);
      }
    });
  });
}
