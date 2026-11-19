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
// * Arena: katilinan turnuvaya (duraklatilmadiysa) yeniden baglaninca arena_join tekrar
//   gonderilir (sunucu kopan soketi kuyruktan dusurur; arena_join tekrarlanabilir).
//   Izlenen turnuvanin puan durumu yayinina da geri donulur.

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
        // Odaya seyirci olarak katildik; game_over Spectating'i dusurse de rovansta yayina doneriz
        private bool _spectatorRole;

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
        /// <summary>Bu baglantida arena_join yapilan turnuva (yoksa null); yeniden baglaninca geri katilir.</summary>
        public int? ArenaId { get; private set; }
        /// <summary>Katilinan turnuvada duraklatildi: yeniden baglaninca kuyruga sokulmaz.</summary>
        public bool ArenaPaused { get; private set; }
        /// <summary>Puan durumu izlenen turnuva (yoksa null); yeniden baglaninca yayina geri donulur.</summary>
        public int? WatchedArenaId { get; private set; }

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

        /// <summary>Oda kurar; timeControl ("3+2") verilirse sureli oda (null: eski yuk, suresiz).</summary>
        public void CreateGame(string userId, string authToken = null, string timeControl = null)
        {
            UserId = userId;
            AuthToken = authToken;
            RejoinToken = null;
            _spectatorRole = false;
            var payload = Identity();
            if (!string.IsNullOrEmpty(timeControl))
                payload["time_control"] = timeControl;
            Send(SocketEvents.CreateGame, Json.Serialize(payload));
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

        /// <summary>Hizli eslesme kuyruguna girer (create_game ile ayni kimlik alanlari).</summary>
        public void JoinQuickMatch(string userId, string authToken = null)
        {
            UserId = userId;
            AuthToken = authToken;
            RejoinToken = null;
            _spectatorRole = false;
            Send(SocketEvents.QuickMatchJoin, Json.Serialize(Identity()));
        }

        /// <summary>
        /// Kuyruktan cikar. Bagli degilken henuz gonderilmemis katilma istegi dusurulur
        /// (eski sunucu hic cevap vermese de arama boylece iptal edilebilir).
        /// </summary>
        public void CancelQuickMatch()
        {
            if (IsConnected)
            {
                _transport.Emit(SocketEvents.QuickMatchCancel, "{}");
                return;
            }
            var keep = new List<(string, string)>(_pending);
            _pending.Clear();
            foreach (var item in keep)
                if (item.Item1 != SocketEvents.QuickMatchJoin)
                    _pending.Enqueue(item);
        }

        /// <summary>Arena istekleri icin kimlik (oyun istekleri kendi kimligini verir).</summary>
        public void SetIdentity(string userId, string authToken)
        {
            UserId = userId;
            AuthToken = authToken;
        }

        /// <summary>Turnuva acar (kayitli kullanici; sure 15/30/60, baslangic 0-1440 dk sonra).</summary>
        public void CreateArena(int duration, int startInMinutes)
        {
            var payload = Identity();
            payload["duration"] = duration;
            payload["start_in_minutes"] = startInMinutes;
            Send(SocketEvents.ArenaCreate, Json.Serialize(payload));
        }

        /// <summary>Turnuvaya katilir (uyelik + duraklatmayi kaldirma + suruyorsa kuyruk).</summary>
        public void JoinArena(int id)
        {
            ArenaId = id;
            ArenaPaused = false;
            Send(SocketEvents.ArenaJoin, Json.Serialize(ArenaPayload(id, true)));
        }

        /// <summary>Puan durumunu izler (misafir de izleyebilir; kimlik gerekmez).</summary>
        public void WatchArena(int id)
        {
            WatchedArenaId = id;
            Send(SocketEvents.ArenaWatch, Json.Serialize(ArenaPayload(id, false)));
        }

        public void PauseArena(int id)
        {
            if (ArenaId == id)
                ArenaPaused = true;
            Send(SocketEvents.ArenaPause, Json.Serialize(ArenaPayload(id, true)));
        }

        public void ResumeArena(int id)
        {
            if (ArenaId == id)
                ArenaPaused = false;
            Send(SocketEvents.ArenaResume, Json.Serialize(ArenaPayload(id, true)));
        }

        /// <summary>Sunucunun bildirdigi duraklatma durumu (puan durumu satiri).</summary>
        public void SetArenaPaused(bool paused) => ArenaPaused = paused;

        /// <summary>Turnuva bitti / iptal: yeniden baglaninca katilinmaz.</summary>
        public void ForgetArena()
        {
            ArenaId = null;
            ArenaPaused = false;
        }

        private Dictionary<string, object> ArenaPayload(int id, bool identity)
        {
            var payload = identity ? Identity() : new Dictionary<string, object>();
            payload["tournament_id"] = id;
            return payload;
        }

        private bool PendingHas(string evt)
        {
            foreach (var item in _pending)
                if (item.evt == evt)
                    return true;
            return false;
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

        /// <summary>Hazir sohbet mesaji gonderir (yetki, numara ve 2 sn siniri sunucuda da denetlenir).</summary>
        public bool SendQuickChat(int msgId)
        {
            if (!IsConnected || RoomId == null)
                return false;
            _transport.Emit(SocketEvents.ChatQuick, Json.Serialize(new Dictionary<string, object>
            {
                ["room_id"] = RoomId,
                ["msg_id"] = msgId,
            }));
            return true;
        }

        /// <summary>Biten oyundan sonra ayni rakiple yeni oyun ister (sunucu iki koltuk da isteyince baslatir).</summary>
        public bool RequestRematch()
        {
            if (!IsConnected || RoomId == null)
                return false;
            _transport.Emit(SocketEvents.RematchRequest,
                            Json.Serialize(new Dictionary<string, object> { ["room_id"] = RoomId }));
            return true;
        }

        /// <summary>Oyundan bilerek ayril (aktif oyunda hukmen yenilgi).</summary>
        public void LeaveGame()
        {
            if (IsConnected && RoomId != null)
                _transport.Emit(SocketEvents.LeaveGame, Json.Serialize(new Dictionary<string, object> { ["room_id"] = RoomId }));
            InGame = false;
            Spectating = false;
            _spectatorRole = false;
        }

        public void Disconnect()
        {
            InGame = false;
            Spectating = false;
            _spectatorRole = false;
            _pending.Clear();
            _connecting = false;
            ArenaId = null;
            ArenaPaused = false;
            WatchedArenaId = null;
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
            // Arena: oyuna geri katildiktan sonra turnuvaya (bekleyen arena istegi yoksa).
            // Sunucu aktif macta oturan oyuncuyu kuyruga almaz; mac bitince kendisi alir.
            if (!PendingHas(SocketEvents.ArenaJoin) && !PendingHas(SocketEvents.ArenaWatch)
                && !PendingHas(SocketEvents.ArenaResume))
            {
                bool rejoined = ArenaId != null && !ArenaPaused && UserId != null;
                if (rejoined)
                {
                    Debug.Log("[GameSocket] Turnuvaya yeniden katiliniyor: " + ArenaId);
                    _transport.Emit(SocketEvents.ArenaJoin, Json.Serialize(ArenaPayload(ArenaId.Value, true)));
                }
                // arena_join turnuva odasina da sokar; baska (ya da duraklatilmis) turnuva izlenir
                if ((WatchedArenaId ?? ArenaId) is int watch && !(rejoined && watch == ArenaId))
                    _transport.Emit(SocketEvents.ArenaWatch, Json.Serialize(ArenaPayload(watch, false)));
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
                _spectatorRole = Spectating;
                RejoinToken = data.GetString("rejoin_token", RejoinToken);
            }
            else if (name == SocketEvents.GameStart)
            {
                // Rovansta koltuklar yer degistirir: yeni tas hamlede ve geri katilmada kullanilir
                RoomId = data.GetString("room_id", RoomId);
                MyPiece = data.GetInt("player_piece", MyPiece);
                InGame = true;
                Spectating = false;
            }
            else if (name == SocketEvents.RematchStarted)
            {
                if (_spectatorRole && !InGame && data.GetString("room_id", RoomId) == RoomId)
                    Spectating = true;   // yeni oyun da canli izlenir: kopunca yayina geri don
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
