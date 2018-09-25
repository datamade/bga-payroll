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

var SIGNUP_FORM_ID = '#fbf1d375-61ec-433d-943f-8d4e6e3ae35a';
var SELECTOR = SIGNUP_FORM_ID + ' button';
var $target;

function checkExistThen(selector, callback) {
  var checkExist = setInterval(function() {
    $target = $(selector);

    if ($target.length) {
      clearInterval(checkExist);
      callback();
    }
  }, 1000);
}

if (!readCookie('SESSpopupsearchlockoutbypass')) {
  showEmailModal();

  checkExistThen(SELECTOR, function overrideClickEvent() {
    var $button = $target;
    var $onClickFunc = $button.attr('onclick');

    $button.attr('onclick', null);

    $button.on('click', function(event) {
      event.preventDefault();

      if (eval($onClickFunc) != false) {
        setCookie('SESSpopupsearchlockoutbypass', '1', 3000);
        setTimeout(function() {
          hideEmailModal();
        }, 3000);
      }
    });
  });
}
