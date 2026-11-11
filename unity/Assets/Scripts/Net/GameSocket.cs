// =============================================================================
// GameSocket.cs - Connect Four Pro Ultimate
// Oyun odasi baglantisi (src/network_client.py NetworkManager karsiligi)
// =============================================================================
//
// * Baglanti yoksa once baglanir, sonra bekleyen istegi gonderir.
// * Oda / tas bilgisini olaylardan takip eder.
// * Kopma sonrasi socket.io yeniden baglaninca oyuna otomatik geri katilir
//   (sunucu RECONNECT_GRACE_SECONDS icinde donen oyuncuyu kabul eder, NFR-08).
//   Seyirci de yeniden baglaninca yayina geri katilir (sunucu guncel durumu yollar).

using System;
using System.Collections.Generic;
using UnityEngine;

namespace ConnectFourPro.Net
{
    public sealed class GameSocket
    {
        private readonly ISocketTransport _transport;
        private readonly string _serverUrl;
        private readonly Queue<(string evt, string json)> _pending = new Queue<(string, string)>();
        private bool _connecting;

        public string RoomId { get; private set; }
        public int MyPiece { get; private set; }
        public string UserId { get; private set; }
        /// <summary>/login token'i (misafirde null); varsa sunucu user_id yerine buna bakar.</summary>
        public string AuthToken { get; private set; }
        /// <summary>Sunucunun verdigi koltuk anahtari; misafir yeniden baglanirken gonderir.</summary>
        public string RejoinToken { get; private set; }
        /// <summary>Oyuncu olarak bir odada (seyirci degil); yeniden baglaninca geri katilir.</summary>
        public bool InGame { get; private set; }
        /// <summary>Seyirci olarak bir odada; yeniden baglaninca yayina geri katilir.</summary>
        public bool Spectating { get; private set; }
        public bool IsConnected => _transport.IsConnected;

        /// <summary>Sunucu olayi (ad, veri) - ana thread'de.</summary>
        public event Action<string, JsonObject> ServerEvent;
        /// <summary>Sunucuya ulasilamadi.</summary>
        public event Action<string> ConnectionFailed;
        public event Action<string> ConnectionLost;

        public GameSocket(ISocketTransport transport, string serverUrl)
        {
            _transport = transport;
            _serverUrl = serverUrl;
            _transport.Connected += OnConnected;
            _transport.Disconnected += OnDisconnected;
            _transport.ConnectError += OnConnectError;
            _transport.EventReceived += OnEvent;
        }

        public void CreateGame(string userId, string authToken = null)
        {
            UserId = userId;
            AuthToken = authToken;
            RejoinToken = null;
            Send(SocketEvents.CreateGame, Json.Serialize(Identity()));
        }

        public void JoinGame(string roomId, string userId, string authToken = null)
        {
            UserId = userId;
            AuthToken = authToken;
            RejoinToken = null;
            var payload = Identity();
            payload["room_id"] = roomId;
            Send(SocketEvents.JoinGame, Json.Serialize(payload));
        }

        private Dictionary<string, object> Identity()
        {
            var payload = new Dictionary<string, object> { ["user_id"] = UserId };
            if (!string.IsNullOrEmpty(AuthToken))
                payload["token"] = AuthToken;
            return payload;
        }

        public void SendMove(int col)
        {
            if (!IsConnected || RoomId == null)
                return;
            _transport.Emit(SocketEvents.MakeMove, Json.Serialize(new Dictionary<string, object>
            {
                ["room_id"] = RoomId,
                ["col"] = col,
                ["player_piece"] = MyPiece,
            }));
        }

        /// <summary>Oyundan bilerek ayril (aktif oyunda hukmen yenilgi).</summary>
        public void LeaveGame()
        {
            if (IsConnected && RoomId != null)
                _transport.Emit(SocketEvents.LeaveGame, Json.Serialize(new Dictionary<string, object> { ["room_id"] = RoomId }));
            InGame = false;
            Spectating = false;
        }

        public void Disconnect()
        {
            InGame = false;
            Spectating = false;
            _pending.Clear();
            _connecting = false;
            _transport.Disconnect();
            RoomId = null;
            MyPiece = 0;
            RejoinToken = null;
        }

        /// <summary>Olay aboneliklerini kaldirir (nesne atilmadan once).</summary>
        public void Detach()
        {
            _transport.Connected -= OnConnected;
            _transport.Disconnected -= OnDisconnected;
            _transport.ConnectError -= OnConnectError;
            _transport.EventReceived -= OnEvent;
        }

        private void Send(string evt, string json)
        {
            if (IsConnected)
            {
                _transport.Emit(evt, json);
                return;
            }
            _pending.Enqueue((evt, json));
            if (!_connecting)
            {
                _connecting = true;
                _transport.Connect(_serverUrl);
            }
        }

        private void OnConnected()
        {
            _connecting = false;
            Debug.Log("[GameSocket] Sunucuya baglandi: " + _serverUrl);
            // Kopma sonrasi otomatik yeniden baglanma: oyuna geri don
            if ((InGame || Spectating) && RoomId != null && UserId != null && _pending.Count == 0)
            {
                Debug.Log("[GameSocket] Oyuna yeniden katiliniyor: " + RoomId);
                var payload = Identity();
                payload["room_id"] = RoomId;
                if (InGame && RejoinToken != null)
                    payload["rejoin_token"] = RejoinToken;
                _transport.Emit(SocketEvents.JoinGame, Json.Serialize(payload));
            }
            while (_pending.Count > 0)
            {
                var (evt, json) = _pending.Dequeue();
                _transport.Emit(evt, json);
            }
        }

        private void OnDisconnected(string reason)
        {
            Debug.Log("[GameSocket] Baglanti kesildi: " + reason);
            ConnectionLost?.Invoke(reason);
        }

        private void OnConnectError(string error)
        {
            Debug.LogWarning("[GameSocket] Baglanti hatasi: " + error);
            if (_connecting)
            {
                _connecting = false;
                _pending.Clear();
                ConnectionFailed?.Invoke(error);
            }
        }

        private void OnEvent(string name, string json)
        {
            JsonObject data;
            try
            {
                data = JsonObject.From(Json.Parse(json));
            }
            catch (JsonException e)
            {
                Debug.LogWarning($"[GameSocket] Gecersiz veri ({name}): {e.Message}");
                return;
            }

            if (name == SocketEvents.GameCreated || name == SocketEvents.GameJoined)
            {
                RoomId = data.GetString("room_id", RoomId);
                MyPiece = data.GetInt("player_piece", MyPiece);
                Spectating = data.GetString("role") == "spectator";
                InGame = !Spectating;
                RejoinToken = data.GetString("rejoin_token", RejoinToken);
            }
            else if (name == SocketEvents.GameOver)
            {
                InGame = false;
                Spectating = false;
            }
            ServerEvent?.Invoke(name, data);
        }
    }
}
