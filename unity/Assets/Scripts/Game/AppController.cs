// =============================================================================
// AppController.cs - Connect Four Pro Ultimate
// Uygulama durum makinesi (src/gui_app.py ConnectFourGUI'nin mantik kismi)
// =============================================================================
//
// Ekranlar: Giris/Kayit, Ana Menu, AI zorluk secimi, Online Lobi, Rakip bekleme,
// Oyun (AI / Online / Seyirci), Liderlik Tablosu, Mac Gecmisi.
//
// Cizim UI katmanindadir (UI/*View.cs); bu sinif yalnizca durumu tutar ve
// degistirir. Tum geri cagrilar (REST, Socket.IO, AI) Unity ana thread'inde
// calisir; Python surumundeki kilitlere gerek yoktur.

using System;
using System.Collections.Generic;
using ConnectFourPro.AI;
using ConnectFourPro.Core;
using ConnectFourPro.Net;
using UnityEngine;

namespace ConnectFourPro.Game
{
    public enum AppScreen
    {
        Login,
        Menu,
        AISelect,
        Lobby,
        Waiting,
        PlayingAI,
        PlayingOnline,
        Spectating,
        Leaderboard,
        History,
    }

    public enum StatusTone
    {
        Neutral,
        Good,
        Bad,
    }

    public sealed class AnalysisSummary
    {
        public int TotalMoves;
        public double MyAccuracy;
        public double OpponentAccuracy;
    }

    public sealed class AppController
    {
        public const int AnalysisDepth = 8;
        public const float LeaveConfirmSeconds = 3f;
        public const double AIMoveDelaySeconds = 0.3;
        public const float LobbyRefreshSeconds = 2f;
        public const int UsernameMinLength = 3;
        public const int UsernameMaxLength = 20;
        public const int PasswordMinLength = 8;
        public const int ReconnectGraceDefault = 30;

        private readonly ApiClient _api;
        private readonly ISocketTransport _transport;
        private readonly AIRunner _ai = new AIRunner();
        private GameSocket _socket;

        // Animasyon: UI katmani saglar (BoardView)
        public Func<bool> IsAnimating = () => false;
        public Action<int, int, int, Action> AnimateDrop = (col, row, piece, done) => done();
        public Action FinishAnimation = () => { };
        public Action CancelAnimation = () => { };

        public AppScreen Screen { get; private set; } = AppScreen.Login;
        public GameState Game { get; private set; } = new GameState();
        public AIEngine Engine { get; private set; }
        public bool AIThinking { get; private set; }
        public bool IsSpectator { get; private set; }

        // Kullanici
        public string Username { get; private set; } = "";
        public bool IsGuest { get; private set; }
        /// <summary>/login (veya /signup) token'i; sunucu kayitli kimligi bununla dogrular. Misafirde null.</summary>
        private string _authToken;
        // Her giris/kayit istegi bir donem alir; misafir girisi/cikis donemi ilerletir,
        // boylece gec gelen eski yanit yeni oturumu ezmez.
        private int _authEpoch;
        public int UserElo { get; private set; } = UserInfo.DefaultRating;
        public bool AuthPending { get; private set; }
        public string OpponentName { get; private set; } = "Rakip";
        public int OpponentElo { get; private set; } = UserInfo.DefaultRating;

        // Online
        public int MyPiece { get; private set; } = Board.Player1;
        public string RoomId { get; private set; }
        public int? LastEloChange { get; private set; }
        private string _finalStatus;
        private float _leaveConfirmUntil;
        // Kendi baglantimiz koptugunda zaman (-1: bagli). Sayac yerel tahmindir;
        // sunucunun bekleme suresi kopmayi fark ettiginde baslar.
        private float _lostAt = -1f;
        private int _lostShownSeconds = -1;
        // Rakip koptu: sunucunun verdigi bekleme suresinin bitis zamani (-1: yok)
        private float _opponentDeadline = -1f;
        private int _opponentShownSeconds = -1;
        // Oturum artik ilerleyemez (oda kapandi, geri donus reddedildi, baglanti donmedi)
        // ama Game.GameOver da degil: hamle engellenir, cikis onay istemez.
        private bool _sessionDead;
        // join_game gonderildi, yanit (game_joined/game_start/error) bekleniyor:
        // cift tiklama ikinci istegi gondermesin
        private bool _joinPending;
        public (string p1, int p1Elo, string p2, int p2Elo) SpectateNames { get; private set; } =
            ("Oyuncu 1", UserInfo.DefaultRating, "Oyuncu 2", UserInfo.DefaultRating);

        // Ekran verileri
        public List<ActiveGame> ActiveGames { get; private set; } = new List<ActiveGame>();
        public int ActiveGamesVersion { get; private set; }
        private float _lastLobbyRefresh = -100f;
        private bool _lobbyFetching;
        public List<UserInfo> LeaderboardData { get; private set; }
        public bool LeaderboardError { get; private set; }
        public List<HistoryEntry> HistoryData { get; private set; }
        public bool HistoryError { get; private set; }

        // Hamle analizi (online oyunlarda)
        public bool AnalysisEnabled = true;
        private readonly List<(int player, bool wasBest)> _analysis = new List<(int, bool)>();
        // Tick'te ozet yalnizca yeni analiz eklenince yeniden hesaplanir (her kare nesne uretme)
        private int _summaryCount = -1;
        public AnalysisSummary Summary { get; private set; }

