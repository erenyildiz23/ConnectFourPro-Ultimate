// Hizli macta ilk hamle gelmedi: sunucu game_over reason 'aborted' gonderir (kazanan yok,
// ELO degismez). Istemci puansiz iptal mesajini gosterir, rovans dugmesi cikmaz, lobiye donulebilir.
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using NUnit.Framework;
using UnityEngine;

namespace ConnectFourPro.Tests
{
    public partial class AppControllerTests
    {
        private void ReceiveAborted() =>
            _transport.Receive("game_over", ServerMessages.GameOver(null, "aborted", "first_move"));

        [Test]
        public void AbortedGameShowsUnratedMessageForPlayer()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            ReceiveAborted();
            Assert.That(_app.Game.GameOver, Is.True, "tahta kilitlenir");
            Assert.That(_app.Game.Winner, Is.EqualTo(0));
            Assert.That(_app.Status, Is.EqualTo("Oyun iptal edildi (puansız)"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Neutral));
            Assert.That(_app.ResultHeadline.Value.text, Is.EqualTo("İPTAL EDİLDİ"));
            Assert.That(_app.LastEloChange, Is.Null);
            Assert.That(_app.CanRequestRematch, Is.False, "iptal edilen oyunda rovans yok");
            Assert.That(_app.BackLabel, Is.EqualTo("Lobiye Dön"));
        }

        [Test]
        public void AbortedGameShowsUnratedMessageForSecondPlayer()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            ReceiveAborted();
            Assert.That(_app.Status, Is.EqualTo("Oyun iptal edildi (puansız)"));
            Assert.That(_app.CanRequestRematch, Is.False);
        }

        [Test]
        public void AbortedGameShowsUnratedMessageForSpectator()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new int[0])));
            ReceiveAborted();
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.Status, Is.EqualTo("Oyun iptal edildi (puansız)"));
            Assert.That(_app.ResultHeadline.Value.text, Is.EqualTo("İPTAL EDİLDİ"));
        }

        [Test]
        public void AbortedMessageIsTranslated()
        {
            Assert.That(Loc.T("Oyun iptal edildi (puansız)", Lang.En), Is.EqualTo("Game aborted (unrated)"));
            Assert.That(Loc.T("İPTAL EDİLDİ", Lang.En), Is.EqualTo("ABORTED"));
        }

        [Test]
        public void ReturningToLobbyAfterAbortIsAllowed()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            ReceiveAborted();
            _app.RequestBack();
            Assert.That(_app.Screen, Is.Not.EqualTo(AppScreen.PlayingOnline));
        }

        private const string MoverText = "Rakibin bağlantısı koptu. Hamleni yapabilirsin; yapmazsan oyun iptal edilir (puansız).";
        private const string WaiterText = "Rakibin bağlantısı koptu. Dönüp ilk hamleyi yapmazsa oyun iptal edilir (puansız).";

        [Test]
        public void FirstMoverIsToldToMoveWhenOpponentDrops()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Time.unscaledTime = 10f;
            _transport.Receive("opponent_disconnected", "{\"grace_seconds\":30,\"first_move_pending\":true}");
            Assert.That(_app.Status, Is.EqualTo(MoverText));
            Time.unscaledTime = 22.5f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo(MoverText), "geri sayim galibiyet vaat etmez");
        }

        [Test]
        public void WaitingPlayerIsToldGameWillBeAborted()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            Time.unscaledTime = 10f;
            _transport.Receive("opponent_disconnected", "{\"grace_seconds\":30,\"first_move_pending\":true}");
            Assert.That(_app.Status, Is.EqualTo(WaiterText));
            Time.unscaledTime = 15.5f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo(WaiterText));
        }

        [Test]
        public void AfterFirstMoveCountdownPromisesWinAgain()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Time.unscaledTime = 10f;
            _transport.Receive("opponent_disconnected", "{\"grace_seconds\":30,\"first_move_pending\":true}");
            _app.HandleColumnClick(3);   // ilk hamle: pencere kapanir
            Time.unscaledTime = 20.5f;
            _app.Tick();
            Assert.That(_app.Status, Is.EqualTo("Rakibin bağlantısı koptu! 20 sn içinde dönmezse kazanırsın."));
        }

        [Test]
        public void FirstMoveWindowTextsAreTranslated()
        {
            Assert.That(Loc.T(MoverText, Lang.En), Is.EqualTo("Opponent disconnected. You can still move; if you don't, the game is aborted (unrated)."));
            Assert.That(Loc.T(WaiterText, Lang.En), Is.EqualTo("Opponent disconnected. If they don't return and make the first move, the game is aborted (unrated)."));
        }

        [Test]
        public void LateFirstMoveGhostDiscIsRemovedOnAbort()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.HandleColumnClick(3);   // iyimser yerel tas; sunucu pencere dolmus diye iptal eder
            Assert.That(_app.Game.MoveCount, Is.EqualTo(1));
            ReceiveAborted();
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0), "sunucunun kaydetmedigi tas tahtada kalmaz");
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.IsAborted, Is.True);
            Assert.That(_app.ResultHeadline.Value.text, Is.EqualTo("İPTAL EDİLDİ"));
        }
    }
}
