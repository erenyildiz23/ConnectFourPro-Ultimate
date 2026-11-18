// Satranc saati, istemci (Game/AppController.cs): sunucunun _clock_fields alanlari
// (time_control, clock_p1/p2, clock_running, clock_delay) yerelde geri sayilir ve her
// saat tasiyan olayda duzeltilir. Eski sunucu (alan yok) ve suresiz oda: saat yok.
// Rakip kopma/donus olaylari saat alani tasimaz; sunucu kopma sirasinda bekleyen
// oyuncunun saatini durdurdugu icin istemci de kendi sayacini durdurur.
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
        private static Dictionary<string, object> ClockFields(string tc, int? p1, int? p2, int running, int delay = 0,
                                                              int moveTime = 30) =>
            new Dictionary<string, object>
            {
                ["move_time"] = moveTime, ["turn_seconds_left"] = null,
                ["time_control"] = tc, ["clock_p1"] = p1, ["clock_p2"] = p2,
                ["clock_running"] = running, ["clock_delay"] = delay,
            };

        private static string Clocked(string json, int p1, int p2, int running, int delay = 0) =>
            ServerMessages.WithFields(json, ClockFields("3+2", p1, p2, running, delay));

        /// <summary>3+2 odasi kurar, rakip katilir: P1 olarak, saat (payi bitmis) P1'de isliyor.</summary>
        private void StartTimedGameAsP1(float at = 100f, int delay = 0)
        {
            _app.CreateOnlineGame("3+2");
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            Time.unscaledTime = at;
            _transport.Receive("game_start", Clocked(StartVsVeli, 180, 180, Board.Player1, delay));
        }

        [Test]
        public void OldServerHasNoClock()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();   // eski sunucu: saat alani yok
            Assert.That(_app.TimeControl, Is.Null);
            Assert.That(_app.ClockSeconds(Board.Player1), Is.Null);
            Assert.That(_app.ClockSeconds(Board.Player2), Is.Null);
            Assert.That(_app.ClockWarning(Board.Player1), Is.False);
            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            Assert.That(_app.ClockSeconds(Board.Player1), Is.Null);
        }

        [Test]
        public void UntimedRoomOnNewServerHasNoClock()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            _transport.Receive("game_start", ServerMessages.WithFields(StartVsVeli, ClockFields(null, null, null, 0)));
            Assert.That(_app.TimeControl, Is.Null);
            Assert.That(_app.ClockSeconds(Board.Player1), Is.Null);
        }

        [Test]
        public void RunningClockCountsDownLocally()
        {
            _app.GuestLogin();
            StartTimedGameAsP1();
            Assert.That(_app.TimeControl, Is.EqualTo("3+2"));
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(180));
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(180));
            Time.unscaledTime = 102f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(178));
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(180), "sirasi gelmeyenin saati sabit");
            Assert.That(_app.ClockTicking(Board.Player1), Is.True);
            Assert.That(_app.ClockTicking(Board.Player2), Is.False);
            Time.unscaledTime = 1000f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(0), "sifirin altina inmez");
        }

        [Test]
        public void StartDelayHoldsTheCountdown()
        {
            _app.GuestLogin();
            StartTimedGameAsP1(100f, delay: 5);
            Time.unscaledTime = 104.5f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(180), "baslangic payinda saat islemez");
            Assert.That(_app.ClockTicking(Board.Player1), Is.False);
            Time.unscaledTime = 107f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(178));
        }

        [Test]
        public void MoveMadeResyncsClocks()
        {
            _app.GuestLogin();
            StartTimedGameAsP1();
            Time.unscaledTime = 104f;
            _transport.Receive("move_made", Clocked(ServerMessages.MoveMade(3), 178, 180, Board.Player2));
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(178), "sunucunun degeri (ek sure dahil) alinir");
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(180));
            Time.unscaledTime = 107f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(178), "hamle yapanin saati durdu");
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(177), "rakibin saati isliyor");

            // Eski (gecikmis) olay saati geri almaz
            _transport.Receive("move_made", Clocked(ServerMessages.MoveMade(3, 2), 178, 175, Board.Player1));
            _transport.Receive("move_made", Clocked(ServerMessages.MoveMade(3), 150, 150, Board.Player2));
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(175));
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(178));
        }

        [Test]
        public void WarningUnder10Seconds()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame("3+2");
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            Time.unscaledTime = 50f;
            _transport.Receive("game_start", Clocked(StartVsVeli, 10, 9, Board.Player1));
            Assert.That(_app.ClockWarning(Board.Player1), Is.False, "10 sn henuz uyari degil");
            Assert.That(_app.ClockWarning(Board.Player2), Is.True, "rakibin saati de 10'un altinda kirmizi");
            Time.unscaledTime = 51f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(9));
            Assert.That(_app.ClockWarning(Board.Player1), Is.True);
        }

        [Test]
        public void CreateTimedRoomSendsTimeControl()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame("3+2");
            _transport.RaiseConnected();
            var sent = _transport.EmittedOf("create_game");
            Assert.That(sent.Count, Is.EqualTo(1));
            Assert.That(sent[0].GetString("time_control"), Is.EqualTo("3+2"));

            _app.ResetToMenu();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            sent = _transport.EmittedOf("create_game");
            Assert.That(sent.Count, Is.EqualTo(2));
            Assert.That(sent[1].Has("time_control"), Is.False, "suresiz oda eski yuku gonderir");
        }

        [Test]
        public void LobbyTimeControlChoiceToggles()
        {
            Assert.That(_app.LobbyTimeControl, Is.Null, "varsayilan suresiz");
            _app.ToggleLobbyTimeControl();
            Assert.That(_app.LobbyTimeControl, Is.EqualTo("3+2"));
            Assert.That(_app.LobbyTimeControlLabel, Is.EqualTo("3+2"));
            _app.ToggleLobbyTimeControl();
            Assert.That(_app.LobbyTimeControl, Is.Null);
            Assert.That(_app.LobbyTimeControlLabel, Is.EqualTo("Süresiz"));
        }

        [Test]
        public void OpponentDisconnectPausesMyClockUntilReconnect()
        {
            _app.GuestLogin();
            StartTimedGameAsP1();
            Time.unscaledTime = 103f;
            _transport.Receive("opponent_disconnected", "{\"msg\":\"Rakip ayrildi\",\"grace_seconds\":30}");
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(177));
            Time.unscaledTime = 120f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(177), "sunucu bekleyen oyuncunun saatini durdurur");
            Assert.That(_app.ClockTicking(Board.Player1), Is.False);

            _transport.Receive("opponent_reconnected", "{\"msg\":\"Rakip geri dondu\"}");
            Time.unscaledTime = 122f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(175), "rakip donunce saat kaldigi yerden isler");
            Assert.That(_app.TurnSecondsLeft, Is.Null, "sureli odada hamle basina sayac acilmaz");
        }

        [Test]
        public void OpponentDisconnectOnTheirTurnKeepsTheirClockRunning()
        {
            _app.GuestLogin();
            StartTimedGameAsP1();
            _transport.Receive("move_made", Clocked(ServerMessages.MoveMade(3), 182, 180, Board.Player2));
            Time.unscaledTime = 101f;
            _transport.Receive("opponent_disconnected", "{\"msg\":\"Rakip ayrildi\",\"grace_seconds\":30}");
            Time.unscaledTime = 110f;
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(170), "kopan sirasi gelenin saati isler");
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(182));
        }

        [Test]
        public void OwnConnectionLossFreezesOpponentClockUntilRejoin()
        {
            _app.GuestLogin();
            StartTimedGameAsP1();
            _transport.Receive("move_made", Clocked(ServerMessages.MoveMade(3), 182, 180, Board.Player2));
            Time.unscaledTime = 104f;
            _transport.RaiseDisconnected("transport close");
            Time.unscaledTime = 115f;
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(176), "biz kopunca sunucu rakibin saatini durdurur");

            _transport.RaiseConnected();
            var rejoined = ServerMessages.WithFields(
                "{\"room_id\":\"AB12C\",\"player_piece\":1,\"role\":\"player\",\"rejoined\":true," +
                "\"opponent_info\":{\"username\":\"veli\",\"rating\":1250},\"rejoin_token\":\"seat-1\"}",
                ClockFields("3+2", 182, 175, Board.Player2));
            var d = (Dictionary<string, object>)Json.Parse(rejoined);
            d["current_state"] = Json.Parse(ServerMessages.Snapshot(GameState.FromMoves(new[] { 3 })));
            _transport.Receive("game_joined", Json.Serialize(d));
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(175), "geri donuste sunucu degeri");
            Time.unscaledTime = 117f;
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(173));
        }

        [Test]
        public void GameOverFreezesClocks()
        {
            _app.GuestLogin();
            StartTimedGameAsP1();
            Time.unscaledTime = 110f;
            _transport.Receive("game_over", ServerMessages.GameOver(Board.Player2, "forfeit", "timeout"));
            Assert.That(_app.Status, Is.EqualTo("Süre doldu, hükmen kaybettin."));
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(170));
            Time.unscaledTime = 150f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(170), "biten oyunun saati donar");
            Assert.That(_app.ClockTicking(Board.Player1), Is.False);
        }

        [Test]
        public void RematchResetsClocksAndLeavingClearsThem()
        {
            _app.GuestLogin();
            StartTimedGameAsP1();
            _transport.Receive("move_made", Clocked(ServerMessages.MoveMade(3), 150, 120, Board.Player2));
            _transport.Receive("game_over", ServerMessages.GameOver(Board.Player1, "forfeit", "leave"));
            Time.unscaledTime = 200f;
            var start = ServerMessages.RematchStart(Board.Player2, "veli", 1250, "Misafir", 1200);
            _transport.Receive("game_start", ServerMessages.WithFields(start, ClockFields("3+2", 180, 180, Board.Player1, 5)));
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(180));
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(180));

            _app.ResetToMenu();
            Assert.That(_app.TimeControl, Is.Null);
            Assert.That(_app.ClockSeconds(Board.Player1), Is.Null);
            _app.StartAIGame(1);
            Assert.That(_app.ClockSeconds(Board.Player1), Is.Null, "AI oyununda saat yok");
        }

        [Test]
        public void SpectatorSeesBothClocks()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            Time.unscaledTime = 10f;
            var joined = (Dictionary<string, object>)Json.Parse(SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            foreach (var kv in ClockFields("3+2", 170, 160, Board.Player2))
                joined[kv.Key] = kv.Value;
            _transport.Receive("game_joined", Json.Serialize(joined));
            Time.unscaledTime = 15f;
            Assert.That(_app.ClockSeconds(Board.Player1), Is.EqualTo(170));
            Assert.That(_app.ClockSeconds(Board.Player2), Is.EqualTo(155));
        }
    }
}
