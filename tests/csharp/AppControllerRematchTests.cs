// Yeni sunucu ozellikleri (Game/AppController.cs): rovans, hamle suresi geri sayimi,
// game_over.detail metinleri ve yokken biten oyunun game_joined.result'i. Eski sunucu
// bu alanlari gondermez; o durumda eski davranis surmelidir.
using System.Collections.Generic;
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using ConnectFourPro.Net;
using NUnit.Framework;
using UnityEngine;

namespace ConnectFourPro.Tests
{
    public partial class AppControllerTests
    {
        private const string OldServerWin = "{\"winner\":1,\"elo_changes\":{},\"new_ratings\":{},\"reason\":\"forfeit\"}";

        private static string Offer(int fromPiece) =>
            "{\"room_id\":\"AB12C\",\"from_piece\":" + fromPiece + ",\"from\":\"x\"}";

        // Varsayilan: sure doldu (tahtada dortlu gerekmez, iki oyuncu da odada kalir)
        private void FinishOnNewServer(int? winner = 1, string reason = "forfeit", string detail = "timeout") =>
            _transport.Receive("game_over", ServerMessages.GameOver(winner, reason, detail));

        private static string Timed(string json, int? secondsLeft, int moveTime = 30) =>
            ServerMessages.WithFields(json, ServerMessages.Clock(secondsLeft, moveTime));

        // ---------------------------------------------------------------------
        // Rovans
        // ---------------------------------------------------------------------

