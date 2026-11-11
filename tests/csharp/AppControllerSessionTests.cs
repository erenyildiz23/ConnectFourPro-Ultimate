// Online oturumun saglamligi (Game/AppController.cs): kendi baglanti kopmamiz, geri
// donus, reddedilen geri donus, kapanan oda, cift tiklama ve gec gelen yanitlar.
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using ConnectFourPro.Net;
using NUnit.Framework;
using UnityEngine;

namespace ConnectFourPro.Tests
{
    public partial class AppControllerTests
    {
        private const string Rejoined1 =
            "{\"room_id\":\"AB12C\",\"player_piece\":1,\"role\":\"player\",\"rejoined\":true,\"current_state\":{0}," +
            "\"opponent_info\":{\"username\":\"veli\",\"rating\":1250},\"rejoin_token\":\"seat-1\"}";

        private static string RejoinedAsP1(GameState state) =>
            Rejoined1.Replace("{0}", ServerMessages.Snapshot(state));

        private static string SpectatorJoined(GameState state) =>
            "{\"room_id\":\"AB12C\",\"player_piece\":0,\"role\":\"spectator\",\"current_state\":" +
            ServerMessages.Snapshot(state) + "," +
            "\"p1_info\":{\"username\":\"ali\",\"rating\":1300},\"p2_info\":{\"username\":\"veli\",\"rating\":1250}}";

        // ---------------------------------------------------------------------
        // Kendi baglantimiz koptu
        // ---------------------------------------------------------------------

        [Test]
        public void OwnDisconnectIsShownAndBlocksMoves()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Assert.That(_app.CanHumanMove(), Is.True);

            _transport.RaiseDisconnected("transport close");
            Assert.That(_app.Offline, Is.True);
            Assert.That(_app.Status, Does.StartWith("Bağlantı koptu!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.CanHumanMove(), Is.False);

            _app.HandleColumnClick(3);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0), "kopukken yerel hayalet tas birakilmamali");
            Assert.That(_transport.EmittedOf("make_move"), Is.Empty);
        }

