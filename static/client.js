var socket = io.connect("http://" + document.domain + ":" + location.port, {
    transports: ["websocket"],
});

socket.on("connect", function () {
    console.log("Connected to server");
    document.getElementById("message").innerHTML = "Connected to server";
});

socket.on("connect_error", function (error) {
    console.log("Connection error:", error);
    document.getElementById("message").innerHTML = ("Connection error:", error);
});

socket.on("state", function (msg) {
    document.getElementById("state").innerHTML = msg.state;
});

socket.on("ms", function (msg) {
    console.log("Received message:", msg);

    var sanitizedMsg = sanitizeInput(msg.ms);
    var replacedMsg = replacePolishDiacritics(sanitizedMsg);

    document.getElementById("message").innerHTML = replacedMsg;
});

function sanitizeInput(str) {
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

function replacePolishDiacritics(str) {
    var replacements = {
        "&lt;ALT + a&gt;": "ą",
        "&lt;ALT + c&gt;": "ć",
        "&lt;ALT + e&gt;": "ę",
        "&lt;ALT + l&gt;": "ł",
        "&lt;ALT + n&gt;": "ń",
        "&lt;ALT + o&gt;": "ó",
        "&lt;ALT + s&gt;": "ś",
        "&lt;ALT + z&gt;": "ź",
        "&lt;ALT + x&gt;": "ż",
        "&lt;ALT + A&gt;": "Ą",
        "&lt;ALT + C&gt;": "Ć",
        "&lt;ALT + E&gt;": "Ę",
        "&lt;ALT + L&gt;": "Ł",
        "&lt;ALT + N&gt;": "Ń",
        "&lt;ALT + O&gt;": "Ó",
        "&lt;ALT + S&gt;": "Ś",
        "&lt;ALT + Z&gt;": "Ź",
        "&lt;ALT + X&gt;": "Ż",
        "&lt;br&gt;": "<br>",
    };

    for (var key in replacements) {
        str = str.split(key).join(replacements[key]);
    }

    return str;
}
