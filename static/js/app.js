function validateForm(formId) {
  errors = false;
  $("#"+formId+" :input.required").each(function(i, f){
    if ($(f).val() == '') {
      $(f).parent().parent().addClass('error');
      errors = true;
    } else {
      $(f).parent().parent().removeClass('error');
    }
  });
  if (errors) {
    return false;
  } else {
    return true;
  }
}
function flash(text, status){
  var msg = $("<div class='alert-message message fade in' data-alert='alert'></div>");
  msg.addClass(status);
  msg.append("<a class='close' href='#'>x</a>");
  msg.append('<p>'+text+'</p>');
  $("#messages").append(msg);
  $("#messages").removeClass('hide');
  $(".alert-message").alert();
  $(".alert-message").delay(5000).fadeOut();
}
