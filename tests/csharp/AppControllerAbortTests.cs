// Hizli macta ilk hamle gelmedi: sunucu game_over reason 'aborted' gonderir (kazanan yok,
// ELO degismez). Istemci puansiz iptal mesajini gosterir, rovans dugmesi cikmaz, lobiye donulebilir.
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using NUnit.Framework;

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
    }
}
