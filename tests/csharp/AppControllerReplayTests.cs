// Mac tekrari (Game/AppController.cs): gecmisten ve biten online oyundan tekrar ekranina
// giris, geri donus ve tekrar sirasinda gelen sunucu olaylari.
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using ConnectFourPro.Net;
using NUnit.Framework;
using UnityEngine;

namespace ConnectFourPro.Tests
{
    public partial class AppControllerTests
    {
        // P1 (kirmizi) 3. sutunda dikey dortlu yapar: 7 hamle
        private static readonly int[] RedWinsColumn3 = { 3, 2, 3, 2, 3, 2, 3 };

        private const string HistoryForReplay =
            "{\"games\":[" +
            "{\"start_time\":\"2026-11-18T10:00:00\",\"moves\":\"[3, 2, 3, 2, 3, 2, 3]\",\"player1\":\"Ali\"," +
            "\"player2\":\"veli\",\"winner\":\"Ali\",\"result\":\"win\",\"end_reason\":\"normal\"}," +
            "{\"start_time\":\"2026-11-17T10:00:00\",\"moves\":\"\",\"player1\":\"veli\"," +
            "\"player2\":\"Ali\",\"winner\":\"veli\",\"result\":\"loss\",\"end_reason\":\"forfeit\"}," +
            "{\"start_time\":\"2026-11-16T10:00:00\",\"moves\":\"[3, 3]\",\"player1\":\"veli\"," +
            "\"player2\":\"Ali\",\"winner\":null,\"result\":\"draw\",\"end_reason\":\"normal\"}," +
            "{\"start_time\":\"2026-11-15T10:00:00\",\"moves\":\"[4]\",\"player1\":\"Ali\"," +
            "\"player2\":\"veli\",\"winner\":\"veli\",\"result\":\"loss\",\"end_reason\":\"forfeit\"}" +
            "]}";

        private void OpenHistoryWithGames()
        {
            LoginAsAli();
            _app.OpenHistory();
            LastCall.Respond(200, HistoryForReplay);
        }

        /// <summary>Misafir P1 olarak online oyunu dikey dortluyle kazanir (yeni sunucu sonucu).</summary>
        private void WinOnlineGameAsP1()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("move_made", ServerMessages.MoveMade(RedWinsColumn3));
            _transport.Receive("game_over", ServerMessages.GameOver(Board.Player1, "normal", "four"));
        }