        public string Status { get; private set; } = "";
        public StatusTone Tone { get; private set; }

        /// <summary>Ekran degisti (UI gorunurlugu gunceller).</summary>
        public event Action<AppScreen> ScreenChanged;
        /// <summary>Giris alanlari temizlenmeli.</summary>
        public event Action InputsCleared;

        public string ServerUrl => _api.BaseUrl;

        public AppController(MonoBehaviour host, string serverUrl, ISocketTransport transport)
            : this(new ApiClient(host, serverUrl), transport)
        {
            Debug.Log("[App] Hazir (sunucu: " + serverUrl + ")");
        }

        /// <summary>ApiClient disaridan verilir (tests/csharp sahte istemciyle kurar).</summary>
        public AppController(ApiClient api, ISocketTransport transport)
        {
            _api = api;
            _transport = transport;
            _socket = NewSocket();
        }

        private GameSocket NewSocket()
        {
            var socket = new GameSocket(_transport, _api.BaseUrl);
            socket.ServerEvent += OnServerEvent;
            socket.ConnectionFailed += _ => ConnectionFailed();
            socket.ConnectionLost += OnConnectionLost;
            return socket;
        }

        private void SetScreen(AppScreen screen)
        {
            if (Screen == screen)
                return;
            Screen = screen;
            ScreenChanged?.Invoke(screen);
        }

        public void SetStatus(string text, StatusTone tone = StatusTone.Neutral)
        {
            Status = text ?? "";
            Tone = tone;
        }

        // =====================================================================
        // Her kare
        // =====================================================================

        public void Tick()
        {
            _ai.Tick();
            if (Screen == AppScreen.Lobby && Time.unscaledTime - _lastLobbyRefresh > LobbyRefreshSeconds)
                RefreshActiveGames();
            if (Screen == AppScreen.PlayingOnline && Game.GameOver && _analysis.Count != _summaryCount)
            {
                _summaryCount = _analysis.Count;
                Summary = ComputeSummary();   // analizler oyun bittikten sonra da tamamlanabilir
            }
            TickConnectionCountdowns();
        }

        public bool LeaveConfirmPending => Time.unscaledTime < _leaveConfirmUntil;

        /// <summary>Kendi sunucu baglantimiz oyun/yayin sirasinda koptu; yeniden baglaniliyor.</summary>
        public bool Offline => _lostAt >= 0f;

        /// <summary>Online oturum sona erdi (oyun bitmeden); yalnizca cikis mumkun.</summary>
        public bool SessionDead => _sessionDead;

        private void TickConnectionCountdowns()
        {
            bool live = (Screen == AppScreen.PlayingOnline || Screen == AppScreen.Spectating) && !Game.GameOver;
            // Cikis onayi metni sayacla ezilmesin
            if (!live || LeaveConfirmPending)
                return;
            if (Offline && !_sessionDead)
            {
                int left = (int)Math.Ceiling(ReconnectGraceDefault - (Time.unscaledTime - _lostAt));
                if (left <= 0)
                {
                    _sessionDead = true;
                    SetStatus(IsSpectator
                        ? "Yayın bağlantısı geri gelmedi. Lobiye dönüp tekrar izleyebilirsin."
                        : "Sunucuya yeniden bağlanılamadı. Oyun hükmen kaybedilmiş olabilir; lobiye dönebilirsin.",
                        StatusTone.Bad);
                }
                else if (left != _lostShownSeconds)
                {
                    _lostShownSeconds = left;
                    SetStatus($"Bağlantı koptu! Yeniden bağlanılıyor... ({left} sn)", StatusTone.Bad);
                }
                return;
            }
            if (_opponentDeadline >= 0f && Screen == AppScreen.PlayingOnline)
            {
                int left = Math.Max(0, (int)Math.Ceiling(_opponentDeadline - Time.unscaledTime));
                if (left != _opponentShownSeconds)
                {
                    _opponentShownSeconds = left;
                    SetStatus($"Rakibin bağlantısı koptu! {left} sn içinde dönmezse kazanırsın.", StatusTone.Bad);
                }
            }
        }

        private void ClearConnectionState()
        {
            _lostAt = -1f;
            _lostShownSeconds = -1;
            _opponentDeadline = -1f;
            _opponentShownSeconds = -1;
            _sessionDead = false;
        }

        public bool CanHumanMove()
        {
            if (IsAnimating() || Game.GameOver || IsSpectator)
                return false;
            if (Screen == AppScreen.PlayingAI)
                return Game.CurrentPlayer == Board.Player1 && !AIThinking && Engine != null;
            if (Screen == AppScreen.PlayingOnline)
                return Game.CurrentPlayer == MyPiece && !Offline && !_sessionDead && _socket.IsConnected;
            return false;
        }

        /// <summary>Oyuncunun hover'da gosterilecek tas rengi.</summary>
        public int HumanPiece => Screen == AppScreen.PlayingAI ? Board.Player1 : MyPiece;

        /// <summary>Bilgi panelinde "(Sen)" etiketi: bu tas yerel oyuncunun mu.</summary>
        public bool IsLocalPiece(int piece) =>
            !IsSpectator && (Screen == AppScreen.PlayingAI || Screen == AppScreen.PlayingOnline) && piece == HumanPiece;