        [Test]
        public void DisconnectDuringOwnDropAnimationDoesNotApplyMove()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            System.Action finish = null;
            _app.AnimateDrop = (col, row, piece, done) => finish = done;
            _app.HandleColumnClick(3);
            _transport.RaiseDisconnected("transport close");
            finish();

            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(_transport.EmittedOf("make_move"), Is.Empty);
            Assert.That(_app.Status, Is.EqualTo("Bağlantı yok, hamle gönderilemedi."));
        }

        [Test]
        public void ReconnectCountdownIsShownAndRejoinRestoresPlay()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Time.unscaledTime = 100f;
            _transport.RaiseDisconnected("transport close");

            Time.unscaledTime = 100.5f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo("Bağlantı koptu! Yeniden bağlanılıyor... (30 sn)"));
            Time.unscaledTime = 110.2f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo("Bağlantı koptu! Yeniden bağlanılıyor... (20 sn)"));

            // socket.io yeniden baglandi: tek bir geri katilma istegi, koltuk anahtariyla
            _transport.RaiseConnected();
            var joins = _transport.EmittedOf("join_game");
            Assert.That(joins.Count, Is.EqualTo(1));
            Assert.That(joins[0].GetString("rejoin_token"), Is.EqualTo("seat-1"));
            Assert.That(_app.CanHumanMove(), Is.False, "game_joined gelene kadar hamle yok");

            _transport.Receive("game_joined", RejoinedAsP1(new GameState()));
            Assert.That(_app.Offline, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Oyuna geri dönüldü. Senin sıran!"));
            Assert.That(_app.CanHumanMove(), Is.True);

            Time.unscaledTime = 115f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo("Oyuna geri dönüldü. Senin sıran!"), "sayac durmali");
        }

        [Test]
        public void ExpiredCountdownEndsSessionWithoutForfeitConfirmation()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Time.unscaledTime = 5f;
            _transport.RaiseDisconnected("transport close");
            Time.unscaledTime = 5f + AppController.ReconnectGraceDefault + 1f;
            _app.Tick();

            Assert.That(_app.SessionDead, Is.True);
            Assert.That(_app.Status, Does.Contain("yeniden bağlanılamadı"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.CanHumanMove(), Is.False);

            _app.RequestBack();
            Assert.That(_app.LeaveConfirmPending, Is.False);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby), "olu oturumdan tek basista cikilir");
        }

        [Test]
        public void RejoinAfterLocalCountdownExpiredRevivesSession()
        {
            // Sunucunun suresi kopmayi fark edince baslar; yerel sayactan sonra da donulebilir
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.RaiseDisconnected("transport close");
            Time.unscaledTime = AppController.ReconnectGraceDefault + 5f;
            _app.Tick();
            Assert.That(_app.SessionDead, Is.True);

            _transport.RaiseConnected();
            _transport.Receive("game_joined", RejoinedAsP1(new GameState()));
            Assert.That(_app.SessionDead, Is.False);
            Assert.That(_app.Offline, Is.False);
            Assert.That(_app.CanHumanMove(), Is.True);
        }

        [Test]
        public void RejoiningFinishedGameShowsForfeitResult()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();

            var state = GameState.FromMoves(new[] { 3, 4 });
            state.GameOver = true;      // sunucu hukmen bitirdi: tahtada dortlu yok
            state.Winner = Board.Player2;
            _transport.Receive("game_joined", RejoinedAsP1(state));

            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.Status, Is.EqualTo("Bağlantın koptuğu için hükmen kaybettin."));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.CanHumanMove(), Is.False);
        }

        [TestCase(new[] { 0, 1, 0, 1, 0, 1, 0 }, "Kazandın!", StatusTone.Good)]
        [TestCase(new[] { 0, 1, 0, 1, 0, 1, 2, 1 }, "Kaybettin.", StatusTone.Bad)]
        public void RejoiningFinishedGameShowsBoardResult(int[] moves, string expected, StatusTone tone)
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", RejoinedAsP1(GameState.FromMoves(moves)));
            Assert.That(_app.Status, Is.EqualTo(expected));
            Assert.That(_app.Tone, Is.EqualTo(tone));
        }

        [TestCase("Yeniden baglanma anahtari gecersiz")]
        [TestCase("Oda bulunamadi")]
        public void RefusedRejoinEndsSession(string error)
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            _transport.Receive("error", "{\"msg\":\"" + error + "\"}");

            Assert.That(_app.SessionDead, Is.True);
            Assert.That(_app.Offline, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Oyun sunucuda sona ermiş. Lobiye dönebilirsin."));
            Assert.That(_app.CanHumanMove(), Is.False);
            Time.unscaledTime = 100f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo("Oyun sunucuda sona ermiş. Lobiye dönebilirsin."));
        }

        [Test]
        public void OwnLeaveIsNotReportedAsConnectionLoss()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.ResetToMenu();   // FakeTransport.Disconnect "io client disconnect" yollar
            Assert.That(_app.Offline, Is.False);
            Assert.That(_app.Status, Is.Empty);
        }

        [Test]
        public void LeaveConfirmationIsNotOverwrittenByCountdown()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.RaiseDisconnected("transport close");
            _app.RequestBack();
            Assert.That(_app.LeaveConfirmPending, Is.True);
            string confirm = _app.Status;
            Time.unscaledTime = 1.5f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo(confirm));
        }

        [Test]
        public void WaitingRoomDropIsAnnouncedAndMissingRoomReturnsToLobby()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            _transport.RaiseDisconnected("transport close");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Waiting));
            Assert.That(_app.Status, Does.StartWith("Bağlantı koptu!"));

            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game").Count, Is.EqualTo(1));
            _transport.Receive("error", "{\"msg\":\"Oda bulunamadi\"}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby));
        }

        [Test]
        public void SpectatorReconnectRejoinsBroadcast()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3, 4 })));

            _transport.RaiseDisconnected("transport close");
            Assert.That(_app.Status, Does.StartWith("Bağlantı koptu!"));
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game").Count, Is.EqualTo(2));

            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3, 4, 3 })));
            Assert.That(_app.Offline, Is.False);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(3));
            Assert.That(_app.Status, Is.EqualTo("Yayına geri dönüldü. Canlı izleniyor"));
        }

        [Test]
        public void SpectatorCountdownExpires()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            _transport.RaiseDisconnected("transport close");
            Time.unscaledTime = AppController.ReconnectGraceDefault + 1f;
            _app.Tick();
            Assert.That(_app.Status, Does.StartWith("Yayın bağlantısı geri gelmedi"));
        }

        [Test]
        public void SpectatorRejoinOfFinishedGameShowsResult()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(Fixtures.P1VerticalWin)));
            Assert.That(_app.Status, Is.EqualTo("Kırmızı kazandı!"));
        }

        [Test]
        public void OpponentGraceCountsDownUntilReturn()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Time.unscaledTime = 10f;
            _transport.Receive("opponent_disconnected", "{\"grace_seconds\":30}");
            Assert.That(_app.Status, Is.EqualTo("Rakibin bağlantısı koptu! 30 sn içinde dönmezse kazanırsın."));

            Time.unscaledTime = 22.5f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo("Rakibin bağlantısı koptu! 18 sn içinde dönmezse kazanırsın."));
            Time.unscaledTime = 60f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo("Rakibin bağlantısı koptu! 0 sn içinde dönmezse kazanırsın."));

            _transport.Receive("opponent_reconnected", "{}");
            Time.unscaledTime = 61f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo("Rakip geri döndü. Senin sıran!"));
        }

        // ---------------------------------------------------------------------
        // Cikmaz durumlar: kapanan oda, sunucuda olmayan oda
        // ---------------------------------------------------------------------

        [Test]
        public void WaitingRoomTimeoutReturnsToLobbyAndDoesNotRejoin()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            int calls = _api.Calls.Count;

            _transport.Receive("game_ended", "{\"reason\":\"timeout\"}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby));
            Assert.That(_app.RoomId, Is.Null);
            Assert.That(_app.Status, Is.EqualTo("Oda zaman aşımına uğradı."));
            Assert.That(_api.Calls.Count, Is.EqualTo(calls + 1), "lobi listesi tazelenir");
            Assert.That(LastCall.Method, Is.EqualTo("ActiveGames"));

            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game"), Is.Empty, "olu odaya geri katilinmaz");
        }

        [Test]
        public void ClosedRoomDuringGameBlocksMovesAndLeavesWithoutConfirmation()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("game_ended", "{\"reason\":\"timeout\"}");
            Assert.That(_app.CanHumanMove(), Is.False);
            _app.HandleColumnClick(3);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));

            _app.RequestBack();
            Assert.That(_app.LeaveConfirmPending, Is.False);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby));
        }

        [Test]
        public void MissingRoomDuringGameEndsSession()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.HandleColumnClick(3);
            _transport.Receive("error", "{\"msg\":\"Oda bulunamadi\"}");
            Assert.That(_app.SessionDead, Is.True);
            Assert.That(_app.Status, Is.EqualTo("Oyun sunucuda sona ermiş. Lobiye dönebilirsin."));
            _transport.Receive("move_made", ServerMessages.MoveMade(3, 4));
            Assert.That(_app.CanHumanMove(), Is.False);
        }

        [Test]
        public void OtherServerErrorsDuringGameOnlyShowMessage()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("error", "{\"msg\":\"Yeniden baglanma anahtari gecersiz\"}");
            Assert.That(_app.SessionDead, Is.False, "bagliyken bu hata oyunu bitirmez");
            Assert.That(_app.Status, Is.EqualTo("Hata: Yeniden baglanma anahtari gecersiz"));
            Assert.That(_app.CanHumanMove(), Is.True);
        }

        [Test]
        public void PreviousGameEloDoesNotLeakIntoSpectatedResult()
        {
            // 'Katil' tiklamasi oda dolunca seyirci olarak sonuclanabilir
            LoginAsAli();
            StartOnlineGameAsP1();
            _transport.Receive("game_over",
                "{\"winner\":1,\"elo_changes\":{\"p1\":12,\"p2\":-12},\"new_ratings\":{\"p1\":1349,\"p2\":1238},\"reason\":\"normal\"}");
            _app.ResetToMenu();

            _app.JoinOnlineGame("XY9Z0");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            _transport.Receive("game_over", "{\"winner\":2,\"elo_changes\":{},\"new_ratings\":{},\"reason\":\"forfeit\"}");
            Assert.That(_app.LastEloChange, Is.Null);
            Assert.That(_app.Status, Does.Not.Contain("ELO"));
        }

        // ---------------------------------------------------------------------
        // Cift gonderim ve gec gelen yanitlar
        // ---------------------------------------------------------------------

        [Test]
        public void DoubleJoinClickSendsOneRequest()
        {
            _app.GuestLogin();
            _app.OpenLobby();
            _app.JoinOnlineGame("AB12C");
            _app.JoinOnlineGame("AB12C");
            _app.JoinOnlineGame("XY9Z0");
            _app.CreateOnlineGame();
            _app.SpectateGame("XY9Z0");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game").Count, Is.EqualTo(1));
            Assert.That(_transport.EmittedOf("create_game"), Is.Empty);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby));

            // Yanit gelince kilit kalkar
            _transport.Receive("error", "{\"msg\":\"Oda bulunamadi\"}");
            _app.JoinOnlineGame("XY9Z0");
            Assert.That(_transport.EmittedOf("join_game").Count, Is.EqualTo(2));
        }

        [Test]
        public void JoinLockIsReleasedByConnectionLossOrLeaving()
        {
            _app.GuestLogin();
            _app.OpenLobby();
            _app.JoinOnlineGame("AB12C");
            _transport.RaiseConnected();
            _transport.RaiseDisconnected("transport close");
            _app.JoinOnlineGame("AB12C");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game").Count, Is.EqualTo(2), "kopma kilidi acar");

            _app.ResetToMenu();
            _app.OpenLobby();
            _app.JoinOnlineGame("AB12C");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game").Count, Is.EqualTo(3), "lobiden cikis kilidi acar");
        }

        [Test]
        public void JoinLockIsReleasedByConnectFailure()
        {
            _app.GuestLogin();
            _app.OpenLobby();
            _app.JoinOnlineGame("AB12C");
            _transport.RaiseConnectError("timeout");
            _app.JoinOnlineGame("AB12C");
            Assert.That(_transport.ConnectUrls.Count, Is.EqualTo(2));
        }

        [Test]
        public void LateLoginResponseDoesNotReplaceGuestSession()
        {
            _app.Login("ali", "secret12");
            var login = LastCall;
            _app.GuestLogin();
            _app.CreateOnlineGame();
            login.Respond(200, LoginOk);

            Assert.That(_app.Username, Does.StartWith("Misafir_"));
            Assert.That(_app.IsGuest, Is.True);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Waiting));
            Assert.That(_app.AuthPending, Is.False);
        }

        [Test]
        public void LateSignupResponseAfterLogoutIsIgnored()
        {
            _app.Register("yeni", "secret12");
            var signup = LastCall;
            _app.Logout();
            signup.Respond(201, "{\"token\":\"tok-2\"}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Login));
            Assert.That(_app.Username, Is.Empty);
        }

        [Test]
        public void LateEloRefreshDoesNotLeakIntoNextSession()
        {
            LoginAsAli();
            _app.ResetToMenu();   // kayitli oyuncu icin /user istegi
            var refresh = LastCall;
            Assert.That(refresh.Method, Is.EqualTo("User"));
            _app.Logout();
            _app.GuestLogin();
            refresh.Respond(200, "{\"user\":{\"username\":\"Ali\",\"rating\":1500}}");
            Assert.That(_app.UserElo, Is.EqualTo(UserInfo.DefaultRating));
        }

        // ---------------------------------------------------------------------
        // Lobi listesi
        // ---------------------------------------------------------------------

        private const string OneWaitingRoom =
            "[{\"room_id\":\"AB12C\",\"p1\":\"ali\",\"p1_elo\":1250,\"p2\":\"Bekleniyor...\",\"p2_elo\":0,\"status\":\"WAITING\",\"move_count\":0}]";

        [Test]
        public void UnchangedLobbyListDoesNotBumpVersion()
        {
            _app.GuestLogin();
            _app.OpenLobby();
            LastCall.Respond(200, OneWaitingRoom);
            Assert.That(_app.ActiveGamesVersion, Is.EqualTo(1));

            _app.RefreshActiveGames();
            LastCall.Respond(200, OneWaitingRoom);
            Assert.That(_app.ActiveGamesVersion, Is.EqualTo(1), "ayni liste satirlari yeniden kurdurmamali");

            _app.RefreshActiveGames();
            LastCall.Respond(200, OneWaitingRoom.Replace("WAITING", "PLAYING").Replace("\"move_count\":0", "\"move_count\":2"));
            Assert.That(_app.ActiveGamesVersion, Is.EqualTo(2));
            Assert.That(_app.ActiveGames[0].Waiting, Is.False);

            _app.RefreshActiveGames();
            LastCall.Respond(200, "[]");
            Assert.That(_app.ActiveGamesVersion, Is.EqualTo(3));
            Assert.That(_app.ActiveGames, Is.Empty);
        }

        // ---------------------------------------------------------------------
        // Sonuc basligi, geri hedefi, tekrar oyna
        // ---------------------------------------------------------------------

        [TestCase(1, "KAZANDIN!", StatusTone.Good)]
        [TestCase(2, "KAYBETTİN", StatusTone.Bad)]
        public void OnlineResultHeadline(int winner, string text, StatusTone tone)
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Assert.That(_app.ResultHeadline, Is.Null);
            _transport.Receive("game_over", "{\"winner\":" + winner + ",\"elo_changes\":{},\"new_ratings\":{},\"reason\":\"forfeit\"}");
            Assert.That(_app.ResultHeadline, Is.EqualTo(((string, StatusTone)?)(text, tone)));
        }

        [Test]
        public void DrawAndSpectatorHeadlines()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            _transport.Receive("game_over", "{\"winner\":2,\"elo_changes\":{},\"new_ratings\":{},\"reason\":\"forfeit\"}");
            Assert.That(_app.ResultHeadline, Is.EqualTo(((string, StatusTone)?)("SARI KAZANDI", StatusTone.Neutral)));

            _app.ResetToMenu();
            StartOnlineGameAsP1();
            _app.Game.GameOver = true;   // berabere: kazanan yok
            Assert.That(_app.ResultHeadline, Is.EqualTo(((string, StatusTone)?)("BERABERE", StatusTone.Neutral)));
        }

        [Test]
        public void BackFromBroadcastGoesToLobbyAndLabelsFollowScreen()
        {
            _app.GuestLogin();
            _app.StartAIGame(1);
            Assert.That(_app.BackLabel, Is.EqualTo("Menü"));
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu), "AI oyunundan menuye donulur");

            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            Assert.That(_app.BackLabel, Is.EqualTo("Lobiye Dön"));
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby));
            Assert.That(LastCall.Method, Is.EqualTo("ActiveGames"));
            Assert.That(_app.Status, Is.Empty);

            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu), "lobiden menuye");

            StartOnlineGameAsP1();
            Assert.That(_app.BackLabel, Is.EqualTo("Lobiye Dön"));
            _app.RequestBack();
            Assert.That(_app.BackLabel, Is.EqualTo("Çıkışı Onayla"));
        }

        [Test]
        public void PlayAgainRestartsAIGameWithSameDepthAndSwapsStarter()
        {
            _app.GuestLogin();
            _app.StartAIGame(1);
            Assert.That(_app.AIStarts, Is.False);
            Assert.That(_app.NewGameLabel, Is.EqualTo("Yeni Oyun"));

            // Basit strateji: hep ilk gecerli sutun; derinlik 1 AI'ya karsi oyun kisa surer
            while (!_app.Game.GameOver)
            {
                int col = _app.Game.GetValidLocations()[0];
                int before = _app.Game.MoveCount;
                _app.HandleColumnClick(col);
                Assert.That(_app.Game.MoveCount, Is.EqualTo(before + 1));
                if (_app.Game.GameOver)
                    break;
                Assert.That(AIRunnerTests.TickUntil(_app.Tick, () => _app.Game.MoveCount == before + 2), "AI hamle yapmadi");
            }
            Assert.That(_app.ResultHeadline, Is.Not.Null);
            Assert.That(_app.NewGameLabel, Is.EqualTo("Tekrar Oyna"));

            _app.PlayAgain();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingAI));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(_app.Engine.Depth, Is.EqualTo(1));
            Assert.That(_app.AIStarts, Is.True, "ilk hamle sirasi degisir");
            Assert.That(_app.Status, Is.EqualTo("AI düşünüyor..."));
            Assert.That(_app.ResultHeadline, Is.Null);
            Assert.That(AIRunnerTests.TickUntil(_app.Tick, _app.CanHumanMove), "AI ilk hamleyi yapmadi");
            Assert.That(_app.Game.MoveCount, Is.EqualTo(1));
            Assert.That(_app.Status, Is.EqualTo("Senin sıran!"));

            _app.PlayAgain();   // oyun surerken de: yine insan baslar
            Assert.That(_app.AIStarts, Is.False);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(_app.Status, Is.EqualTo(AppController.CoachText));
        }

        // ---------------------------------------------------------------------
        // Tahta: dolu sutun, "(Sen)" etiketi, analiz ozeti
        // ---------------------------------------------------------------------

        [Test]
        public void FullColumnClickOnOwnTurnSaysSo()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("move_made", ServerMessages.MoveMade(0, 0, 0, 0, 0, 0));
            Assert.That(_app.CanHumanMove(), Is.True);
            _app.HandleColumnClick(0);
            Assert.That(_app.Status, Is.EqualTo("Bu sütun dolu!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(6));
            Assert.That(_transport.EmittedOf("make_move"), Is.Empty);

            _app.HandleColumnClick(1);
            Assert.That(_app.Status, Is.EqualTo("Rakibin sırası..."));
            _app.HandleColumnClick(0);   // sira rakipte: dolu sutun bile sessiz
            Assert.That(_app.Status, Is.EqualTo("Rakibin sırası..."));
        }

        [Test]
        public void FullColumnIsSilentWhileAIThinks()
        {
            _app.GuestLogin();
            _app.StartAIGame(1);
            _app.HandleColumnClick(3);
            _app.HandleColumnClick(3);
            Assert.That(_app.Status, Is.EqualTo("AI düşünüyor..."));
            _app.HandleColumnClick(-1);
            _app.HandleColumnClick(7);
            Assert.That(_app.Status, Is.EqualTo("AI düşünüyor..."));
        }

        [Test]
        public void LocalPieceIsMarkedForPlayersOnly()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            Assert.That(_app.IsLocalPiece(Board.Player2), Is.True);
            Assert.That(_app.IsLocalPiece(Board.Player1), Is.False);

            _app.ResetToMenu();
            _app.StartAIGame(1);
            Assert.That(_app.IsLocalPiece(Board.Player1), Is.True);
            Assert.That(_app.IsLocalPiece(Board.Player2), Is.False);

            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            Assert.That(_app.IsLocalPiece(Board.Player1), Is.False);
            Assert.That(_app.IsLocalPiece(Board.Player2), Is.False);
        }

        [Test]
        public void SummaryIsNotRebuiltEveryFrameAfterGameOver()
        {
            _app.AnalysisEnabled = true;
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.HandleColumnClick(3);
            _transport.Receive("move_made", ServerMessages.MoveMade(3, 3));
            _transport.Receive("game_over", "{\"winner\":1,\"elo_changes\":{},\"new_ratings\":{},\"reason\":\"forfeit\"}");

            Assert.That(AIRunnerTests.TickUntil(_app.Tick, () => _app.Summary != null && _app.Summary.TotalMoves == 2, 60),
                        "analizler tamamlanmadi");
            var summary = _app.Summary;
            _app.Tick();
            _app.Tick();
            Assert.That(_app.Summary, Is.SameAs(summary));
        }
    }
}
