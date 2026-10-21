// =============================================================================
// SocketBridge.jslib - Connect Four Pro Ultimate
// Unity WebGL <-> tarayicidaki socket.io-client v4 koprusu
// =============================================================================
//
// socket.io-client, WebGL sablonundaki index.html tarafindan yuklenir
// (WebGLTemplates/ConnectFour/socket.io.min.js). Olaylar C# tarafina
// SendMessage ile "olay_adi\n{json}" bicimiyle iletilir.

mergeInto(LibraryManager.library, {
  CF4_SocketConnect: function (urlPtr, goPtr) {
    var url = UTF8ToString(urlPtr);
    var go = UTF8ToString(goPtr);
    if (typeof io === 'undefined') {
      SendMessage(go, 'OnSocketError', 'socket.io-client yuklenemedi');
      return;
    }
    if (window.cf4Socket) {
      window.cf4Socket.removeAllListeners();
      window.cf4Socket.offAny();
      window.cf4Socket.disconnect();
    }
    var socket = url ? io(url, { reconnectionAttempts: 5 }) : io({ reconnectionAttempts: 5 });
    window.cf4Socket = socket;
    var current = function () { return window.cf4Socket === socket; };

    socket.on('connect', function () {
      if (current()) SendMessage(go, 'OnSocketConnected', '');
    });
    socket.on('disconnect', function (reason) {
      if (current()) SendMessage(go, 'OnSocketDisconnected', String(reason));
    });
    socket.on('connect_error', function (err) {
      if (current()) SendMessage(go, 'OnSocketError', err && err.message ? err.message : String(err));
    });
    socket.onAny(function (name, data) {
      if (!current()) return;
      SendMessage(go, 'OnSocketEvent', name + '\n' + JSON.stringify(data === undefined ? null : data));
    });
  },

  CF4_SocketEmit: function (eventPtr, jsonPtr) {
    var socket = window.cf4Socket;
    if (!socket || !socket.connected) return;
    var name = UTF8ToString(eventPtr);
    var json = UTF8ToString(jsonPtr);
    var data = null;
    try {
      data = JSON.parse(json);
    } catch (e) {
      console.error('[CF4] Gecersiz JSON:', json);
      return;
    }
    if (data === null) socket.emit(name);
    else socket.emit(name, data);
  },

  CF4_SocketDisconnect: function () {
    var socket = window.cf4Socket;
    if (!socket) return;
    window.cf4Socket = null;
    socket.removeAllListeners();
    socket.offAny();
    socket.disconnect();
  },

  // Sayfanin adresi (http://host:port); oyun Flask'in /play rotasindan sunulur
  CF4_PageOrigin: function () {
    var origin = window.location.origin || '';
    var size = lengthBytesUTF8(origin) + 1;
    var buffer = _malloc(size);
    stringToUTF8(origin, buffer, size);
    return buffer;
  },

  // ?server=http://... sorgu parametresi (baska sunucuya baglanmak icin)
  CF4_QueryParam: function (namePtr) {
    var name = UTF8ToString(namePtr);
    var value = '';
    try {
      value = new URLSearchParams(window.location.search).get(name) || '';
    } catch (e) {
      value = '';
    }
    var size = lengthBytesUTF8(value) + 1;
    var buffer = _malloc(size);
    stringToUTF8(value, buffer, size);
    return buffer;
  },
});