        /// <summary>(p1 adi, p1 elo, p2 adi, p2 elo); elo null ise gosterilmez.</summary>
        public (string p1, int? p1Elo, string p2, int? p2Elo) PlayerLabels()
        {
            if (Screen == AppScreen.PlayingAI)
                return (Username, UserElo, $"AI (D{Engine?.Depth.ToString() ?? "?"})", null);
            if (IsSpectator)
                return (SpectateNames.p1, SpectateNames.p1Elo, SpectateNames.p2, SpectateNames.p2Elo);
            if (MyPiece == Board.Player1)
                return (Username, UserElo, OpponentName, OpponentElo);
            return (OpponentName, OpponentElo, Username, UserElo);
        }

        // =====================================================================
        // Kimlik dogrulama
        // =====================================================================

        public void Login(string username, string password)
        {
            if (AuthPending)
                return;
            username = (username ?? "").Trim();
            if (username.Length == 0 || string.IsNullOrEmpty(password))
            {
                SetStatus("Kullanıcı adı ve şifre gerekli!", StatusTone.Bad);
                return;
            }
            AuthPending = true;
            int epoch = ++_authEpoch;
            SetStatus("Giriş yapılıyor...", StatusTone.Good);
            _api.Login(username, password, r =>
            {
                if (epoch != _authEpoch)
                    return;   // bu arada misafir girisi/cikis yapildi
                AuthPending = false;
                if (r.NetworkError)
                    SetStatus("Sunucuya bağlanılamadı!", StatusTone.Bad);
                else if (r.Status == 200)
                {
                    var user = UserInfo.From(r.BodyObject.GetObject("user"), username);
                    EnterMenu(user.Username, user.Rating, false, r.BodyObject.GetString("token"));
                    SetStatus($"Hoş geldin {Username}!", StatusTone.Good);
                }
                else if (r.Status == 401)
                    SetStatus("Yanlış kullanıcı adı veya şifre!", StatusTone.Bad);
                else if (r.Status == 429)
                    SetStatus("Çok fazla deneme! Biraz sonra tekrar deneyin.", StatusTone.Bad);
                else if (r.Status == 503)
                    SetStatus("Sunucu veritabanına ulaşamıyor. Misafir olarak devam edebilirsiniz.", StatusTone.Bad);
                else
                    SetStatus("Giriş başarısız!", StatusTone.Bad);
            });
        }

        public void Register(string username, string password)
        {
            if (AuthPending)
                return;
            username = (username ?? "").Trim();
            if (username.Length == 0 || string.IsNullOrEmpty(password))
            {
                SetStatus("Kullanıcı adı ve şifre gerekli!", StatusTone.Bad);
                return;
            }
            if (username.Length < UsernameMinLength || password.Length < PasswordMinLength)
            {
                SetStatus($"Kullanıcı adı en az {UsernameMinLength}, şifre en az {PasswordMinLength} karakter olmalı!", StatusTone.Bad);
                return;
            }
            AuthPending = true;
            int epoch = ++_authEpoch;
            SetStatus("Hesap oluşturuluyor...", StatusTone.Good);
            _api.Signup(username, password, r =>
            {
                if (epoch != _authEpoch)
                    return;
                AuthPending = false;
                if (r.NetworkError)
                    SetStatus("Sunucuya bağlanılamadı!", StatusTone.Bad);
                else if (r.Status == 201)
                {
                    EnterMenu(username, UserInfo.DefaultRating, false, r.BodyObject.GetString("token"));
                    SetStatus($"Kayıt başarılı! Hoş geldin {username}!", StatusTone.Good);
                }
                else if (r.Status == 409)
                    SetStatus("Bu kullanıcı adı zaten alınmış!", StatusTone.Bad);
                else if (r.Status == 429)
                    SetStatus("Çok fazla deneme! Biraz sonra tekrar deneyin.", StatusTone.Bad);
                else if (r.Status == 400)
                    SetStatus("Geçersiz kullanıcı adı veya şifre (harf, rakam, _ . - kullanın)", StatusTone.Bad);
                else if (r.Status == 503)
                    SetStatus("Sunucu veritabanına ulaşamıyor.", StatusTone.Bad);
                else
                    SetStatus("Kayıt başarısız!", StatusTone.Bad);
            });
        }

        public void GuestLogin()
        {
            _authEpoch++;
            AuthPending = false;
            // Sunucu "misafir_" ile baslayan adlarla kayit olunmasina izin vermez
            EnterMenu($"Misafir_{UnityEngine.Random.Range(0, 1000000):D6}", UserInfo.DefaultRating, true);
            SetStatus("");
        }

        private void EnterMenu(string username, int elo, bool isGuest, string authToken = null)
        {
            Username = username;
            _authToken = authToken;
            UserElo = elo;
            IsGuest = isGuest;
            SetScreen(AppScreen.Menu);
            InputsCleared?.Invoke();
            Debug.Log($"[App] Oturum acildi: {username} (misafir={isGuest})");
        }

        public void Logout()
        {
            _authEpoch++;
            AuthPending = false;
            Username = "";
            _authToken = null;
            UserElo = UserInfo.DefaultRating;
            IsGuest = false;
            SetScreen(AppScreen.Login);
            SetStatus("");
            InputsCleared?.Invoke();
        }

