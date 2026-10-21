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
        public const int PasswordMinLength = 3;
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
        public AnalysisSummary Summary { get; private set; }

        public string Status { get; private set; } = "";
        public StatusTone Tone { get; private set; }

        /// <summary>Ekran degisti (UI gorunurlugu gunceller).</summary>
        public event Action<AppScreen> ScreenChanged;
        /// <summary>Giris alanlari temizlenmeli.</summary>
        public event Action InputsCleared;

        public string ServerUrl => _api.BaseUrl;

        public AppController(MonoBehaviour host, string serverUrl, ISocketTransport transport)
        {
            _api = new ApiClient(host, serverUrl);
            _transport = transport;
            _socket = NewSocket();
            Debug.Log("[App] Hazir (sunucu: " + serverUrl + ")");
        }

        private GameSocket NewSocket()
        {
            var socket = new GameSocket(_transport, _api.BaseUrl);
            socket.ServerEvent += OnServerEvent;
            socket.ConnectionFailed += _ => ConnectionFailed();
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
            if (Screen == AppScreen.PlayingOnline && Game.GameOver)
                Summary = ComputeSummary();   // analizler oyun bittikten sonra da tamamlanabilir
        }

        public bool LeaveConfirmPending => Time.unscaledTime < _leaveConfirmUntil;

        public bool CanHumanMove()
        {
            if (IsAnimating() || Game.GameOver || IsSpectator)
                return false;
            if (Screen == AppScreen.PlayingAI)
                return Game.CurrentPlayer == Board.Player1 && !AIThinking && Engine != null;
            if (Screen == AppScreen.PlayingOnline)
                return Game.CurrentPlayer == MyPiece;
            return false;
        }

        /// <summary>Oyuncunun hover'da gosterilecek tas rengi.</summary>
        public int HumanPiece => Screen == AppScreen.PlayingAI ? Board.Player1 : MyPiece;

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
            SetStatus("Giriş yapılıyor...", StatusTone.Good);
            _api.Login(username, password, r =>
            {
                AuthPending = false;
                if (r.NetworkError)
                    SetStatus("Sunucuya bağlanılamadı!", StatusTone.Bad);
                else if (r.Status == 200)
                {
                    var user = UserInfo.From(r.BodyObject.GetObject("user"), username);
                    EnterMenu(user.Username, user.Rating, false);
                    SetStatus($"Hoş geldin {Username}!", StatusTone.Good);
                }
                else if (r.Status == 401)
                    SetStatus("Yanlış kullanıcı adı veya şifre!", StatusTone.Bad);
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
                SetStatus($"En az {UsernameMinLength} karakter gerekli!", StatusTone.Bad);
                return;
            }
            AuthPending = true;
            SetStatus("Hesap oluşturuluyor...", StatusTone.Good);
            _api.Signup(username, password, r =>
            {
                AuthPending = false;
                if (r.NetworkError)
                    SetStatus("Sunucuya bağlanılamadı!", StatusTone.Bad);
                else if (r.Status == 201)
                {
                    EnterMenu(username, UserInfo.DefaultRating, false);
                    SetStatus($"Kayıt başarılı! Hoş geldin {username}!", StatusTone.Good);
                }
                else if (r.Status == 409)
                    SetStatus("Bu kullanıcı adı zaten alınmış!", StatusTone.Bad);
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
            // Sunucu "misafir_" ile baslayan adlarla kayit olunmasina izin vermez
            EnterMenu($"Misafir_{UnityEngine.Random.Range(0, 1000000):D6}", UserInfo.DefaultRating, true);
            SetStatus("");
        }

        private void EnterMenu(string username, int elo, bool isGuest)
        {
            Username = username;
            UserElo = elo;
            IsGuest = isGuest;
            SetScreen(AppScreen.Menu);
            InputsCleared?.Invoke();
            Debug.Log($"[App] Oturum acildi: {username} (misafir={isGuest})");
        }

        public void Logout()
        {
            Username = "";
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
            _api.User(Username, r =>
            {
                if (r.Status == 200)
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
                    ActiveGames = ActiveGame.ListFrom(r.ParseBody());
                    ActiveGamesVersion++;
                }
            });
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
            InvalidateAISession();
            RoomId = null;
            SetScreen(AppScreen.Waiting);
            SetStatus("");
            _socket.CreateGame(Username);
        }

        public void JoinOnlineGame(string roomId)
        {
            InvalidateAISession();
            RoomId = roomId.ToUpperInvariant();
            IsSpectator = false;
            SetStatus("Odaya katılınıyor...");
            _socket.JoinGame(RoomId, Username);
        }

        public void SpectateGame(string roomId)
        {
            InvalidateAISession();
            RoomId = roomId.ToUpperInvariant();
            IsSpectator = true;
            ResetOnlineGame();
            SetScreen(AppScreen.Spectating);
            SetStatus("Yayına bağlanılıyor...");
            _socket.JoinGame(RoomId, Username);
        }

        private void ConnectionFailed()
        {
            SetStatus("Sunucuya bağlanılamadı!", StatusTone.Bad);
            if (Screen == AppScreen.Waiting || Screen == AppScreen.Spectating)
                SetScreen(AppScreen.Lobby);
        }

        private void ResetOnlineGame()
        {
            CancelAnimation();
            Game = new GameState();
            LastEloChange = null;
            _finalStatus = null;
            Summary = null;
            CancelAnalysis();
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
                SetStatus("Canlı izleniyor");
                return;
            }

            IsSpectator = false;
            var opponent = data.GetObject("opponent_info");
            OpponentName = opponent.GetString("username", "Rakip");
            OpponentElo = opponent.GetInt("rating", UserInfo.DefaultRating);
            if (data.GetBool("rejoined"))
            {
                // Kopma sonrasi geri donus: oyunu sunucudaki durumdan surdur
                CancelAnimation();
                GameSnapshot.Apply(Game, data.GetObject("current_state"));
                SetScreen(AppScreen.PlayingOnline);
                SetStatus("Oyuna geri dönüldü. " + (Game.CurrentPlayer == MyPiece ? "Senin sıran!" : "Rakibin sırası..."));
            }
        }

        private void OnGameStart(JsonObject data)
        {
            Debug.Log("[App] Online oyun basliyor");
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
                SetStatus($"Rakibin bağlantısı koptu! {grace} sn içinde dönmezse kazanırsın.", StatusTone.Bad);
            }
            else if (IsSpectator)
                SetStatus("Bir oyuncunun bağlantısı koptu...");
        }

        private void OnOpponentReconnected()
        {
            if ((Screen == AppScreen.PlayingOnline || Screen == AppScreen.Spectating) && !Game.GameOver)
            {
                string turn = Game.CurrentPlayer == MyPiece ? "Senin sıran!" : "Rakibin sırası...";
                SetStatus("Rakip geri döndü. " + (IsSpectator ? "" : turn));
            }
        }

        private void OnGameEnded()
        {
            if (!Game.GameOver)
                SetStatus("Oda zaman aşımı nedeniyle kapatıldı.", StatusTone.Bad);
        }

        private void OnServerError(JsonObject data)
        {
            string msg = data.GetString("msg", "");
            SetStatus("Hata: " + msg, StatusTone.Bad);
            if ((Screen == AppScreen.Spectating || Screen == AppScreen.Waiting) && Game.MoveCount == 0 && msg == "Oda bulunamadi")
                SetScreen(AppScreen.Lobby);
        }

        // =====================================================================
        // Oyun mantigi
        // =====================================================================

        public void HandleColumnClick(int col)
        {
            if (!CanHumanMove() || !Game.IsValidLocation(col))
                return;
            AnimateDrop(col, Game.NextRow(col), Game.CurrentPlayer, () => FinishMove(col));
        }

        private void FinishMove(int col)
        {
            if (Screen == AppScreen.PlayingOnline)
            {
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

        /// <summary>Menu/Geri/Iptal. Aktif online oyundan cikis onay ister (hukmen yenilgi).</summary>
        public void RequestBack()
        {
            if (Screen == AppScreen.PlayingOnline && !Game.GameOver && !LeaveConfirmPending)
            {
                _leaveConfirmUntil = Time.unscaledTime + LeaveConfirmSeconds;
                SetStatus("Oyundan çıkmak hükmen yenilgi sayılır. Onaylamak için tekrar basın.", StatusTone.Bad);
                return;
            }
            ResetToMenu();
        }

        public void ResetToMenu()
        {
            InvalidateAISession();
            CancelAnalysis();
            CancelAnimation();
            Summary = null;
            _leaveConfirmUntil = 0f;
            if (Screen == AppScreen.PlayingOnline || Screen == AppScreen.Waiting)
                _socket.LeaveGame();
            _socket.Disconnect();
            _socket.Detach();
            _socket = NewSocket();
            RoomId = null;
            IsSpectator = false;
            Game = new GameState();
            SetScreen(string.IsNullOrEmpty(Username) ? AppScreen.Login : AppScreen.Menu);
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