        [Test]
        public void OpenReplayFromHistoryShowsReplayScreen()
        {
            OpenHistoryWithGames();
            var entry = _app.HistoryData[0];
            _app.OpenReplay(entry);

            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Replay));
            Assert.That(_screens[_screens.Count - 1], Is.EqualTo(AppScreen.Replay));
            Assert.That(_app.Replay, Is.Not.Null);
            Assert.That(_app.Replay.Count, Is.EqualTo(entry.Moves.Count));
            Assert.That(_app.Replay.Index, Is.EqualTo(0), "tekrar bos tahtadan baslar");
            Assert.That(_app.Replay.P1, Is.EqualTo("Ali"));
            Assert.That(_app.Replay.P2, Is.EqualTo("veli"));
            Assert.That(_app.Replay.ResultText, Is.EqualTo("Ali kazandı!"));
            Assert.That(_app.ReplayReturnScreen, Is.EqualTo(AppScreen.History));

            _app.Replay.Last();
            Assert.That(_app.Replay.State.MoveHistory, Is.EqualTo(RedWinsColumn3));
            Assert.That(_app.Replay.State.Winner, Is.EqualTo(Board.Player1));
        }

        [Test]
        public void HistoryReplayResultTextCoversDrawAndForfeit()
        {
            OpenHistoryWithGames();
            _app.OpenReplay(_app.HistoryData[2]);
            Assert.That(_app.Replay.ResultText, Is.EqualTo("Berabere!"));
            Assert.That(_app.Replay.P1, Is.EqualTo("veli"));
            _app.RequestBack();

            _app.OpenReplay(_app.HistoryData[3]);
            Assert.That(_app.Replay.ResultText, Is.EqualTo("veli kazandı! (hükmen)"));
        }

        [Test]
        public void ReplayBackReturnsToHistory()
        {
            OpenHistoryWithGames();
            var data = _app.HistoryData;
            int calls = _api.Calls.Count;
            _app.OpenReplay(data[0]);
            _app.RequestBack();

            Assert.That(_app.Screen, Is.EqualTo(AppScreen.History));
            Assert.That(_app.Replay, Is.Null);
            Assert.That(_app.HistoryData, Is.SameAs(data), "gecmis listesi yeniden istenmez");
            Assert.That(_api.Calls.Count, Is.EqualTo(calls));
        }

        [Test]
        public void ReplayBackReturnsToGameOverScreen()
        {
            WinOnlineGameAsP1();
            string status = _app.Status;
            Assert.That(_app.CanRequestRematch, Is.True);

            _app.OpenReplayOfLastGame();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Replay));
            Assert.That(_app.ReplayReturnScreen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.Replay.Count, Is.EqualTo(RedWinsColumn3.Length));
            Assert.That(_app.Replay.P1, Is.EqualTo(_app.Username), "P1 bizim tasimiz");
            Assert.That(_app.Replay.P2, Is.EqualTo("veli"));
            Assert.That(_app.Replay.ResultText, Is.EqualTo(_app.Username + " kazandı!"));

            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.Replay, Is.Null);
            Assert.That(_app.Game.GameOver, Is.True, "biten oyun yerinde kalir");
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(RedWinsColumn3));
            Assert.That(_app.RoomId, Is.EqualTo("AB12C"));
            Assert.That(_app.CanRequestRematch, Is.True, "oturum kapanmaz, rovans hala istenebilir");
            Assert.That(_app.Status, Is.EqualTo(status));
            Assert.That(_transport.EmittedOf("leave_game"), Is.Empty);
        }

        [Test]
        public void CannotReplayEmptyMoveList()
        {
            OpenHistoryWithGames();
            int changes = _screens.Count;
            _app.OpenReplay(_app.HistoryData[1]);
            Assert.That(_app.HistoryData[1].Moves, Is.Empty);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.History));
            Assert.That(_app.Replay, Is.Null);

            _app.OpenReplay(null);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.History));
            Assert.That(_screens.Count, Is.EqualTo(changes));
        }

        [Test]
        public void CanReplayLastGameOnlyAfterOnlineGameOver()
        {
            _app.GuestLogin();
            Assert.That(_app.CanReplayLastGame, Is.False, "menude");
            StartOnlineGameAsP1();
            Assert.That(_app.CanReplayLastGame, Is.False, "oyun suruyor");
            _transport.Receive("move_made", ServerMessages.MoveMade(3, 2));
            Assert.That(_app.CanReplayLastGame, Is.False, "oyun suruyor");
            _app.OpenReplayOfLastGame();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.Replay, Is.Null);

            _transport.Receive("move_made", ServerMessages.MoveMade(RedWinsColumn3));
            _transport.Receive("game_over", ServerMessages.GameOver(Board.Player1, "normal", "four"));
            Assert.That(_app.CanReplayLastGame, Is.True);

            _app.ResetToMenu();
            Assert.That(_app.CanReplayLastGame, Is.False, "menude son oyun yok");
        }

        [Test]
        public void ForfeitBeforeAnyMoveCannotBeReplayed()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("game_over", ServerMessages.GameOver(Board.Player1, "forfeit", "leave"));
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.CanReplayLastGame, Is.False, "hamlesiz oyunun tekrari yok");
        }

        [Test]
        public void SpectatorCannotReplayLastGame()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined",
                "{\"room_id\":\"AB12C\",\"player_piece\":0,\"role\":\"spectator\",\"current_state\":" +
                ServerMessages.Snapshot(GameState.FromMoves(RedWinsColumn3)) + "," +
                "\"p1_info\":{\"username\":\"ali\",\"rating\":1300},\"p2_info\":{\"username\":\"veli\",\"rating\":1250}}");
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.CanReplayLastGame, Is.False);
        }

        [Test]
        public void ReplayPlaysOnTickWhileOnReplayScreen()
        {
            Time.unscaledTime = 10f;
            OpenHistoryWithGames();
            _app.OpenReplay(_app.HistoryData[0]);
            _app.Replay.TogglePlay();

            Time.unscaledTime = 10.5f;
            _app.Tick();
            Assert.That(_app.Replay.Index, Is.EqualTo(0));
            Time.unscaledTime = 10f + ReplayModel.StepSeconds + 0.01f;
            _app.Tick();
            Assert.That(_app.Replay.Index, Is.EqualTo(1));
            Time.unscaledTime += 3 * ReplayModel.StepSeconds;
            _app.Tick();
            Assert.That(_app.Replay.Index, Is.EqualTo(4));
        }

        [Test]
        public void ReplayTickIgnoresTimeSpentBeforeOpening()
        {
            Time.unscaledTime = 1f;
            OpenHistoryWithGames();
            _app.Tick();
            Time.unscaledTime = 500f;   // gecmis ekraninda uzun bekleme
            _app.OpenReplay(_app.HistoryData[0]);
            _app.Replay.TogglePlay();
            _app.Tick();
            Assert.That(_app.Replay.Index, Is.EqualTo(0));
        }

        [Test]
        public void RematchOfferWhileWatchingReplayIsKept()
        {
            WinOnlineGameAsP1();
            _app.OpenReplayOfLastGame();
            _transport.Receive("rematch_offered", Offer(Board.Player2));
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.OfferedByOpponent));
            Assert.That(_app.Status, Is.EqualTo("Rakip rövanş istiyor!"));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Replay), "teklif tekrari kesmez");

            _app.RequestBack();
            Assert.That(_app.CanRequestRematch, Is.True);
            Assert.That(_app.RematchLabel, Is.EqualTo("Rövanşı Kabul Et"));
        }

        [Test]
        public void RoomClosedWhileWatchingReplayDisablesRematch()
        {
            WinOnlineGameAsP1();
            _app.OpenReplayOfLastGame();
            _transport.Receive("game_ended", "{}");
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.Unavailable));
            _app.RequestBack();
            Assert.That(_app.CanRequestRematch, Is.False);
        }

        [Test]
        public void RematchStartWhileWatchingReplayLeavesReplay()
        {
            WinOnlineGameAsP1();
            _app.OpenReplayOfLastGame();
            _transport.Receive("game_start",
                "{\"opponent_name\":\"veli\",\"opponent_elo\":1250,\"rematch\":true,\"player_piece\":2,\"room_id\":\"AB12C\"}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.Replay, Is.Null);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
        }
    }
}