        private void RefreshUserElo()
        {
            if (string.IsNullOrEmpty(Username) || IsGuest)
                return;
            string user = Username;
            _api.User(user, r =>
            {
                // Yanit gelene kadar oturum degismis olabilir (cikis + misafir girisi)
                if (r.Status == 200 && user == Username && !IsGuest)
                    UserElo = r.BodyObject.GetObject("user").GetInt("rating", UserElo);
            });
        }

        // =====================================================================
        // Menu ve veri ekranlari
        // =====================================================================

        public void OpenAISelect() => SetScreen(AppScreen.AISelect);

        public void OpenLobby()
        {
            SetScreen(AppScreen.Lobby);
            SetStatus("");
            RefreshActiveGames();
        }

        public void RefreshActiveGames()
        {
            _lastLobbyRefresh = Time.unscaledTime;
            if (_lobbyFetching)
                return;
            _lobbyFetching = true;
            _api.ActiveGames(r =>
            {
                _lobbyFetching = false;
                if (r.Ok)
                {
                    var games = ActiveGame.ListFrom(r.ParseBody());
                    // Liste ayniysa surum artmaz: LobbyView satirlari yeniden kurmaz
                    // (kurulum basili tutulan 'Katil'/'Izle' tiklamasini yutar)
                    if (SameGames(ActiveGames, games))
                        return;
                    ActiveGames = games;
                    ActiveGamesVersion++;
                }
            });
        }

        private static bool SameGames(List<ActiveGame> a, List<ActiveGame> b)
        {
            if (a.Count != b.Count)
                return false;
            for (int i = 0; i < a.Count; i++)
            {
                ActiveGame x = a[i], y = b[i];
                if (x.RoomId != y.RoomId || x.P1 != y.P1 || x.P1Elo != y.P1Elo || x.P2 != y.P2
                    || x.P2Elo != y.P2Elo || x.Waiting != y.Waiting || x.MoveCount != y.MoveCount)
                    return false;
            }
            return true;
        }

        public void OpenLeaderboard()
        {
            SetScreen(AppScreen.Leaderboard);
            LeaderboardData = null;
            LeaderboardError = false;
            _api.Leaderboard(r =>
            {
                if (!r.Ok || !(r.ParseBody() is List<object> items))
                {
                    LeaderboardError = true;
                    return;
                }
                var list = new List<UserInfo>();
                foreach (object o in items)
                    list.Add(UserInfo.From(JsonObject.From(o), "?"));
                LeaderboardData = list;
            });
        }

        public void OpenHistory()
        {
            SetScreen(AppScreen.History);
            HistoryData = null;
            HistoryError = false;
            if (IsGuest)
                return;
            _api.History(Username, r =>
            {
                if (!r.Ok)
                {
                    HistoryError = true;
                    return;
                }
                HistoryData = HistoryEntry.ListFrom(r.BodyObject);
            });
        }

        // =====================================================================
        // AI oyunu
        // =====================================================================

        private void InvalidateAISession()
        {
            _ai.CancelMove();
            AIThinking = false;
            Engine = null;
        }

        public void StartAIGame(int depth)
        {
            Debug.Log("[App] AI oyunu basliyor, derinlik=" + depth);
            InvalidateAISession();
            CancelAnimation();
            Game = new GameState();
            Engine = new AIEngine(Board.Player2, depth);
            MyPiece = Board.Player1;
            IsSpectator = false;
            RoomId = null;
            Summary = null;
            SetScreen(AppScreen.PlayingAI);
            SetStatus("Senin sıran!");
        }

        private void RequestAIMove()
        {
            if (Engine == null || Game.CurrentPlayer != Board.Player2)
                return;
            SetStatus("AI düşünüyor...");
            AIThinking = true;
            var engine = Engine;
            _ai.RequestMove(engine, Game.Clone(), AIMoveDelaySeconds, col =>
            {
                AIThinking = false;
                if (Screen != AppScreen.PlayingAI || Engine != engine || col < 0)
                    return;
                if (Game.GameOver || !Game.IsValidLocation(col))
                    return;
                AnimateDrop(col, Game.NextRow(col), Board.Player2, () => FinishAIMove(col));
            });
        }

        private void FinishAIMove(int col)
        {
            if (Screen != AppScreen.PlayingAI || Engine == null)
                return;
            if (!Game.MakeMove(col))
                return;
            if (Game.GameOver)
                HandleGameOver();
            else
                SetStatus("Senin sıran!");
        }

        // =====================================================================
        // Hamle analizi (Lichess tarzi)
        // =====================================================================

        private void StartBackgroundAnalysis(GameState before, int actualCol)
        {
            if (!AnalysisEnabled)
                return;
            int player = before.CurrentPlayer;
            _ai.EnqueueAnalysis(before, AnalysisDepth, best =>
            {
                if (best >= 0)
                    _analysis.Add((player, best == actualCol));
            });
        }

        private void CancelAnalysis()
        {
            _ai.CancelAnalysis();
            _analysis.Clear();
            _summaryCount = -1;
        }

