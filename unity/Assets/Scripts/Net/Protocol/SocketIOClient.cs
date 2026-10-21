// =============================================================================
// SocketIOClient.cs - Connect Four Pro Ultimate
// Kucuk bir Socket.IO v5 (Engine.IO v4) istemcisi, WebSocket uzerinden
// =============================================================================
//
// Unity Editor ve masaustu oyuncusunda kullanilir. WebGL'de tarayicinin
// WebSocket'i C#'tan kullanilamadigi icin orada resmi socket.io-client (JS)
// kullanilir (bkz. Plugins/WebGL/SocketBridge.jslib); iki taraf da
// ISocketTransport arayuzunun arkasindadir.
//
// Desteklenen protokol (python-socketio 5.x / python-engineio 4.x ile uyumlu):
//   Engine.IO: 0 open, 1 close, 2 ping, 3 pong, 4 message
//   Socket.IO: 0 CONNECT, 1 DISCONNECT, 2 EVENT, 4 CONNECT_ERROR (yalnizca "/" namespace)
// Ikili ekler ve ack'ler desteklenmez (sunucu kullanmiyor).
//
// Olaylar arka plan thread'inde tetiklenir; Unity tarafi bunlari ana thread'e
// tasimalidir (EditorSocketTransport bunu yapar).

using System;
using System.Collections.Generic;
using System.Net.WebSockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

namespace ConnectFourPro.Net
{
    public sealed class SocketIOClient : IDisposable
    {
        private readonly object _sendLock = new object();
        private ClientWebSocket _ws;
        private CancellationTokenSource _cts;
        private Task _sendChain = Task.CompletedTask;
        private int _generation;

        public bool IsConnected { get; private set; }

        /// <summary>Socket.IO namespace baglantisi kuruldu.</summary>
        public event Action Connected;
        /// <summary>Baglanti kapandi (neden).</summary>
        public event Action<string> Disconnected;
        /// <summary>Baglanti kurulamadi (hata mesaji).</summary>
        public event Action<string> ConnectError;
        /// <summary>Sunucu olayi: (ad, JSON veri; veri yoksa "null").</summary>
        public event Action<string, string> EventReceived;

        /// <summary>http(s)://host:port adresini Engine.IO WebSocket adresine cevirir.</summary>
        public static Uri BuildUri(string serverUrl)
        {
            string url = serverUrl.TrimEnd('/');
            if (url.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
                url = "wss://" + url.Substring(8);
            else if (url.StartsWith("http://", StringComparison.OrdinalIgnoreCase))
                url = "ws://" + url.Substring(7);
            else if (!url.StartsWith("ws://", StringComparison.OrdinalIgnoreCase)
                     && !url.StartsWith("wss://", StringComparison.OrdinalIgnoreCase))
                url = "ws://" + url;
            return new Uri(url + "/socket.io/?EIO=4&transport=websocket");
        }

        public void Connect(string serverUrl, TimeSpan? timeout = null)
        {
            Close("yeniden baglaniliyor", raiseEvent: false);
            int generation = Interlocked.Increment(ref _generation);
            _cts = new CancellationTokenSource();
            _ws = new ClientWebSocket();
            var ws = _ws;
            var token = _cts.Token;
            _ = Task.Run(() => RunAsync(ws, BuildUri(serverUrl), timeout ?? TimeSpan.FromSeconds(5), generation, token));
        }

        private async Task RunAsync(ClientWebSocket ws, Uri uri, TimeSpan timeout, int generation, CancellationToken token)
        {
            try
            {
                using (var connectCts = CancellationTokenSource.CreateLinkedTokenSource(token))
                {
                    connectCts.CancelAfter(timeout);
                    await ws.ConnectAsync(uri, connectCts.Token).ConfigureAwait(false);
                }
            }
            catch (Exception e)
            {
                if (generation == _generation)
                    ConnectError?.Invoke(e.Message);
                return;
            }

            var buffer = new byte[16 * 1024];
            var message = new StringBuilder();
            string closeReason = "transport close";
            try
            {
                while (!token.IsCancellationRequested && ws.State == WebSocketState.Open)
                {
                    message.Clear();
                    WebSocketReceiveResult result;
                    do
                    {
                        result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), token).ConfigureAwait(false);
                        if (result.MessageType == WebSocketMessageType.Close)
                            break;
                        message.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                    } while (!result.EndOfMessage);

                    if (result.MessageType == WebSocketMessageType.Close)
                        break;
                    if (generation != _generation)
                        return;
                    HandlePacket(message.ToString());
                }
            }
            catch (OperationCanceledException)
            {
                closeReason = "io client disconnect";
            }
            catch (Exception e)
            {
                closeReason = e.Message;
            }

