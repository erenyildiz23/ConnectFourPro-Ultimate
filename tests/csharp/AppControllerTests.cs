// Uygulama durum makinesi (Game/AppController.cs): gercek sinif, sahte REST istemcisi
// (stubs/FakeApiClient.cs) ve sahte tasiyici (FakeTransport) ile.
using System.Collections.Generic;
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using ConnectFourPro.Net;
using NUnit.Framework;
using UnityEngine;

namespace ConnectFourPro.Tests
{
    public class AppControllerTests
    {
        private const string Url = "http://test";
        private const string LoginOk = "{\"user\":{\"username\":\"Ali\",\"rating\":1337},\"token\":\"tok-1\"}";
        private const string Created = "{\"room_id\":\"AB12C\",\"player_piece\":1,\"rejoin_token\":\"seat-1\"}";
        private const string JoinedAsP2 =
            "{\"room_id\":\"AB12C\",\"player_piece\":2,\"role\":\"player\"," +
            "\"opponent_info\":{\"username\":\"ali\",\"rating\":1300},\"rejoin_token\":\"seat-2\"}";
        private const string StartVsVeli = "{\"msg\":\"Oyun Basladi!\",\"opponent_name\":\"veli\",\"opponent_elo\":1250}";
        private const string StartVsAli = "{\"msg\":\"Oyun Basladi!\",\"opponent_name\":\"ali\",\"opponent_elo\":1300}";

        private FakeTransport _transport;
        private ApiClient _api;
        private AppController _app;
        private List<AppScreen> _screens;

        [SetUp]
        public void SetUp()
        {
            UnityStubs.Reset();
            _transport = new FakeTransport();
            _api = new ApiClient(null, Url);
            _app = new AppController(_api, _transport);
            _app.AnalysisEnabled = false;   // derinlik 8 analizleri bu testlerin konusu degil
            _screens = new List<AppScreen>();
            _app.ScreenChanged += _screens.Add;
        }

        private ApiClient.Call LastCall => _api.Calls[_api.Calls.Count - 1];

        private void LoginAsAli()
        {
            _app.Login("ali", "secret12");
            LastCall.Respond(200, LoginOk);
        }

        /// <summary>Oda kurar, rakip katilir: P1 (kirmizi) olarak oyunda.</summary>
        private void StartOnlineGameAsP1()
        {
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            _transport.Receive("game_start", StartVsVeli);
        }

        /// <summary>Odaya katilir: P2 (sari) olarak oyunda.</summary>
        private void StartOnlineGameAsP2()
        {
            _app.JoinOnlineGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", JoinedAsP2);
            _transport.Receive("game_start", StartVsAli);
        }

        // ---------------------------------------------------------------------
        // Kimlik dogrulama
        // ---------------------------------------------------------------------