        private AnalysisSummary ComputeSummary()
        {
            if (_analysis.Count == 0)
                return null;
            int mine = 0, mineBest = 0, theirs = 0, theirsBest = 0;
            foreach (var (player, wasBest) in _analysis)
            {
                if (player == MyPiece)
                {
                    mine++;
                    if (wasBest) mineBest++;
                }
                else
                {
                    theirs++;
                    if (wasBest) theirsBest++;
                }
            }
            return new AnalysisSummary
            {
                TotalMoves = _analysis.Count,
                MyAccuracy = mine > 0 ? 100.0 * mineBest / mine : 0,
                OpponentAccuracy = theirs > 0 ? 100.0 * theirsBest / theirs : 0,
            };
        }

        // =====================================================================
        // Online oyun
        // =====================================================================

        public void CreateOnlineGame()
        {
            if (_joinPending)
                return;
            InvalidateAISession();
            RoomId = null;
            SetScreen(AppScreen.Waiting);
            SetStatus("");
            _socket.CreateGame(Username, _authToken);
        }

        public void JoinOnlineGame(string roomId)
        {
            if (_joinPending)
                return;
            _joinPending = true;
            InvalidateAISession();
            ResetOnlineGame();   // onceki macin sonucu/ELO'su yeni odaya tasinmasin
            RoomId = roomId.ToUpperInvariant();
            IsSpectator = false;
            SetStatus("Odaya katılınıyor...");
            _socket.JoinGame(RoomId, Username, _authToken);
        }

        public void SpectateGame(string roomId)
        {
            if (_joinPending)
                return;
            InvalidateAISession();
            RoomId = roomId.ToUpperInvariant();
            IsSpectator = true;
            ResetOnlineGame();
            SetScreen(AppScreen.Spectating);
            SetStatus("Yayına bağlanılıyor...");
            _socket.JoinGame(RoomId, Username, _authToken);
        }

        private void ConnectionFailed()
        {
            _joinPending = false;
            SetStatus("Sunucuya bağlanılamadı!", StatusTone.Bad);
            if (Screen == AppScreen.Waiting || Screen == AppScreen.Spectating)
                SetScreen(AppScreen.Lobby);
        }

        private void OnConnectionLost(string reason)
        {
            // ResetToMenu'nun kendi Disconnect'i (WebGL'de senkron gelir) kopma degildir
            if (reason == "io client disconnect")
                return;
            _joinPending = false;   // yanitsiz kalan katilma istegi 'Katil'i kilitlemesin
            if (Screen == AppScreen.Waiting)
            {
                // Sunucu kurucusu kopan bekleyen odayi hemen siler; geri baglaninca
                // "Oda bulunamadi" gelir ve lobiye donulur (OnServerError)
                SetStatus("Bağlantı koptu! Oda kapanmış olabilir, yeniden bağlanılıyor...", StatusTone.Bad);
                return;
            }
            if ((Screen != AppScreen.PlayingOnline && Screen != AppScreen.Spectating) || Game.GameOver || _sessionDead)
                return;
            _lostAt = Time.unscaledTime;
            _lostShownSeconds = -1;
            SetStatus("Bağlantı koptu! Yeniden bağlanılıyor...", StatusTone.Bad);
        }

        private void ResetOnlineGame()
        {
            CancelAnimation();
            Game = new GameState();
            LastEloChange = null;
            _finalStatus = null;
            Summary = null;
            CancelAnalysis();
            ClearConnectionState();
        }

        private void OnServerEvent(string name, JsonObject data)
        {
            switch (name)
            {
                case SocketEvents.GameCreated: OnGameCreated(data); break;
                case SocketEvents.GameJoined: OnGameJoined(data); break;
                case SocketEvents.GameStart: OnGameStart(data); break;
                case SocketEvents.MoveMade: OnMoveMade(data); break;
                case SocketEvents.GameOver: OnGameOver(data); break;
                case SocketEvents.EloUpdate: OnEloUpdate(data); break;
                case SocketEvents.OpponentDisconnected: OnOpponentDisconnected(data); break;
                case SocketEvents.OpponentReconnected: OnOpponentReconnected(); break;
                case SocketEvents.GameEnded: OnGameEnded(); break;
                case SocketEvents.Error: OnServerError(data); break;
            }
        }

        private void OnGameCreated(JsonObject data)
        {
            RoomId = data.GetString("room_id");
            MyPiece = data.GetInt("player_piece", Board.Player1);
            IsSpectator = false;
            SetScreen(AppScreen.Waiting);
            SetStatus("Oda: " + RoomId);
        }

        private void OnGameJoined(JsonObject data)
        {
            _joinPending = false;
            RoomId = data.GetString("room_id", RoomId);
            MyPiece = data.GetInt("player_piece");
            if (data.GetString("role") == "spectator")
            {
                IsSpectator = true;
                SetScreen(AppScreen.Spectating);
                var p1 = data.GetObject("p1_info");
                var p2 = data.GetObject("p2_info");
                SpectateNames = (p1.GetString("username", "Oyuncu 1"), p1.GetInt("rating", UserInfo.DefaultRating),
                                 p2.GetString("username", "Oyuncu 2"), p2.GetInt("rating", UserInfo.DefaultRating));
                if (data.Has("current_state"))
                    GameSnapshot.Apply(Game, data.GetObject("current_state"));
                bool resumed = Offline || _sessionDead;
                ClearConnectionState();
                if (Game.GameOver)
                    HandleGameOver();   // kopukken biten yayin
                else
                    SetStatus(resumed ? "Yayına geri dönüldü. Canlı izleniyor" : "Canlı izleniyor");
                return;
            }

            IsSpectator = false;
            var opponent = data.GetObject("opponent_info");
            OpponentName = opponent.GetString("username", "Rakip");
            OpponentElo = opponent.GetInt("rating", UserInfo.DefaultRating);
            if (data.GetBool("rejoined"))
            {
                // Kopma sonrasi geri donus: oyunu sunucudaki durumdan surdur. Yerel sayac
                // dolduktan sonra da gelebilir (sunucunun suresi daha gec baslar).
                CancelAnimation();
                ClearConnectionState();
                GameSnapshot.Apply(Game, data.GetObject("current_state"));
                SetScreen(AppScreen.PlayingOnline);
                if (Game.GameOver)
                    ShowRejoinedResult();
                else
                    SetStatus("Oyuna geri dönüldü. " + (Game.CurrentPlayer == MyPiece ? "Senin sıran!" : "Rakibin sırası..."));
            }
        }

