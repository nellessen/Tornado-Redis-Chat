/**
 * Initiate global websocket object.
 * @todo: Add user cookie for authentication.
 */
var host = location.origin.replace(/^http/, 'ws')
var ws = new WebSocket(host +"/socket/" + location.pathname.replace('/room/', '').replace('/', ''));


/**
 * Helper function to get the value of a cookie.
 */
function cookie(name) {
    var r = document.cookie.match("\\b" + name + "=([^;]*)\\b");
    return r ? r[1] : undefined;
}


$(document).ready(function() {
    if (!window.console) window.console = {};
    if (!window.console.log) window.console.log = function() {};

    // Bind the submit event of the form input to postMessage().
    $("#chat-input").submit(function() {
        postMessage($(this));
        return false;
    });
    $("#message-input").focus();
    $('html, body').animate({scrollTop: $(document).height()}, 800);
    
    // Connection state should be reflacted in submit button.
    var disabled = $("form#chat-input").find("input");
    disabled.attr("disabled", "disabled");

    // Websocket callbacks:
    ws.onopen = function() {
        console.log("Connected...");
        disabled.removeAttr("disabled");
    };
    ws.onmessage = function(event) {
        data = JSON.parse(event.data);
        if(data.textStatus && data.textStatus == "unauthorized") {
            alert("unauthorized");
            disabled.attr("disabled", "disabled");
        }
        else if(data.error && data.textStatus) {
            alert(data.textStatus);
        }
        console.log("New Message", data);
        if (data.messages) newMessages(data);
    };
    ws.onclose = function() {
        // @todo: Implement reconnect.
        console.log("Closed!");
        disabled.attr("disabled", "disabled");
    };
});


/**
 * Function to create a new message.
 */
function postMessage(form) {
    var value = form.find("input[type=text]").val();
    var message = {body: value};
    message._xsrf = cookie("_xsrf");
    message.user = cookie("user");
    var disabled = form.find("input");
    disabled.attr("disabled", "disabled");
    // Send message using websocket.
    ws.send(JSON.stringify(message));
    // @todo: A response if successful would be nice. 
    console.log("Created message (successfuly)");
    $("#message-input").val("").select();
    disabled.removeAttr("disabled");
}


/**
 * Callback when receiving new messages.
 */
updater = {}
newMessages = function (data) {
    var messages = data.messages;
    if(messages.length == 0) return;
    updater.cursor = messages[messages.length - 1]._id;
    console.log(messages.length + "new messages, cursor: " + updater.cursor);
    for (var i = 0; i < messages.length; i++) {
        showMessage(messages[i]);
    }
};


/**
 * Function to add a bunch of (new) messages to the inbox.
 */
showMessage = function(message) {
    console.log("Show Message");
    var existing = $("#m" + message._id);
    if (existing.length > 0) return;
    $("#messsages").append('<div style="display: none;" class="message" id="' + message._id + '"><b>' + message.from + ': </b>' + message.body + '</div>');
    $('#messsages').find(".message:last").slideDown("fast", function(){
        $('html, body').animate({scrollTop: $(document).height()}, 400);
    });
};