        [Test]
        public void StartsOnLoginScreen()
        {
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Login));
            Assert.That(_app.ServerUrl, Is.EqualTo(Url));
            Assert.That(_api.Calls, Is.Empty);
            Assert.That(_transport.ConnectUrls, Is.Empty);
        }

        [Test]
        public void HostConstructorBuildsItsOwnApiClientAndLogsReady()
        {
            // tests/e2e/webgl.spec.mjs bu satiri bekler
            var app = new AppController(new MonoBehaviour(), Url, new FakeTransport());
            Assert.That(app.Screen, Is.EqualTo(AppScreen.Login));
            Assert.That(app.ServerUrl, Is.EqualTo(Url));
            Assert.That(Debug.Logs, Has.Some.EqualTo("[App] Hazir (sunucu: " + Url + ")"));
        }

        [Test]
        public void LoginSendsTrimmedCredentialsAndWaits()
        {
            _app.Login("  ali ", "secret12");
            Assert.That(_api.Calls.Count, Is.EqualTo(1));
            Assert.That(LastCall.Method, Is.EqualTo("Login"));
            Assert.That(LastCall.Username, Is.EqualTo("ali"));
            Assert.That(LastCall.Password, Is.EqualTo("secret12"));
            Assert.That(_app.AuthPending, Is.True);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Login));

            _app.Login("ali", "secret12");
            Assert.That(_api.Calls.Count, Is.EqualTo(1), "yanit beklenirken ikinci istek gitmemeli");
        }

        [Test]
        public void LoginSuccessStoresIdentityAndEntersMenu()
        {
            bool cleared = false;
            _app.InputsCleared += () => cleared = true;
            _app.Login("ali", "secret12");
            LastCall.Respond(200, LoginOk);

            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_screens, Is.EqualTo(new[] { AppScreen.Menu }));
            Assert.That(_app.Username, Is.EqualTo("Ali"), "sunucunun dondurdugu yazim kullanilir");
            Assert.That(_app.UserElo, Is.EqualTo(1337));
            Assert.That(_app.IsGuest, Is.False);
            Assert.That(_app.AuthPending, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Hoş geldin Ali!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Good));
            Assert.That(cleared, Is.True);
        }

        [Test]
        public void LoginTokenIsSentWhenCreatingGame()
        {
            LoginAsAli();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            var data = _transport.EmittedOf("create_game")[0];
            Assert.That(data.GetString("user_id"), Is.EqualTo("Ali"));
            Assert.That(data.GetString("token"), Is.EqualTo("tok-1"));
        }

        [TestCase(401, "Yanlış kullanıcı adı veya şifre!")]
        [TestCase(429, "Çok fazla deneme! Biraz sonra tekrar deneyin.")]
        [TestCase(503, "Sunucu veritabanına ulaşamıyor. Misafir olarak devam edebilirsiniz.")]
        [TestCase(500, "Giriş başarısız!")]
        [TestCase(0, "Sunucuya bağlanılamadı!")]
        public void LoginFailureShowsStatusAndStaysOnLogin(int status, string expected)
        {
            _app.Login("ali", "secret12");
            LastCall.Respond(status, status == 0 ? null : "{\"error\":\"x\"}");

            Assert.That(_app.Status, Is.EqualTo(expected));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Login));
            Assert.That(_app.Username, Is.Empty);
            Assert.That(_app.AuthPending, Is.False);
        }

        [TestCase("", "secret12")]
        [TestCase("   ", "secret12")]
        [TestCase("ali", "")]
        [TestCase(null, null)]
        public void LoginWithoutCredentialsSendsNothing(string username, string password)
        {
            _app.Login(username, password);
            Assert.That(_api.Calls, Is.Empty);
            Assert.That(_app.Status, Is.EqualTo("Kullanıcı adı ve şifre gerekli!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        [Test]
        public void RegisterSuccessEntersMenuWithToken()
        {
            _app.Register("yeni", "secret12");
            Assert.That(LastCall.Method, Is.EqualTo("Signup"));
            LastCall.Respond(201, "{\"token\":\"tok-2\"}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.Username, Is.EqualTo("yeni"));
            Assert.That(_app.UserElo, Is.EqualTo(UserInfo.DefaultRating));

            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("create_game")[0].GetString("token"), Is.EqualTo("tok-2"));
        }

        [TestCase("ab", "secret12")]
        [TestCase("ali", "short")]
        public void RegisterRejectsShortInputLocally(string username, string password)
        {
            _app.Register(username, password);
            Assert.That(_api.Calls, Is.Empty);
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Login));
        }

        [Test]
        public void RegisterConflictShowsTakenName()
        {
            _app.Register("ali", "secret12");
            LastCall.Respond(409, "{}");
            Assert.That(_app.Status, Is.EqualTo("Bu kullanıcı adı zaten alınmış!"));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Login));
        }

        [Test]
        public void GuestLoginEntersMenuWithoutServer()
        {
            _app.GuestLogin();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.Username, Does.Match("^Misafir_[0-9]{6}$"));
            Assert.That(_app.IsGuest, Is.True);
            Assert.That(_app.UserElo, Is.EqualTo(UserInfo.DefaultRating));
            Assert.That(_app.Status, Is.Empty);
            Assert.That(_api.Calls, Is.Empty);
        }

        [Test]
        public void GuestSendsNoToken()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            var data = _transport.EmittedOf("create_game")[0];
            Assert.That(data.GetString("user_id"), Is.EqualTo(_app.Username));
            Assert.That(data.Has("token"), Is.False);
        }

        [Test]
        public void LogoutClearsIdentityAndSessionToken()
        {
            LoginAsAli();
            _app.Logout();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Login));
            Assert.That(_app.Username, Is.Empty);
            Assert.That(_app.UserElo, Is.EqualTo(UserInfo.DefaultRating));
            Assert.That(_app.Status, Is.Empty);

            // Token gercekten silindi mi: sonraki oda isteginde gitmemeli
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("create_game")[0].Has("token"), Is.False);
        }

        [Test]
        public void GuestAfterLogoutDoesNotInheritToken()
        {
            LoginAsAli();
            _app.Logout();
            _app.GuestLogin();
            _app.JoinOnlineGame("AB12C");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game")[0].Has("token"), Is.False);
        }

        // ---------------------------------------------------------------------
        // Veri ekranlari
        // ---------------------------------------------------------------------

        [Test]
        public void LobbyLoadsActiveGamesAndRefreshesPeriodically()
        {
            _app.GuestLogin();
            _app.OpenLobby();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby));
            Assert.That(LastCall.Method, Is.EqualTo("ActiveGames"));
            LastCall.Respond(200, "[{\"room_id\":\"AB12C\",\"p1\":\"ali\",\"p1_elo\":1250,\"p2\":\"Bekleniyor...\",\"p2_elo\":0,\"status\":\"WAITING\",\"move_count\":0}]");
            Assert.That(_app.ActiveGames.Count, Is.EqualTo(1));
            Assert.That(_app.ActiveGames[0].RoomId, Is.EqualTo("AB12C"));
            Assert.That(_app.ActiveGamesVersion, Is.EqualTo(1));

            Time.unscaledTime = AppController.LobbyRefreshSeconds - 0.5f;
            _app.Tick();
            Assert.That(_api.Calls.Count, Is.EqualTo(1), "sure dolmadan yenilenmemeli");
            Time.unscaledTime = AppController.LobbyRefreshSeconds + 0.5f;
            _app.Tick();
            Assert.That(_api.Calls.Count, Is.EqualTo(2));

            // Onceki istek yanitlanmadan yenisi gonderilmez; hata listeyi silmez
            Time.unscaledTime += AppController.LobbyRefreshSeconds + 0.5f;
            _app.Tick();
            Assert.That(_api.Calls.Count, Is.EqualTo(2));
            LastCall.Respond(0);
            Assert.That(_app.ActiveGames.Count, Is.EqualTo(1));
            Assert.That(_app.ActiveGamesVersion, Is.EqualTo(1));
        }

        [Test]
        public void LeaderboardLoadsOrFlagsError()
        {
            _app.OpenLeaderboard();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Leaderboard));
            LastCall.Respond(200, "[{\"username\":\"ali\",\"rating\":1400,\"wins\":3,\"losses\":1}]");
            Assert.That(_app.LeaderboardError, Is.False);
            Assert.That(_app.LeaderboardData.Count, Is.EqualTo(1));
            Assert.That(_app.LeaderboardData[0].Rating, Is.EqualTo(1400));

            _app.OpenLeaderboard();
            Assert.That(_app.LeaderboardData, Is.Null);
            LastCall.Respond(503, "{}");
            Assert.That(_app.LeaderboardError, Is.True);
        }

        [Test]
        public void HistoryIsRequestedForRegisteredUserOnly()
        {
            _app.GuestLogin();
            _app.OpenHistory();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.History));
            Assert.That(_api.Calls, Is.Empty);

            _app.Logout();
            LoginAsAli();
            _app.OpenHistory();
            Assert.That(LastCall.Method, Is.EqualTo("History"));
            Assert.That(LastCall.Username, Is.EqualTo("Ali"));
            LastCall.Respond(200, "{\"games\":[{\"start_time\":\"2026-10-21T13:20:59\",\"moves\":\"[3, 3, 2]\",\"player1\":\"Ali\",\"player2\":\"veli\",\"winner\":\"Ali\",\"result\":\"win\",\"end_reason\":\"normal\"}]}");
            Assert.That(_app.HistoryData.Count, Is.EqualTo(1));
            Assert.That(_app.HistoryData[0].MoveCount, Is.EqualTo(3));
        }

        // ---------------------------------------------------------------------
        // Online oyun: oda kurma / katilma
        // ---------------------------------------------------------------------

        [Test]
        public void CreateOnlineGameWaitsForOpponentThenPlays()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Waiting));
            Assert.That(_app.RoomId, Is.Null);
            Assert.That(_transport.ConnectUrls, Is.EqualTo(new[] { Url }));

            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("create_game").Count, Is.EqualTo(1));

            _transport.Receive("game_created", Created);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Waiting));
            Assert.That(_app.RoomId, Is.EqualTo("AB12C"));
            Assert.That(_app.MyPiece, Is.EqualTo(Board.Player1));
            Assert.That(_app.Status, Is.EqualTo("Oda: AB12C"));
            Assert.That(_app.CanHumanMove(), Is.False);

            _transport.Receive("game_start", StartVsVeli);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.OpponentName, Is.EqualTo("veli"));
            Assert.That(_app.OpponentElo, Is.EqualTo(1250));
            Assert.That(_app.Status, Is.EqualTo("Oyun başladı! Senin sıran."));
            Assert.That(_app.CanHumanMove(), Is.True);
            Assert.That(_app.PlayerLabels(), Is.EqualTo((_app.Username, (int?)1200, "veli", (int?)1250)));
        }

        [Test]
        public void JoinOnlineGamePlaysAsSecondPlayer()
        {
            _app.GuestLogin();
            _app.JoinOnlineGame("ab12c");
            Assert.That(_app.RoomId, Is.EqualTo("AB12C"));
            Assert.That(_app.Status, Is.EqualTo("Odaya katılınıyor..."));
            _transport.RaiseConnected();
            var join = _transport.EmittedOf("join_game")[0];
            Assert.That(join.GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(join.GetString("user_id"), Is.EqualTo(_app.Username));

            _transport.Receive("game_joined", JoinedAsP2);
            Assert.That(_app.MyPiece, Is.EqualTo(Board.Player2));
            Assert.That(_app.OpponentName, Is.EqualTo("ali"));
            Assert.That(_app.OpponentElo, Is.EqualTo(1300));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu), "oyun game_start ile baslar");

            _transport.Receive("game_start", StartVsAli);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.IsSpectator, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Oyun başladı! Rakibin sırası."));
            Assert.That(_app.CanHumanMove(), Is.False);
            Assert.That(_app.HumanPiece, Is.EqualTo(Board.Player2));
        }

        [Test]
        public void ConnectionFailureReturnsFromWaitingToLobby()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnectError("timeout");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby));
            Assert.That(_app.Status, Is.EqualTo("Sunucuya bağlanılamadı!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        [Test]
        public void ServerErrorIsShownAndMissingRoomReturnsToLobby()
        {
            _app.GuestLogin();
            _app.SpectateGame("zzzzz");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Spectating));
            _transport.RaiseConnected();
            _transport.Receive("error", "{\"msg\":\"Oda bulunamadi\"}");
            Assert.That(_app.Status, Is.EqualTo("Hata: Oda bulunamadi"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby));
        }

        [Test]
        public void SpectatorSeesCurrentPositionAndCannotMove()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            string state = ServerMessages.Snapshot(GameState.FromMoves(new[] { 3, 4 }));
            _transport.Receive("game_joined",
                "{\"room_id\":\"AB12C\",\"player_piece\":0,\"role\":\"spectator\",\"current_state\":" + state + "," +
                "\"p1_info\":{\"username\":\"ali\",\"rating\":1300},\"p2_info\":{\"username\":\"veli\",\"rating\":1250}}");

            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Spectating));
            Assert.That(_app.IsSpectator, Is.True);
            Assert.That(_app.SpectateNames, Is.EqualTo(("ali", 1300, "veli", 1250)));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(2));
            Assert.That(_app.Game.GetCell(4, 0), Is.EqualTo(Board.Player2));
            Assert.That(_app.Status, Is.EqualTo("Canlı izleniyor"));
            Assert.That(_app.CanHumanMove(), Is.False);

            _transport.Receive("move_made", ServerMessages.MoveMade(3, 4, 3));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(3));
            Assert.That(_app.Status, Is.EqualTo("Canlı izleniyor"));
        }

        [Test]
        public void RejoinRestoresGameFromServerState()
        {
            _app.GuestLogin();
            _app.JoinOnlineGame("AB12C");
            _transport.RaiseConnected();
            string state = ServerMessages.Snapshot(GameState.FromMoves(new[] { 3, 4, 3 }));
            _transport.Receive("game_joined",
                "{\"room_id\":\"AB12C\",\"player_piece\":2,\"role\":\"player\",\"rejoined\":true,\"current_state\":" + state + "," +
                "\"opponent_info\":{\"username\":\"ali\",\"rating\":1300},\"rejoin_token\":\"seat-2\"}");

            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3, 4, 3 }));
            Assert.That(_app.Status, Is.EqualTo("Oyuna geri dönüldü. Senin sıran!"));
            Assert.That(_app.CanHumanMove(), Is.True);
        }

        // ---------------------------------------------------------------------
        // Online oyun: hamleler
        // ---------------------------------------------------------------------

        [Test]
        public void OpponentMoveUpdatesBoardAndGivesTurn()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            var drops = new List<(int col, int row, int piece)>();
            _app.AnimateDrop = (col, row, piece, done) =>
            {
                drops.Add((col, row, piece));
                done();
            };

            _transport.Receive("move_made", ServerMessages.MoveMade(3));

            Assert.That(drops, Is.EqualTo(new[] { (3, 0, Board.Player1) }));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(1));
            Assert.That(_app.Game.GetCell(3, 0), Is.EqualTo(Board.Player1));
            Assert.That(_app.Game.CurrentPlayer, Is.EqualTo(Board.Player2));
            Assert.That(_app.Status, Is.EqualTo("Senin sıran!"));
            Assert.That(_app.CanHumanMove(), Is.True);
        }

        [Test]
        public void OpponentMoveIsAppliedOnlyWhenAnimationFinishes()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            System.Action finish = null;
            _app.AnimateDrop = (col, row, piece, done) => finish = done;

            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            finish();
            Assert.That(_app.Game.MoveCount, Is.EqualTo(1));
        }

        [Test]
        public void OwnMoveIsSentAndEchoDoesNotDuplicateIt()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();

            _app.HandleColumnClick(2);
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 2 }));
            var move = _transport.EmittedOf("make_move")[0];
            Assert.That(move.GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(move.GetInt("col", -1), Is.EqualTo(2));
            Assert.That(move.GetInt("player_piece"), Is.EqualTo(Board.Player1));
            Assert.That(_app.Status, Is.EqualTo("Rakibin sırası..."));
            Assert.That(_app.CanHumanMove(), Is.False);

            _app.HandleColumnClick(4);   // sira rakipte: yok sayilir
            Assert.That(_transport.EmittedOf("make_move").Count, Is.EqualTo(1));

            _transport.Receive("move_made", ServerMessages.MoveMade(2));
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 2 }));
            Assert.That(_app.Status, Is.EqualTo("Rakibin sırası..."));
        }

        [Test]
        public void StaleMoveEventIsIgnored()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            _app.HandleColumnClick(4);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(2));

            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3, 4 }));
        }

        [Test]
        public void MissedMovesAreLoadedFromSnapshot()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            int animations = 0;
            _app.AnimateDrop = (col, row, piece, done) =>
            {
                animations++;
                done();
            };

            _transport.Receive("move_made", ServerMessages.MoveMade(3, 4, 3));
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3, 4, 3 }));
            Assert.That(animations, Is.EqualTo(0), "kacan hamleler animasyonsuz yuklenir");
            Assert.That(_app.Status, Is.EqualTo("Senin sıran!"));
        }

        [Test]
        public void MoveEventsOutsideAGameAreIgnored()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
        }

        [Test]
        public void WinningOpponentMoveEndsGameLocally()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            int[] moves = Fixtures.P1VerticalWin;   // P1: 0,0,0,0  P2: 1,1,1
            for (int i = 0; i < moves.Length; i++)
            {
                if (i % 2 == 0)
                {
                    var upTo = new int[i + 1];
                    System.Array.Copy(moves, upTo, i + 1);
                    _transport.Receive("move_made", ServerMessages.MoveMade(upTo));
                }
                else
                    _app.HandleColumnClick(moves[i]);
            }

            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.Game.Winner, Is.EqualTo(Board.Player1));
            Assert.That(_app.Status, Is.EqualTo("ali kazandı!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.CanHumanMove(), Is.False);
        }

        // ---------------------------------------------------------------------
        // Online oyun: sonuc
        // ---------------------------------------------------------------------

        [Test]
        public void GameOverWinShowsResultAndElo()
        {
            LoginAsAli();
            StartOnlineGameAsP1();
            int callsBefore = _api.Calls.Count;
            _transport.Receive("game_over",
                "{\"winner\":1,\"winner_uid\":\"Ali\",\"elo_changes\":{\"p1\":15,\"p2\":-15}," +
                "\"new_ratings\":{\"p1\":1352,\"p2\":1235},\"move_count\":7,\"reason\":\"normal\"}");

            Assert.That(_app.Status, Is.EqualTo("Kazandın!  ELO +15 (1352)"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Good));
            Assert.That(_app.LastEloChange, Is.EqualTo(15));
            Assert.That(_app.UserElo, Is.EqualTo(1352));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));

            // Kayitli oyuncunun ELO'su sunucudan da tazelenir
            Assert.That(_api.Calls.Count, Is.EqualTo(callsBefore + 1));
            Assert.That(LastCall.Method, Is.EqualTo("User"));
            LastCall.Respond(200, "{\"user\":{\"username\":\"Ali\",\"rating\":1353}}");
            Assert.That(_app.UserElo, Is.EqualTo(1353));
        }

        [Test]
        public void GameOverLossForSecondPlayer()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            _transport.Receive("game_over",
                "{\"winner\":1,\"elo_changes\":{\"p1\":0,\"p2\":0},\"new_ratings\":{\"p1\":null,\"p2\":null},\"reason\":\"normal\"}");
            Assert.That(_app.Status, Is.EqualTo("Kaybettin."));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.LastEloChange, Is.Null);
            Assert.That(_api.Calls, Is.Empty, "misafirin ELO'su sorulmaz");
        }

        [Test]
        public void GameOverDraw()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("game_over",
                "{\"winner\":null,\"elo_changes\":{\"p1\":0,\"p2\":0},\"new_ratings\":{\"p1\":null,\"p2\":null},\"reason\":\"normal\"}");
            Assert.That(_app.Status, Is.EqualTo("Berabere!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Neutral));
        }

        [Test]
        public void ForfeitWinEndsGameWithoutBoardWin()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("game_over", "{\"winner\":1,\"elo_changes\":{},\"new_ratings\":{},\"reason\":\"forfeit\"}");
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.Game.Winner, Is.EqualTo(Board.Player1));
            Assert.That(_app.Status, Is.EqualTo("Rakip oyunu terk etti - Kazandın!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Good));
            Assert.That(_app.CanHumanMove(), Is.False);
        }

        [Test]
        public void ForfeitLoss()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("game_over", "{\"winner\":2,\"elo_changes\":{},\"new_ratings\":{},\"reason\":\"forfeit\"}");
            Assert.That(_app.Game.Winner, Is.EqualTo(Board.Player2));
            Assert.That(_app.Status, Is.EqualTo("Hükmen kaybettin."));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        [Test]
        public void ServerResultSurvivesLateWinningMoveAnimation()
        {
            // game_over (ELO ile) son hamlenin animasyonu bitmeden gelirse metin korunur
            LoginAsAli();
            StartOnlineGameAsP2();
            int[] moves = Fixtures.P1VerticalWin;
            for (int i = 0; i < moves.Length - 1; i++)
            {
                if (i % 2 == 0)
                {
                    var upTo = new int[i + 1];
                    System.Array.Copy(moves, upTo, i + 1);
                    _transport.Receive("move_made", ServerMessages.MoveMade(upTo));
                }
                else
                    _app.HandleColumnClick(moves[i]);
            }
            System.Action finish = null;
            _app.AnimateDrop = (col, row, piece, done) => finish = done;
            _transport.Receive("move_made", ServerMessages.MoveMade(moves));
            _transport.Receive("game_over",
                "{\"winner\":1,\"elo_changes\":{\"p1\":15,\"p2\":-15},\"new_ratings\":{\"p1\":1315,\"p2\":1322},\"reason\":\"normal\"}");
            finish();

            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.Status, Is.EqualTo("Kaybettin.  ELO -15 (1322)"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        [Test]
        public void EloUpdateEventChangesRating()
        {
            LoginAsAli();
            StartOnlineGameAsP1();
            _transport.Receive("elo_update", "{\"new_elo\":1350,\"change\":13,\"winner\":true}");
            Assert.That(_app.UserElo, Is.EqualTo(1350));
            Assert.That(_app.LastEloChange, Is.EqualTo(13));
        }

        [Test]
        public void OpponentDisconnectAndReturnAreAnnounced()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("opponent_disconnected", "{\"msg\":\"Rakip ayrildi\",\"grace_seconds\":45}");
            Assert.That(_app.Status, Is.EqualTo("Rakibin bağlantısı koptu! 45 sn içinde dönmezse kazanırsın."));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));

            _transport.Receive("opponent_reconnected", "{\"msg\":\"Rakip geri dondu\"}");
            Assert.That(_app.Status, Is.EqualTo("Rakip geri döndü. Senin sıran!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Neutral));
        }

        [Test]
        public void RoomTimeoutIsAnnounced()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("game_ended", "{\"reason\":\"timeout\"}");
            Assert.That(_app.Status, Is.EqualTo("Oda zaman aşımı nedeniyle kapatıldı."));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        // ---------------------------------------------------------------------
        // Cikis
        // ---------------------------------------------------------------------

        [Test]
        public void LeavingLiveGameNeedsConfirmationWithinWindow()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Time.unscaledTime = 10f;

            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.LeaveConfirmPending, Is.True);
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_transport.EmittedOf("leave_game"), Is.Empty);

            // Sure doldu: onay dusmus, tekrar basmak yeniden sorar
            Time.unscaledTime = 10f + AppController.LeaveConfirmSeconds + 0.1f;
            Assert.That(_app.LeaveConfirmPending, Is.False);
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_transport.EmittedOf("leave_game"), Is.Empty);

            Time.unscaledTime += 1f;
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_transport.EmittedOf("leave_game")[0].GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(_transport.DisconnectCalls, Is.EqualTo(1));
            Assert.That(_app.RoomId, Is.Null);
            Assert.That(_app.LeaveConfirmPending, Is.False);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
        }

        [Test]
        public void LeavingWaitingRoomIsImmediateAndCancelsRoom()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);

            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_transport.EmittedOf("leave_game").Count, Is.EqualTo(1));
        }

        [Test]
        public void OldRoomEventsAreIgnoredAfterReturningToMenu()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.ResetToMenu();

            // Yeni soket eski odayi bilmez: yeniden baglaninca geri katilmamali
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game"), Is.Empty);
            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
        }

        [Test]
        public void ShutdownLeavesLiveGameAndDisconnects()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.Shutdown();
            Assert.That(_transport.EmittedOf("leave_game").Count, Is.EqualTo(1));
            Assert.That(_transport.DisconnectCalls, Is.EqualTo(1));
        }

        // ---------------------------------------------------------------------
        // AI oyunu (AIRunner gercek saatle calisir: AIMoveDelaySeconds kadar bekler)
        // ---------------------------------------------------------------------

        [Test]
        public void AIGameAnswersHumanMove()
        {
            _app.GuestLogin();
            _app.StartAIGame(2);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingAI));
            Assert.That(_app.Status, Is.EqualTo("Senin sıran!"));
            Assert.That(_app.CanHumanMove(), Is.True);

            _app.HandleColumnClick(3);
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3 }));
            Assert.That(_app.AIThinking, Is.True);
            Assert.That(_app.Status, Is.EqualTo("AI düşünüyor..."));
            Assert.That(_app.CanHumanMove(), Is.False);

            Assert.That(AIRunnerTests.TickUntil(_app.Tick, () => _app.Game.MoveCount == 2), "AI hamle yapmadi");
            Assert.That(_app.AIThinking, Is.False);
            Assert.That(_app.Game.CurrentPlayer, Is.EqualTo(Board.Player1));
            Assert.That(_app.Status, Is.EqualTo("Senin sıran!"));
            Assert.That(_transport.Emitted, Is.Empty, "AI oyununda sunucuya hamle gitmez");
        }

        [Test]
        public void LeavingAIGameCancelsPendingAIMove()
        {
            _app.GuestLogin();
            _app.StartAIGame(2);
            _app.HandleColumnClick(3);
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.AIThinking, Is.False);
            Assert.That(_app.Engine, Is.Null);

            _app.StartAIGame(2);
            var clock = System.Diagnostics.Stopwatch.StartNew();
            while (clock.Elapsed.TotalSeconds < AppController.AIMoveDelaySeconds + 0.3)
                _app.Tick();
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0), "iptal edilen arama yeni oyuna hamle yapmamali");
        }
    }
}