        /// <summary>Geri donuldugunde oyun coktan bitmis (sunucu biten odayi bir sure tutar).</summary>
        private void ShowRejoinedResult()
        {
            string msg;
            StatusTone tone;
            if (Game.Winner == MyPiece)
            {
                msg = "Kazandın!";
                tone = StatusTone.Good;
            }
            else if (Game.Winner == 0)
            {
                msg = "Berabere!";
                tone = StatusTone.Neutral;
            }
            else if (Game.Status == GameStatus.Win)
            {
                msg = "Kaybettin.";
                tone = StatusTone.Bad;
            }
            else
            {
                // Hukmen: tahtada dortlu yok, sunucu yalnizca kazanani isaretledi
                msg = "Bağlantın koptuğu için hükmen kaybettin.";
                tone = StatusTone.Bad;
            }
            _finalStatus = msg;
            SetStatus(msg, tone);
            RefreshUserElo();
        }

        private void OnGameStart(JsonObject data)
        {
            Debug.Log("[App] Online oyun basliyor");
            _joinPending = false;
            InvalidateAISession();
            ResetOnlineGame();
            IsSpectator = false;
            SetScreen(AppScreen.PlayingOnline);
            OpponentName = data.GetString("opponent_name");
            if (string.IsNullOrEmpty(OpponentName))
                OpponentName = "Rakip";
            OpponentElo = data.GetInt("opponent_elo", UserInfo.DefaultRating);
            SetStatus("Oyun başladı!" + (Game.CurrentPlayer == MyPiece ? " Senin sıran." : " Rakibin sırası."));
        }

        /// <summary>
        /// Sunucu hamleyi odadaki herkese yayinlar. Hamle gecmisinin uzunluguna gore:
        ///   sunucu &lt; yerel      -> eski olay, yok say
        ///   sunucu == yerel     -> kendi hamlemin yankisi, sadece senkronize et
        ///   sunucu == yerel + 1 -> rakibin yeni hamlesi, animasyonla uygula
        ///   sunucu &gt; yerel + 1 -> arada kacan hamle var, durumu dogrudan al
        /// </summary>
        private void OnMoveMade(JsonObject data)
        {
            int? col = data.GetNullableInt("col");
            if (col == null || (Screen != AppScreen.PlayingOnline && Screen != AppScreen.Spectating))
                return;
            if (IsAnimating())
                FinishAnimation();   // onceki animasyonu tamamla ki yerel durum guncel olsun

            int serverLen = GameSnapshot.HistoryLength(data);
            int localLen = Game.MoveCount;
            if (serverLen < localLen)
                return;
            if (serverLen == localLen)
            {
                GameSnapshot.Apply(Game, data);
                if (Game.GameOver)
                    HandleGameOver();
                else if (!IsSpectator)
                    SetStatus("Rakibin sırası...");
                return;
            }
            if (serverLen > localLen + 1 || Game.GameOver)
            {
                ApplyNetworkMove(data);
                return;
            }
            // Hamleyi yapan = yerel durumda sirasi gelen (sunucunun 'current' alani
            // kazandiran/berabere hamlede degismedigi icin guvenilir degil)
            int mover = Game.CurrentPlayer;
            int c = col.Value;
            if (!Game.IsValidLocation(c))
            {
                ApplyNetworkMove(data);
                return;
            }
            AnimateDrop(c, Game.NextRow(c), mover, () => ApplyNetworkMove(data));
        }

        private void ApplyNetworkMove(JsonObject data)
        {
            int? col = data.GetNullableInt("col");
            if (Screen == AppScreen.PlayingOnline && col != null && Game.MoveCount < GameSnapshot.HistoryLength(data))
                StartBackgroundAnalysis(Game.Clone(), col.Value);
            GameSnapshot.Apply(Game, data);
            if (Game.GameOver)
                HandleGameOver();
            else if (IsSpectator)
                SetStatus("Canlı izleniyor");
            else if (Game.CurrentPlayer == MyPiece)
                SetStatus("Senin sıran!");
            else
                SetStatus("Rakibin sırası...");
        }

