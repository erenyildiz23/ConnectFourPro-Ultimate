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

    /// <summary>Biten online oyundan sonra rovans durumu.</summary>
    public enum RematchState
    {
        None,
        OfferedByMe,
        OfferedByOpponent,
        Unavailable,
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
        /// <summary>Yerel oyuncunun kendi sirasinda son bu kadar saniye uyari rengiyle gosterilir.</summary>
        public const int TurnWarningSeconds = 10;
        /// <summary>AI oyununda bos tahtada ilk ipucu (ilk hamleden sonra siradan mesajlar).</summary>
        public const string CoachText = "Dört taşı yatay, dikey ya da çapraz diz. Kırmızı sensin - bir sütuna tıkla.";
        public const string UndoneText = "Hamle geri alındı. Senin sıran!";

        /// <summary>Zorluk secim ekranindaki sade aciklama (dugmelerin derinligi degismez).</summary>
        public static string DifficultyLabel(string name)
        {
            switch (name)
            {
                case "Kolay": return "Kolay - yeni başlayanlar için";
                case "Orta": return "Orta - dengeli rakip";
                case "Zor": return "Zor - en güçlü rakip";
                default: return name;
            }
        }

        /// <summary>Derinlige karsilik gelen seviye adi (Kolay/Orta/Zor); bilinmiyorsa D&lt;derinlik&gt;.</summary>
        public static string DifficultyName(int depth)
        {
            foreach (var (name, d) in AIEngine.Difficulties)
                if (d == depth)
                    return name;
            return "D" + depth;
        }

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
        /// <summary>Zorluk ekranindaki "Ilk hamle" secimi (varsayilan: insan baslar).</summary>
        public bool AIStartsNext { get; private set; }
        /// <summary>Bu AI oyununda ilk hamleyi AI mi yapti.</summary>
        public bool AIStarts { get; private set; }
        /// <summary>Kolay seviyesinin hata zarlari icin oyun tohumu (geri almada degismez).</summary>
        public uint AISeed { get; private set; }
        /// <summary>Her AI oyunu icin yeni 32 bit tohum (testler sabitleyebilir).</summary>
        public Func<uint> NewSeed = RandomSeed;
        private static readonly System.Random SeedRandom = new System.Random();
        private int _aiDepth;
        // Her yeni AI oyununda / geri almada artar: eski animasyon geri cagrilari yeni oyuna sizmaz
        private int _aiGameId;
        // AI oyununda dusen (henuz tahtaya islenmemis) bir tas var
        private bool _aiDropPending;
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
        // Rovans: sunucu destekliyor mu (game_over/game_joined 'detail'/'result' tasir) ve durum
        private bool _rematchSupported;
        public RematchState Rematch { get; private set; }
        // Hamle suresi: sunucunun son bildirdigi kalan saniye ve geldigi yerel zaman (null: sure yok)
        private int? _turnSecondsLeft;
        private float _turnClockAt;
        /// <summary>Sunucunun hamle suresi (sn); 0: kapali ya da eski sunucu.</summary>
        public int MoveTimeSeconds { get; private set; }
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

        /// <summary>
        /// Sirasi gelen oyuncunun kalan tam saniyesi (0'in altina inmez); hamle suresi yoksa,
        /// oyun bittiyse ya da baglanti yoksa null.
        /// </summary>
        public int? TurnSecondsLeft
        {
            get
            {
                if ((Screen != AppScreen.PlayingOnline && Screen != AppScreen.Spectating) || Game.GameOver
                    || _turnSecondsLeft == null || Offline || _sessionDead)
                    return null;
                double left = _turnSecondsLeft.Value - (Time.unscaledTime - _turnClockAt);
                return Math.Max(0, (int)Math.Ceiling(left));
            }
        }

        /// <summary>Yerel oyuncunun kendi sirasinda son TurnWarningSeconds saniye.</summary>
        public bool TurnClockWarning =>
            Screen == AppScreen.PlayingOnline && !IsSpectator && Game.CurrentPlayer == MyPiece
            && TurnSecondsLeft is int s && s <= TurnWarningSeconds;

        /// <summary>Sunucunun yolladigi hamle suresi alanlarini alir (eski sunucuda alan yok: sure yok).</summary>
        private void UpdateTurnClock(JsonObject data)
        {
            _turnSecondsLeft = data.GetNullableInt("turn_seconds_left");
            _turnClockAt = Time.unscaledTime;
            if (data.Has("move_time"))
                MoveTimeSeconds = data.GetInt("move_time");
        }

        private void ClearTurnClock()
        {
            _turnSecondsLeft = null;
            MoveTimeSeconds = 0;
        }

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
                return (Username, UserElo, "AI - " + DifficultyName(_aiDepth), null);
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

        private static uint RandomSeed()
        {
            lock (SeedRandom)
                return ((uint)SeedRandom.Next(1 << 16) << 16) | (uint)SeedRandom.Next(1 << 16);
        }

        /// <summary>Zorluk ekranindaki "Ilk hamle: Sen/AI" dugmesi.</summary>
        public void ToggleAIStartsNext() => AIStartsNext = !AIStartsNext;

        public string AIStartsLabel => AIStartsNext ? "İlk hamle: AI" : "İlk hamle: Sen";

        /// <summary>Zorluk ekranindaki secimle (AIStartsNext) yeni AI oyunu.</summary>
        public void StartAIGame(int depth) => StartAIGame(depth, AIStartsNext);

        /// <summary>
        /// Yeni AI oyunu. Insan hep kirmizi (P1), AI hep sari (P2); yalnizca ilk hamleyi
        /// kimin yaptigi degisir (AI baslarsa oyun P2 sirasiyla kurulur).
        /// </summary>
        public void StartAIGame(int depth, bool aiStarts)
        {
            Debug.Log("[App] AI oyunu basliyor, derinlik=" + depth + ", ilk hamle=" + (aiStarts ? "AI" : "insan"));
            InvalidateAISession();
            CancelAnimation();
            _aiGameId++;
            _aiDropPending = false;
            Game = new GameState(aiStarts ? Board.Player2 : Board.Player1);
            Engine = new AIEngine(Board.Player2, depth);
            _aiDepth = depth;
            AIStarts = aiStarts;
            AISeed = NewSeed();
            MyPiece = Board.Player1;
            IsSpectator = false;
            RoomId = null;
            Summary = null;
            SetScreen(AppScreen.PlayingAI);
            if (aiStarts)
                RequestAIMove();
            else
                SetStatus(CoachText, StatusTone.Good);
        }

        /// <summary>"Tekrar Oyna"/"Yeni Oyun": ayni zorluk, ilk hamleyi yapan taraf degisir.</summary>
        public void NewAIGame()
        {
            if (Screen == AppScreen.PlayingAI && Engine != null && _aiDepth > 0)
                StartAIGame(_aiDepth, !AIStarts);
        }

        /// <summary>Insanin son hamlesinin hamle gecmisindeki sirasi (0 tabanli); yoksa -1.</summary>
        private int LastHumanPly()
        {
            int humanParity = AIStarts ? 1 : 0;   // AI basladiysa insan tek sirali hamlelerde oynar
            for (int i = Game.MoveCount - 1; i >= 0; i--)
                if (i % 2 == humanParity)
                    return i;
            return -1;
        }

        /// <summary>Geri Al: yalnizca AI oyununda; tas duserken, AI dusunurken ya da AI hamlesi beklerken olmaz.</summary>
        public bool CanUndo =>
            Screen == AppScreen.PlayingAI && !IsSpectator && Engine != null && _aiDepth > 0
            && !IsAnimating() && !AIThinking && !_aiDropPending && LastHumanPly() >= 0;

        /// <summary>Insanin son hamlesini ve (varsa) AI'nin cevabini geri alir; sira yine insanda olur.</summary>
        public void UndoAIMove()
        {
            if (!CanUndo)
                return;
            var moves = new List<int>(Game.MoveHistory).GetRange(0, LastHumanPly());
            int depth = _aiDepth;
            InvalidateAISession();
            _aiGameId++;
            Game = GameState.FromMoves(moves, AIStarts ? Board.Player2 : Board.Player1);
            Engine = new AIEngine(Board.Player2, depth);   // tohum (AISeed) ayni kalir: hata yeniden zarlanmaz
            SetStatus(UndoneText);
        }

        private void RequestAIMove()
        {
            if (Engine == null || Game.CurrentPlayer != Board.Player2)
                return;
            SetStatus("AI düşünüyor...");
            AIThinking = true;
            var engine = Engine;
            var snapshot = Game.Clone();
            uint seed = AISeed;
            int gameId = _aiGameId;
            _ai.RequestMove(engine, snapshot, AIMoveDelaySeconds, col =>
            {
                AIThinking = false;
                if (Screen != AppScreen.PlayingAI || Engine != engine || gameId != _aiGameId || col < 0)
                    return;
                // Kolay seviyesi: arama sonrasi kasitli hata (arama aynen calisti)
                col = SlipPolicy.Apply(snapshot, engine.Depth, seed, col);
                if (Game.GameOver || !Game.IsValidLocation(col))
                    return;
                _aiDropPending = true;
                AnimateDrop(col, Game.NextRow(col), Board.Player2, () =>
                {
                    if (gameId != _aiGameId)
                        return;   // bu arada yeni oyun / geri alma
                    _aiDropPending = false;
                    FinishAIMove(col);
                });
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
            // Oynanan hamle esit en iyi hamlelerden biriyse (ya da kitap hamlesiyse) isabetli
            _ai.EnqueueAnalysis(before, AnalysisDepth, best => _analysis.Add((player, best.Contains(actualCol))));
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
            if (Screen == AppScreen.PlayingOnline && !IsSpectator && ResultKnown && _rematchSupported
                && Rematch != RematchState.Unavailable)
            {
                // Biten oyunda koltuga geri katilinmaz (sunucu ayrilan oyuncunun rovansini iptal eder)
                Rematch = RematchState.Unavailable;
                SetStatus("Bağlantı koptu, rövanş yapılamaz.", StatusTone.Bad);
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
            ClearTurnClock();
            _rematchSupported = false;
            Rematch = RematchState.None;
        }

        /// <summary>Sunucunun sonucu geldi (son tasin animasyonu henuz bitmemis olabilir).</summary>
        private bool ResultKnown => Game.GameOver || _finalStatus != null;

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
                case SocketEvents.RematchOffered: OnRematchOffered(data); break;
                case SocketEvents.RematchUnavailable: OnRematchUnavailable(data); break;
                case SocketEvents.RematchStarted: OnRematchStarted(data); break;
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
                UpdateTurnClock(data);
                bool resumed = Offline || _sessionDead;
                ClearConnectionState();
                if (Game.GameOver && data.Has("result"))
                    ApplyResult(GameOverInfo.From(data.GetObject("result")));   // sunucunun kesin sonucu
                else if (Game.GameOver)
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
                UpdateTurnClock(data);
                SetScreen(AppScreen.PlayingOnline);
                if (Game.GameOver && data.Has("result"))
                    ApplyResult(GameOverInfo.From(data.GetObject("result")));   // kesin sonuc ve ELO
                else if (Game.GameOver)
                    ShowRejoinedResult();
                else
                    SetStatus("Oyuna geri dönüldü. " + (Game.CurrentPlayer == MyPiece ? "Senin sıran!" : "Rakibin sırası..."));
            }
        }

        /// <summary>Geri donuldugunde oyun coktan bitmis; eski sunucu sonucu yollamaz, tahtadan cikarilir.</summary>
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
            bool rematch = data.GetBool("rematch");
            // Rovansta koltuklar yer degistirir; ilk oyunda tas game_created/game_joined'dan gelir
            MyPiece = data.GetInt("player_piece", MyPiece);
            RoomId = data.GetString("room_id", RoomId);
            UpdateTurnClock(data);
            SetScreen(AppScreen.PlayingOnline);
            OpponentName = data.GetString("opponent_name");
            if (string.IsNullOrEmpty(OpponentName))
                OpponentName = "Rakip";
            OpponentElo = data.GetInt("opponent_elo", UserInfo.DefaultRating);
            if (rematch && !IsGuest)
            {
                var mine = data.GetObject(MyPiece == Board.Player1 ? "p1_info" : "p2_info");
                if (mine.Has("rating"))
                    UserElo = mine.GetInt("rating", UserElo);
            }
            SetStatus((rematch ? "Rövanş başladı!" : "Oyun başladı!")
                      + (Game.CurrentPlayer == MyPiece ? " Senin sıran." : " Rakibin sırası."));
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
            UpdateTurnClock(data);
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

        private void OnGameOver(JsonObject data) => ApplyResult(GameOverInfo.From(data));

        /// <summary>Sunucunun sonucu: game_over ya da yokken biten oyuna donuldugunde game_joined.result.</summary>
        private void ApplyResult(GameOverInfo info)
        {
            int w = info.Winner;
            _opponentDeadline = -1f;
            _turnSecondsLeft = null;
            if (info.HasDetailField)
                _rematchSupported = true;
            // Rakip ayrildi / koptu: rovans istenemez
            if (!IsSpectator && w == MyPiece && (info.Detail == "leave" || info.Detail == "disconnect"))
                Rematch = RematchState.Unavailable;
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

            var (msg, tone) = ResultText(w, forfeit, info.Detail);
            if (LastEloChange.HasValue && LastEloChange.Value != 0)
                msg += $"  ELO {(LastEloChange.Value > 0 ? "+" : "")}{LastEloChange.Value} ({UserElo})";
            _finalStatus = msg;
            SetStatus(msg, tone);
            Summary = ComputeSummary();
            RefreshUserElo();
        }

        /// <summary>Sonuc metni; detail yoksa (eski sunucu) eski metinler.</summary>
        private (string msg, StatusTone tone) ResultText(int w, bool forfeit, string detail)
        {
            if (IsSpectator)
            {
                string msg = w == Board.Player1 ? "Kırmızı kazandı!" : (w == Board.Player2 ? "Sarı kazandı!" : "Berabere!");
                if (forfeit)
                    msg += detail == "timeout" ? " (süre doldu)"
                         : detail == "disconnect" ? " (bağlantı koptu)"
                         : detail == "leave" ? " (oyun terk edildi)"
                         : " (hükmen)";
                return (msg, StatusTone.Neutral);
            }
            if (w == 0)
                return ("Berabere!", StatusTone.Neutral);
            if (w == MyPiece)
            {
                string msg = !forfeit ? "Kazandın!"
                           : detail == "timeout" ? "Rakibin süresi doldu, kazandın!"
                           : detail == "disconnect" ? "Rakibin bağlantısı koptu, hükmen kazandın!"
                           : "Rakip oyunu terk etti - Kazandın!";
                return (msg, StatusTone.Good);
            }
            string lost = !forfeit ? "Kaybettin."
                        : detail == "timeout" ? "Süre doldu, hükmen kaybettin."
                        : detail == "disconnect" ? "Bağlantın koptuğu için hükmen kaybettin."
                        : detail == "leave" ? "Oyunu terk ettin, hükmen kaybettin."
                        : "Hükmen kaybettin.";
            return (lost, StatusTone.Bad);
        }

        // =====================================================================
        // Rovans
        // =====================================================================

        /// <summary>Biten online oyunda (oyuncu, sunucu destekliyor, rakip hala odada) rovans istenebilir.</summary>
        public bool CanRequestRematch =>
            Screen == AppScreen.PlayingOnline && !IsSpectator && Game.GameOver && _rematchSupported
            && RoomId != null && _socket.IsConnected
            && (Rematch == RematchState.None || Rematch == RematchState.OfferedByOpponent);

        /// <summary>Rovans butonunun yazisi.</summary>
        public string RematchLabel => Rematch == RematchState.OfferedByOpponent ? "Rövanşı Kabul Et" : "Rövanş";

        public void RequestRematch()
        {
            if (!CanRequestRematch || !_socket.RequestRematch())
                return;
            if (Rematch == RematchState.OfferedByOpponent)
                SetStatus("Rövanş kabul edildi, oyun başlıyor...", StatusTone.Good);
            else
                SetStatus("Rövanş istendi, rakip bekleniyor...");
            Rematch = RematchState.OfferedByMe;
        }

        private bool IsRematchForMe(JsonObject data) =>
            Screen == AppScreen.PlayingOnline && !IsSpectator && ResultKnown && _rematchSupported
            && data.GetString("room_id", RoomId) == RoomId;

        private void OnRematchOffered(JsonObject data)
        {
            if (!IsRematchForMe(data) || Rematch == RematchState.Unavailable)
                return;
            int from = data.GetInt("from_piece");
            if (from == MyPiece)
                return;   // kendi istegimizin yankisi
            if (Rematch == RematchState.OfferedByMe)
                return;   // iki istek de sunucuda: game_start gelecek
            Rematch = RematchState.OfferedByOpponent;
            SetStatus("Rakip rövanş istiyor!", StatusTone.Good);
        }

        private void OnRematchUnavailable(JsonObject data)
        {
            if (!IsRematchForMe(data))
                return;
            Rematch = RematchState.Unavailable;
            SetStatus("Rakip ayrıldı, rövanş yapılamaz.", StatusTone.Bad);
        }

        /// <summary>Seyirci: ayni odada yeni oyun (oyuncular game_start alir).</summary>
        private void OnRematchStarted(JsonObject data)
        {
            if (Screen != AppScreen.Spectating || !IsSpectator || data.GetString("room_id", RoomId) != RoomId)
                return;
            ResetOnlineGame();
            var p1 = data.GetObject("p1_info");
            var p2 = data.GetObject("p2_info");
            SpectateNames = (p1.GetString("username", "Oyuncu 1"), p1.GetInt("rating", UserInfo.DefaultRating),
                             p2.GetString("username", "Oyuncu 2"), p2.GetInt("rating", UserInfo.DefaultRating));
            if (data.Has("current_state"))
                GameSnapshot.Apply(Game, data.GetObject("current_state"));
            UpdateTurnClock(data);
            SetStatus("Rövanş başladı! Canlı izleniyor");
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
                // Sunucu, sira bendeyken kopan rakibi beklerken saatimi durdurur (_clock_paused)
                if (Game.CurrentPlayer == MyPiece)
                    _turnSecondsLeft = null;
                SetStatus($"Rakibin bağlantısı koptu! {grace} sn içinde dönmezse kazanırsın.", StatusTone.Bad);
            }
            else if (IsSpectator)
            {
                _turnSecondsLeft = null;   // kimin koptugu bilinmez: saat gosterilmez
                SetStatus("Bir oyuncunun bağlantısı koptu...");
            }
        }

        private void OnOpponentReconnected()
        {
            _opponentDeadline = -1f;
            // Sunucu, rakip donunce sirasi gelen oyuncunun suresini bastan baslatir
            if (Screen == AppScreen.PlayingOnline && !IsSpectator && !Game.GameOver
                && Game.CurrentPlayer == MyPiece && MoveTimeSeconds > 0)
            {
                _turnSecondsLeft = MoveTimeSeconds;
                _turnClockAt = Time.unscaledTime;
            }
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
            else if (Screen == AppScreen.PlayingOnline && !IsSpectator && _rematchSupported
                     && Rematch != RematchState.Unavailable)
            {
                Rematch = RematchState.Unavailable;   // biten oda silindi
                SetStatus("Oda kapandı, rövanş yapılamaz.", StatusTone.Bad);
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
            if (Screen == AppScreen.PlayingOnline && Game.GameOver && Rematch == RematchState.OfferedByMe)
            {
                // Rovans istegi reddedildi (oda silindi ya da koltuk artik bizim degil)
                Rematch = RematchState.Unavailable;
                SetStatus("Rövanş yapılamaz.", StatusTone.Bad);
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
            if (Screen == AppScreen.PlayingAI)
            {
                int gameId = _aiGameId;
                _aiDropPending = true;
                AnimateDrop(col, Game.NextRow(col), Game.CurrentPlayer, () =>
                {
                    if (gameId != _aiGameId)
                        return;   // tas duserken yeni oyun basladi
                    _aiDropPending = false;
                    FinishMove(col);
                });
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
                // Sunucunun sonucu (ELO dahil) animasyon bitmeden geldiyse onu koru; bu arada
                // gelen rovans mesaji ezilmez (sonuc baslikta gorunur)
                if (Rematch == RematchState.None)
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

        /// <summary>"Tekrar Oyna" dugmesi: NewAIGame (ayni zorluk, ilk hamle sirasi degisir).</summary>
        public void PlayAgain() => NewAIGame();

        /// <summary>AI oyunu dugmesinin yazisi: oyun surerken "Yeni Oyun", bitince "Tekrar Oyna".</summary>
        public string NewGameLabel => Game.GameOver ? "Tekrar Oyna" : "Yeni Oyun";

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
            _aiGameId++;
            _aiDropPending = false;
            _aiDepth = 0;
            CancelAnalysis();
            CancelAnimation();
            Summary = null;
            _leaveConfirmUntil = 0f;
            _joinPending = false;
            ClearConnectionState();
            ClearTurnClock();
            _rematchSupported = false;
            Rematch = RematchState.None;
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