        [Test]
        public void OldServerGameOverOffersNoRematch()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("game_over", OldServerWin);
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.CanRequestRematch, Is.False, "rovans_request'i bilmeyen sunucuda buton yok");
            _app.RequestRematch();
            Assert.That(_transport.EmittedOf("rematch_request"), Is.Empty);
        }

        [Test]
        public void RematchIsOfferedToPlayersOnlyAfterGameOver()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Assert.That(_app.CanRequestRematch, Is.False, "oyun suruyor");
            FinishOnNewServer();
            Assert.That(_app.CanRequestRematch, Is.True);
            Assert.That(_app.RematchLabel, Is.EqualTo("Rövanş"));

            _app.ResetToMenu();
            Assert.That(_app.CanRequestRematch, Is.False);
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.None));

            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            FinishOnNewServer(2, "forfeit", "leave");
            Assert.That(_app.CanRequestRematch, Is.False, "seyirci rovans isteyemez");
        }

        [Test]
        public void RequestRematchSendsRoomOnceAndWaitsForOpponent()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer();
            _app.RequestRematch();

            var sent = _transport.EmittedOf("rematch_request");
            Assert.That(sent.Count, Is.EqualTo(1));
            Assert.That(sent[0].GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.OfferedByMe));
            Assert.That(_app.Status, Is.EqualTo("Rövanş istendi, rakip bekleniyor..."));
            Assert.That(_app.CanRequestRematch, Is.False);

            _app.RequestRematch();
            Assert.That(_transport.EmittedOf("rematch_request").Count, Is.EqualTo(1), "ikinci tiklama gitmez");

            // Sunucu teklifi odaya (bize de) yayinlar: kendi yankimiz durumu degistirmez
            _transport.Receive("rematch_offered", Offer(Board.Player1));
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.OfferedByMe));
            Assert.That(_app.Status, Is.EqualTo("Rövanş istendi, rakip bekleniyor..."));
        }

        [Test]
        public void OpponentOfferIsAnnouncedAndCanBeAccepted()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            FinishOnNewServer(1);
            _transport.Receive("rematch_offered", Offer(Board.Player1));

            Assert.That(_app.Rematch, Is.EqualTo(RematchState.OfferedByOpponent));
            Assert.That(_app.Status, Is.EqualTo("Rakip rövanş istiyor!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Good));
            Assert.That(_app.RematchLabel, Is.EqualTo("Rövanşı Kabul Et"));
            Assert.That(_app.CanRequestRematch, Is.True);

            _app.RequestRematch();
            Assert.That(_transport.EmittedOf("rematch_request").Count, Is.EqualTo(1));
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.OfferedByMe));
        }

        [Test]
        public void OfferForAnotherRoomOrDuringGameIsIgnored()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            string status = _app.Status;
            _transport.Receive("rematch_offered", Offer(Board.Player2));
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.None), "oyun suruyor");
            Assert.That(_app.Status, Is.EqualTo(status));

            FinishOnNewServer();
            _transport.Receive("rematch_offered", "{\"room_id\":\"XY9Z0\",\"from_piece\":2}");
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.None));
        }

        [Test]
        public void UnavailableRematchIsAnnouncedAndHidesButton()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer();
            _app.RequestRematch();
            _transport.Receive("rematch_unavailable", "{\"room_id\":\"AB12C\",\"reason\":\"opponent_left\"}");

            Assert.That(_app.Rematch, Is.EqualTo(RematchState.Unavailable));
            Assert.That(_app.Status, Is.EqualTo("Rakip ayrıldı, rövanş yapılamaz."));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.CanRequestRematch, Is.False);

            _transport.Receive("rematch_offered", Offer(Board.Player2));
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.Unavailable), "gec gelen teklif geri acmaz");
        }

        [TestCase("leave")]
        [TestCase("disconnect")]
        public void OpponentGoneWinOffersNoRematch(string detail)
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer(1, "forfeit", detail);
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.Unavailable));
            Assert.That(_app.CanRequestRematch, Is.False);
        }

        [Test]
        public void TimeoutLossStillOffersRematch()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer(2, "forfeit", "timeout");
            Assert.That(_app.CanRequestRematch, Is.True, "sure dolunca iki oyuncu da odada");
        }

        [Test]
        public void ConnectionLossAfterGameOverEndsRematch()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer();
            _app.RequestRematch();
            _transport.RaiseDisconnected("transport close");

            Assert.That(_app.Rematch, Is.EqualTo(RematchState.Unavailable));
            Assert.That(_app.Status, Is.EqualTo("Bağlantı koptu, rövanş yapılamaz."));
            Assert.That(_app.Offline, Is.False, "biten oyunda geri sayim yok");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game"), Is.Empty);
            Assert.That(_app.CanRequestRematch, Is.False);
        }

        [Test]
        public void ServerErrorOnRematchRequestMakesItUnavailable()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer();
            _app.RequestRematch();
            _transport.Receive("error", "{\"msg\":\"Oda bulunamadi\"}");
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.Unavailable));
            Assert.That(_app.Status, Is.EqualTo("Rövanş yapılamaz."));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
        }

        [Test]
        public void ClosedFinishedRoomMakesRematchUnavailable()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer();
            _transport.Receive("game_ended", "{\"reason\":\"timeout\"}");
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.Unavailable));
            Assert.That(_app.Status, Is.EqualTo("Oda kapandı, rövanş yapılamaz."));
            Assert.That(_app.CanRequestRematch, Is.False);
        }

        [Test]
        public void RematchGameStartSwapsSeatsAndResetsGame()
        {
            LoginAsAli();
            StartOnlineGameAsP1();
            _app.HandleColumnClick(3);
            _transport.Receive("game_over", ServerMessages.GameOver(1, "forfeit", "timeout", eloP1: 15, eloP2: -15, ratingP1: 1352, ratingP2: 1235));
            Assert.That(_app.LastEloChange, Is.EqualTo(15));
            Assert.That(_app.ResultHeadline, Is.Not.Null);
            _app.RequestRematch();

            _transport.Receive("game_start", ServerMessages.RematchStart(Board.Player2, "veli", 1235, "Ali", 1352, 30, 30));
            _transport.Receive("rematch_started", ServerMessages.RematchStarted("veli", "Ali", 30, 30));

            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.MyPiece, Is.EqualTo(Board.Player2), "koltuklar yer degistirir");
            Assert.That(_app.HumanPiece, Is.EqualTo(Board.Player2));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(_app.Game.GameOver, Is.False);
            Assert.That(_app.ResultHeadline, Is.Null);
            Assert.That(_app.LastEloChange, Is.Null);
            Assert.That(_app.Summary, Is.Null);
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.None));
            Assert.That(_app.CanRequestRematch, Is.False);
            Assert.That(_app.UserElo, Is.EqualTo(1352));
            Assert.That(_app.OpponentElo, Is.EqualTo(1235));
            Assert.That(_app.Status, Is.EqualTo("Rövanş başladı! Rakibin sırası."));
            Assert.That(_app.CanHumanMove(), Is.False);
            Assert.That(_app.PlayerLabels(), Is.EqualTo(("veli", (int?)1235, "Ali", (int?)1352)));

            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            Assert.That(_app.Status, Is.EqualTo("Senin sıran!"));
            _app.HandleColumnClick(4);
            var moves = _transport.EmittedOf("make_move");
            Assert.That(moves[moves.Count - 1].GetInt("player_piece"), Is.EqualTo(Board.Player2), "hamle yeni tasla gider");

            // Yeni oyunda kopma: yeni koltuga geri katilinir (anahtar koltukla tasinir)
            _transport.RaiseDisconnected("transport close");
            Assert.That(_app.Offline, Is.True);
            _transport.RaiseConnected();
            var joins = _transport.EmittedOf("join_game");
            Assert.That(joins.Count, Is.EqualTo(1));
            Assert.That(joins[0].GetString("rejoin_token"), Is.EqualTo("seat-1"));
            Assert.That(joins[0].GetString("token"), Is.EqualTo("tok-1"));
        }

        [Test]
        public void SecondGameCanAlsoEndInRematch()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer();
            _app.RequestRematch();
            _transport.Receive("game_start", ServerMessages.RematchStart(Board.Player2, "veli", 1250, _app.Username, 1200));
            FinishOnNewServer(2);
            Assert.That(_app.Status, Is.EqualTo("Rakibin süresi doldu, kazandın!"));
            Assert.That(_app.CanRequestRematch, Is.True);
            _app.RequestRematch();
            Assert.That(_transport.EmittedOf("rematch_request").Count, Is.EqualTo(2));
        }

        [Test]
        public void RematchIsOfferedAfterBoardWinOnceTheLastDiscLands()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            int[] moves = Fixtures.P1VerticalWin;
            for (int i = 0; i < moves.Length - 1; i++)
            {
                if (i % 2 == 0)
                    _transport.Receive("move_made", ServerMessages.MoveMade(moves[..(i + 1)]));
                else
                    _app.HandleColumnClick(moves[i]);
            }
            System.Action finish = null;
            _app.AnimateDrop = (col, row, piece, done) => finish = done;
            _transport.Receive("move_made", ServerMessages.MoveMade(moves));
            FinishOnNewServer(1, "normal", null);
            // Son tas dusmeden gelen teklif kaybolmaz
            _transport.Receive("rematch_offered", Offer(Board.Player1));
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.OfferedByOpponent));
            Assert.That(_app.CanRequestRematch, Is.False, "buton son tas dusunce gorunur");
            finish();
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.Status, Is.EqualTo("Rakip rövanş istiyor!"));
            Assert.That(_app.CanRequestRematch, Is.True);
            Assert.That(_app.RematchLabel, Is.EqualTo("Rövanşı Kabul Et"));
        }

        [Test]
        public void SpectatorFollowsRematchStarted()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            _transport.Receive("game_over", ServerMessages.GameOver(1, "forfeit", "timeout"));
            Assert.That(_app.ResultHeadline, Is.Not.Null);
            _transport.Receive("rematch_offered", Offer(Board.Player1));
            Assert.That(_app.Status, Is.EqualTo("Kırmızı kazandı! (süre doldu)"), "seyirci teklifleri gormez");

            _transport.Receive("rematch_started", ServerMessages.RematchStarted("veli", "ali", 30, 30));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Spectating));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(_app.Game.GameOver, Is.False);
            Assert.That(_app.ResultHeadline, Is.Null);
            Assert.That(_app.SpectateNames, Is.EqualTo(("veli", 1250, "ali", 1300)));
            Assert.That(_app.Status, Is.EqualTo("Rövanş başladı! Canlı izleniyor"));
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(30));

            _transport.Receive("move_made", ServerMessages.MoveMade(2));
            Assert.That(_app.Game.MoveCount, Is.EqualTo(1));

            // Yeni oyun da canli: kopunca yayina geri katilinir
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game").Count, Is.EqualTo(2));
        }

        // ---------------------------------------------------------------------
        // Hamle suresi
        // ---------------------------------------------------------------------

        [Test]
        public void TurnClockCountsDownFromServerValue()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            Time.unscaledTime = 100f;
            _transport.Receive("game_start", Timed(StartVsVeli, 30));

            Assert.That(_app.MoveTimeSeconds, Is.EqualTo(30));
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(30));
            Assert.That(_app.TurnClockWarning, Is.False);
            Time.unscaledTime = 104.2f;
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(26));
            Time.unscaledTime = 120.5f;
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(10));
            Assert.That(_app.TurnClockWarning, Is.True, "kendi siramda son 10 sn");
            Time.unscaledTime = 200f;
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(0), "sifirin altina inmez");
        }

        [Test]
        public void ClockIsHiddenWithoutServerFieldsAndInAIGames()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();   // eski sunucu: alan yok
            Assert.That(_app.TurnSecondsLeft, Is.Null);
            Assert.That(_app.MoveTimeSeconds, Is.EqualTo(0));
            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            Assert.That(_app.TurnSecondsLeft, Is.Null);

            _app.ResetToMenu();
            _app.StartAIGame(1);
            Assert.That(_app.TurnSecondsLeft, Is.Null);
            Assert.That(_app.TurnClockWarning, Is.False);
        }

        [Test]
        public void MoveMadeRestartsClockForOpponentWithoutWarning()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.HandleColumnClick(3);
            Time.unscaledTime = 50f;
            _transport.Receive("move_made", ServerMessages.MoveMadeTimed(5, 30, 3));
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(5));
            Assert.That(_app.TurnClockWarning, Is.False, "uyari yalnizca kendi siramda");

            _transport.Receive("move_made", ServerMessages.MoveMadeTimed(30, 30, 3, 4));
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(30));
            Time.unscaledTime = 71f;
            Assert.That(_app.TurnClockWarning, Is.True);

            // Eski olay saati geri almaz
            _transport.Receive("move_made", ServerMessages.MoveMadeTimed(2, 30, 3));
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(9));
        }

        [Test]
        public void ClockStopsOnNullAndAtGameOver()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            _transport.Receive("move_made", ServerMessages.MoveMadeTimed(30, 30, 3));
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(30));
            _transport.Receive("move_made", ServerMessages.MoveMadeTimed(null, 30, 3, 4));
            Assert.That(_app.TurnSecondsLeft, Is.Null);

            _transport.Receive("move_made", ServerMessages.MoveMadeTimed(30, 30, 3, 4, 3));
            FinishOnNewServer(2, "forfeit", "timeout");
            Assert.That(_app.TurnSecondsLeft, Is.Null);
        }

        [Test]
        public void OpponentDisconnectPausesMyClockAndReturnRestartsIt()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            _transport.Receive("game_start", Timed(StartVsVeli, 30));
            Time.unscaledTime = 12f;
            _transport.Receive("opponent_disconnected", "{\"grace_seconds\":30}");
            Assert.That(_app.TurnSecondsLeft, Is.Null, "sunucu bekleyen oyuncunun saatini durdurur");

            Time.unscaledTime = 20f;
            _transport.Receive("opponent_reconnected", "{}");
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(30), "rakip donunce sure bastan baslar");
        }

        [Test]
        public void OpponentDisconnectOnTheirTurnKeepsTheirClock()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            _transport.Receive("game_start", Timed(StartVsAli, 30));
            _transport.Receive("opponent_disconnected", "{\"grace_seconds\":30}");
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(30));
            _transport.Receive("opponent_reconnected", "{}");
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(30));
        }

        [Test]
        public void OwnConnectionLossHidesClockAndRejoinRestoresIt()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            _transport.Receive("game_start", Timed(StartVsVeli, 30));
            _transport.RaiseDisconnected("transport close");
            Assert.That(_app.TurnSecondsLeft, Is.Null);

            _transport.RaiseConnected();
            _transport.Receive("game_joined", Timed(RejoinedAsP1(new GameState()), 17));
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(17));
            Assert.That(_app.MoveTimeSeconds, Is.EqualTo(30));
        }

        [Test]
        public void SpectatorSeesClockWithoutWarning()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", Timed(SpectatorJoined(GameState.FromMoves(new[] { 3 })), 4));
            Assert.That(_app.TurnSecondsLeft, Is.EqualTo(4));
            Assert.That(_app.TurnClockWarning, Is.False);
            _transport.Receive("opponent_disconnected", "{\"grace_seconds\":30}");
            Assert.That(_app.TurnSecondsLeft, Is.Null);
        }

        // ---------------------------------------------------------------------
        // game_over.detail
        // ---------------------------------------------------------------------

        [TestCase(1, "timeout", "Rakibin süresi doldu, kazandın!", StatusTone.Good)]
        [TestCase(2, "timeout", "Süre doldu, hükmen kaybettin.", StatusTone.Bad)]
        [TestCase(1, "disconnect", "Rakibin bağlantısı koptu, hükmen kazandın!", StatusTone.Good)]
        [TestCase(2, "disconnect", "Bağlantın koptuğu için hükmen kaybettin.", StatusTone.Bad)]
        [TestCase(1, "leave", "Rakip oyunu terk etti - Kazandın!", StatusTone.Good)]
        [TestCase(2, "leave", "Oyunu terk ettin, hükmen kaybettin.", StatusTone.Bad)]
        [TestCase(1, null, "Rakip oyunu terk etti - Kazandın!", StatusTone.Good)]
        [TestCase(2, null, "Hükmen kaybettin.", StatusTone.Bad)]
        public void ForfeitDetailTexts(int winner, string detail, string expected, StatusTone tone)
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer(winner, "forfeit", detail);
            Assert.That(_app.Status, Is.EqualTo(expected));
            Assert.That(_app.Tone, Is.EqualTo(tone));
            Assert.That(_app.Game.Winner, Is.EqualTo(winner));
        }

        [Test]
        public void TimeoutLossShowsEloToo()
        {
            LoginAsAli();
            StartOnlineGameAsP2();
            _transport.Receive("game_over",
                ServerMessages.GameOver(1, "forfeit", "timeout", eloP1: 14, eloP2: -14, ratingP1: 1314, ratingP2: 1323));
            Assert.That(_app.Status, Is.EqualTo("Süre doldu, hükmen kaybettin.  ELO -14 (1323)"));
        }

        [TestCase("timeout", "Sarı kazandı! (süre doldu)")]
        [TestCase("disconnect", "Sarı kazandı! (bağlantı koptu)")]
        [TestCase("leave", "Sarı kazandı! (oyun terk edildi)")]
        [TestCase(null, "Sarı kazandı! (hükmen)")]
        public void SpectatorForfeitDetailTexts(string detail, string expected)
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            FinishOnNewServer(2, "forfeit", detail);
            Assert.That(_app.Status, Is.EqualTo(expected));
        }

        // ---------------------------------------------------------------------
        // game_joined.result: yokken biten oyun
        // ---------------------------------------------------------------------

        private static string RejoinedWithResult(GameState state, Dictionary<string, object> result)
        {
            return ServerMessages.WithFields(RejoinedAsP1(state), new Dictionary<string, object>
            {
                ["result"] = result,
                ["game_no"] = 1,
                ["move_time"] = 30,
                ["turn_seconds_left"] = null,
            });
        }

        [Test]
        public void RejoinedFinishedGameUsesServerResultAndElo()
        {
            LoginAsAli();
            StartOnlineGameAsP1();
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();

            var state = GameState.FromMoves(new[] { 3, 4 });
            state.GameOver = true;
            state.Winner = Board.Player2;
            _transport.Receive("game_joined", RejoinedWithResult(state,
                ServerMessages.GameOverFields(2, "forfeit", "timeout", eloP1: -14, eloP2: 14, ratingP1: 1323, ratingP2: 1264)));

            // Tahtadan cikarilan eski metin "Baglantin koptugu icin..." olurdu
            Assert.That(_app.Status, Is.EqualTo("Süre doldu, hükmen kaybettin.  ELO -14 (1323)"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.LastEloChange, Is.EqualTo(-14));
            Assert.That(_app.UserElo, Is.EqualTo(1323));
            Assert.That(_app.ResultHeadline, Is.EqualTo(((string, StatusTone)?)("KAYBETTİN", StatusTone.Bad)));
            Assert.That(_app.TurnSecondsLeft, Is.Null);
            Assert.That(_app.CanRequestRematch, Is.True, "yeni sunucu: rovans istenebilir");
        }

        [Test]
        public void RejoinedResultWinsOverBoardInference()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            var state = GameState.FromMoves(new[] { 3, 4 });
            state.GameOver = true;
            state.Winner = Board.Player1;
            _transport.Receive("game_joined", RejoinedWithResult(state, ServerMessages.GameOverFields(1, "forfeit", "disconnect")));
            Assert.That(_app.Status, Is.EqualTo("Rakibin bağlantısı koptu, hükmen kazandın!"));
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.Unavailable), "rakip yok");
        }

        [Test]
        public void SpectatorRejoinOfFinishedGameUsesServerResult()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();

            var state = GameState.FromMoves(new[] { 3, 4 });
            state.GameOver = true;
            state.Winner = Board.Player2;
            string joined = ServerMessages.WithFields(SpectatorJoined(state), new Dictionary<string, object>
            {
                ["result"] = ServerMessages.GameOverFields(2, "forfeit", "leave"),
            });
            _transport.Receive("game_joined", joined);
            Assert.That(_app.Status, Is.EqualTo("Sarı kazandı! (oyun terk edildi)"));
        }
    }
}