        private void OnGameOver(JsonObject data)
        {
            var info = GameOverInfo.From(data);
            int w = info.Winner;
            _opponentDeadline = -1f;
            bool forfeit = info.Reason == "forfeit";
            if (forfeit && !Game.GameOver)
            {
                Game.GameOver = true;
                Game.Winner = w;
            }
            if (!IsSpectator && (MyPiece == Board.Player1 || MyPiece == Board.Player2))
            {
                int change = info.EloChangeFor(MyPiece);
                int? newRating = info.NewRatingFor(MyPiece);
                if (change != 0)
                {
                    LastEloChange = change;
                    if (newRating != null)
                        UserElo = newRating.Value;
                }
            }

            string msg;
            StatusTone tone = StatusTone.Neutral;
            if (IsSpectator)
            {
                msg = w == Board.Player1 ? "Kırmızı kazandı!" : (w == Board.Player2 ? "Sarı kazandı!" : "Berabere!");
                if (forfeit)
                    msg += " (hükmen)";
            }
            else if (w == 0)
                msg = "Berabere!";
            else if (w == MyPiece)
            {
                msg = forfeit ? "Rakip oyunu terk etti - Kazandın!" : "Kazandın!";
                tone = StatusTone.Good;
            }
            else
            {
                msg = forfeit ? "Hükmen kaybettin." : "Kaybettin.";
                tone = StatusTone.Bad;
            }
            if (LastEloChange.HasValue && LastEloChange.Value != 0)
                msg += $"  ELO {(LastEloChange.Value > 0 ? "+" : "")}{LastEloChange.Value} ({UserElo})";
            _finalStatus = msg;
            SetStatus(msg, tone);
            Summary = ComputeSummary();
            RefreshUserElo();
        }

        private void OnEloUpdate(JsonObject data)
        {
            UserElo = data.GetInt("new_elo", UserElo);
            LastEloChange = data.GetInt("change");
        }

        private void OnOpponentDisconnected(JsonObject data)
        {
            if (Screen == AppScreen.PlayingOnline && !Game.GameOver)
            {
                int grace = data.GetInt("grace_seconds", ReconnectGraceDefault);
                _opponentDeadline = Time.unscaledTime + grace;
                _opponentShownSeconds = grace;
                SetStatus($"Rakibin bağlantısı koptu! {grace} sn içinde dönmezse kazanırsın.", StatusTone.Bad);
            }
            else if (IsSpectator)
                SetStatus("Bir oyuncunun bağlantısı koptu...");
        }

        private void OnOpponentReconnected()
        {
            _opponentDeadline = -1f;
            if ((Screen == AppScreen.PlayingOnline || Screen == AppScreen.Spectating) && !Game.GameOver)
            {
                string turn = Game.CurrentPlayer == MyPiece ? "Senin sıran!" : "Rakibin sırası...";
                SetStatus("Rakip geri döndü. " + (IsSpectator ? "" : turn));
            }
        }

        private void OnGameEnded()
        {
            if (Screen == AppScreen.Waiting)
            {
                // Bekleyen oda silindi: olu oda kodunu gostermeye devam etme. LeaveGame
                // InGame'i dusurur; yoksa sonraki yeniden baglanma olu odaya katilmaya calisir.
                _socket.LeaveGame();
                RoomId = null;
                SetScreen(AppScreen.Lobby);
                SetStatus("Oda zaman aşımına uğradı.", StatusTone.Bad);
                RefreshActiveGames();
                return;
            }
            if ((Screen == AppScreen.PlayingOnline || Screen == AppScreen.Spectating) && !Game.GameOver)
            {
                ClearConnectionState();
                _sessionDead = true;
                SetStatus("Oda zaman aşımı nedeniyle kapatıldı. Lobiye dönebilirsin.", StatusTone.Bad);
            }
        }

        private void OnServerError(JsonObject data)
        {
            _joinPending = false;
            string msg = data.GetString("msg", "");
            if (Screen == AppScreen.PlayingOnline && !Game.GameOver
                && (msg == "Oda bulunamadi" || (Offline && msg == "Yeniden baglanma anahtari gecersiz")))
            {
                // Geri donus reddedildi ya da oda sunucuda yok: oyun burada surdurulemez
                ClearConnectionState();
                _sessionDead = true;
                SetStatus("Oyun sunucuda sona ermiş. Lobiye dönebilirsin.", StatusTone.Bad);
                return;
            }
            if (Screen == AppScreen.Spectating && Game.MoveCount > 0 && !Game.GameOver && msg == "Oda bulunamadi")
            {
                ClearConnectionState();
                _sessionDead = true;
                SetStatus("Yayın sunucuda sona ermiş. Lobiye dönebilirsin.", StatusTone.Bad);
                return;
            }
            SetStatus("Hata: " + msg, StatusTone.Bad);
            if ((Screen == AppScreen.Spectating || Screen == AppScreen.Waiting) && Game.MoveCount == 0 && msg == "Oda bulunamadi")
                SetScreen(AppScreen.Lobby);
        }

        // =====================================================================
        // Oyun mantigi
        // =====================================================================

        public void HandleColumnClick(int col)
        {
            // Sira bizde degilse / animasyon / AI dusunurken sessizce yok sayilir
            if (!CanHumanMove() || col < 0 || col >= Board.Cols)
                return;
            if (!Game.IsValidLocation(col))
            {
                SetStatus("Bu sütun dolu!", StatusTone.Bad);
                return;
            }
            AnimateDrop(col, Game.NextRow(col), Game.CurrentPlayer, () => FinishMove(col));
        }