            if (generation == _generation && IsConnected)
            {
                IsConnected = false;
                Disconnected?.Invoke(closeReason);
            }
            else if (generation == _generation)
            {
                ConnectError?.Invoke(closeReason);
            }
        }

        private void HandlePacket(string packet)
        {
            if (packet.Length == 0)
                return;
            switch (packet[0])
            {
                case '0':   // Engine.IO open -> namespace'e baglan
                    Send("40");
                    break;
                case '1':   // Engine.IO close
                    Close("transport close", raiseEvent: true);
                    break;
                case '2':   // ping -> pong
                    Send("3" + packet.Substring(1));
                    break;
                case '4':
                    HandleSocketIO(packet.Substring(1));
                    break;
            }
        }

        private void HandleSocketIO(string p)
        {
            if (p.Length == 0)
                return;
            char type = p[0];
            string body = p.Substring(1);
            // Namespace ("/ns,") yalnizca kok namespace kullanildigi icin atlanir
            if (body.StartsWith("/"))
            {
                int comma = body.IndexOf(',');
                body = comma >= 0 ? body.Substring(comma + 1) : "";
            }
            switch (type)
            {
                case '0':   // CONNECT
                    IsConnected = true;
                    Connected?.Invoke();
                    break;
                case '1':   // DISCONNECT (sunucu tarafindan)
                    Close("io server disconnect", raiseEvent: true);
                    break;
                case '2':   // EVENT: [ad, veri]
                    // Ack kimligi (rakamlar) varsa atla
                    int i = 0;
                    while (i < body.Length && char.IsDigit(body[i]))
                        i++;
                    if (Json.Parse(body.Substring(i)) is List<object> items && items.Count > 0 && items[0] is string name)
                        EventReceived?.Invoke(name, Json.Serialize(items.Count > 1 ? items[1] : null));
                    break;
                case '4':   // CONNECT_ERROR
                    ConnectError?.Invoke(body);
                    break;
            }
        }

        /// <summary>Olay gonderir; veri JSON metnidir ("null" veya bos: verisiz).</summary>
        public void Emit(string eventName, string jsonData)
        {
            if (!IsConnected)
                return;
            string name = Json.Serialize(eventName);
            string payload = string.IsNullOrEmpty(jsonData) || jsonData == "null"
                ? "42[" + name + "]"
                : "42[" + name + "," + jsonData + "]";
            Send(payload);
        }

        private void Send(string text)
        {
            var ws = _ws;
            var token = _cts?.Token ?? CancellationToken.None;
            if (ws == null)
                return;
            byte[] bytes = Encoding.UTF8.GetBytes(text);
            // ClientWebSocket ayni anda tek SendAsync kabul eder: gonderimler zincirlenir
            lock (_sendLock)
            {
                _sendChain = _sendChain.ContinueWith(async _ =>
                {
                    if (ws.State == WebSocketState.Open)
                        await ws.SendAsync(new ArraySegment<byte>(bytes), WebSocketMessageType.Text, true, token)
                                .ConfigureAwait(false);
                }, TaskScheduler.Default).Unwrap();
            }
        }

        public void Disconnect() => Close("io client disconnect", raiseEvent: true);

        private void Close(string reason, bool raiseEvent)
        {
            var ws = _ws;
            var cts = _cts;
            bool wasConnected = IsConnected;
            if (ws == null)
                return;
            if (ws.State == WebSocketState.Open && wasConnected)
            {
                try
                {
                    Send("41");
                    _sendChain.Wait(500);
                }
                catch (Exception)
                {
                    // Kapanirken gonderim hatasi onemsiz
                }
            }
            Interlocked.Increment(ref _generation);   // eski okuma dongusunun olaylarini sustur
            IsConnected = false;
            _ws = null;
            _cts = null;
            try
            {
                cts?.Cancel();
                ws.Abort();
                ws.Dispose();
            }
            catch (Exception)
            {
                // zaten kapali
            }
            if (raiseEvent && wasConnected)
                Disconnected?.Invoke(reason);
        }

        public void Dispose() => Close("dispose", raiseEvent: false);
    }
}