        private void FinishMove(int col)
        {
            if (Screen == AppScreen.PlayingOnline)
            {
                // Dusme animasyonu sirasinda baglanti kopmus olabilir: hayalet tas birakma
                if (!_socket.IsConnected || Offline || _sessionDead)
                {
                    SetStatus("Bağlantı yok, hamle gönderilemedi.", StatusTone.Bad);
                    return;
                }
                var before = Game.Clone();
                if (!Game.MakeMove(col))
                    return;
                StartBackgroundAnalysis(before, col);
                _socket.SendMove(col);
                if (!Game.GameOver)
                    SetStatus("Rakibin sırası...");
                return;   // Oyun sonu mesaji sunucunun game_over olayiyla gelir
            }

            if (Screen != AppScreen.PlayingAI || !Game.MakeMove(col))
                return;
            if (Game.GameOver)
            {
                HandleGameOver();
                return;
            }
            RequestAIMove();
        }

        private void HandleGameOver()
        {
            int w = Game.Winner;
            if (_finalStatus != null && Screen != AppScreen.PlayingAI)
            {
                // Sunucunun sonucu (ELO dahil) animasyon bitmeden geldiyse onu koru
                SetStatus(_finalStatus, Tone);
                return;
            }
            if (Screen == AppScreen.PlayingAI)
                SetStatus(w == Board.Player1 ? "Kazandın!" : (w == Board.Player2 ? "AI kazandı!" : "Berabere!"),
                          w == Board.Player1 ? StatusTone.Good : (w == Board.Player2 ? StatusTone.Bad : StatusTone.Neutral));
            else if (IsSpectator)
                SetStatus(w == Board.Player1 ? "Kırmızı kazandı!" : (w == Board.Player2 ? "Sarı kazandı!" : "Berabere!"));
            else
                SetStatus(w == 0 ? "Berabere!" : (w == MyPiece ? "Kazandın!" : OpponentName + " kazandı!"),
                          w == 0 ? StatusTone.Neutral : (w == MyPiece ? StatusTone.Good : StatusTone.Bad));
        }

        /// <summary>
        /// Menu/Geri/Iptal. Aktif online oyundan cikis onay ister (hukmen yenilgi).
        /// Online ekranlardan (bekleme, oyun, yayin) lobiye, digerlerinden menuye donulur.
        /// </summary>
        public void RequestBack()
        {
            if (Screen == AppScreen.PlayingOnline && !Game.GameOver && !_sessionDead && !LeaveConfirmPending)
            {
                _leaveConfirmUntil = Time.unscaledTime + LeaveConfirmSeconds;
                SetStatus("Oyundan çıkmak hükmen yenilgi sayılır. Onaylamak için tekrar basın.", StatusTone.Bad);
                return;
            }
            bool online = Screen == AppScreen.Waiting || Screen == AppScreen.PlayingOnline || Screen == AppScreen.Spectating;
            LeaveSession(online ? AppScreen.Lobby : AppScreen.Menu);
        }

        /// <summary>Oyun ekranindaki geri butonunun yazisi.</summary>
        public string BackLabel =>
            LeaveConfirmPending ? "Çıkışı Onayla"
            : Screen == AppScreen.PlayingOnline || Screen == AppScreen.Spectating ? "Lobiye Dön"
            : "Menü";

        /// <summary>Biten AI oyununu ayni zorlukla yeniden baslatir.</summary>
        public void PlayAgain()
        {
            if (Screen == AppScreen.PlayingAI && Engine != null && Game.GameOver)
                StartAIGame(Engine.Depth);
        }

        /// <summary>Biten oyunun buyuk basligi (null: oyun suruyor).</summary>
        public (string text, StatusTone tone)? ResultHeadline
        {
            get
            {
                if (!Game.GameOver)
                    return null;
                int w = Game.Winner;
                if (w == 0)
                    return ("BERABERE", StatusTone.Neutral);
                if (IsSpectator)
                    return (w == Board.Player1 ? "KIRMIZI KAZANDI" : "SARI KAZANDI", StatusTone.Neutral);
                if (Screen == AppScreen.PlayingAI)
                    return w == Board.Player1 ? ("KAZANDIN!", StatusTone.Good) : ("AI KAZANDI", StatusTone.Bad);
                return w == MyPiece ? ("KAZANDIN!", StatusTone.Good) : ("KAYBETTİN", StatusTone.Bad);
            }
        }

        public void ResetToMenu() => LeaveSession(AppScreen.Menu);

        private void LeaveSession(AppScreen target)
        {
            InvalidateAISession();
            CancelAnalysis();
            CancelAnimation();
            Summary = null;
            _leaveConfirmUntil = 0f;
            _joinPending = false;
            ClearConnectionState();
            if (Screen == AppScreen.PlayingOnline || Screen == AppScreen.Waiting)
                _socket.LeaveGame();
            _socket.Disconnect();
            _socket.Detach();
            _socket = NewSocket();
            RoomId = null;
            IsSpectator = false;
            Game = new GameState();
            if (string.IsNullOrEmpty(Username))
                SetScreen(AppScreen.Login);
            else if (target == AppScreen.Lobby)
                OpenLobby();
            else
                SetScreen(AppScreen.Menu);
            SetStatus("");
            RefreshUserElo();
        }

        public void Shutdown()
        {
            _ai.CancelAll();
            if (Screen == AppScreen.PlayingOnline || Screen == AppScreen.Waiting)
                _socket.LeaveGame();
            _socket.Disconnect();
        }
    }
}
