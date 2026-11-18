// Hizli eslesme (Game/AppController.cs): kuyruga girme, arama ekrani, iptal, eslesme,
// baglanti hatasi ve sunucunun kendiliginden gonderdigi quick_match_cancelled.
// Eski sunucu quick_match_join'e hic cevap vermez; kullanici yine de iptal edebilmelidir.
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public partial class AppControllerTests
    {
        private const string QuickJoinedAsP2 =
            "{\"room_id\":\"QM123\",\"player_piece\":2,\"role\":\"player\"," +
            "\"opponent_info\":{\"username\":\"veli\",\"rating\":1250},\"rejoin_token\":\"seat-q\",\"quick\":true}";
        private const string QuickStart =
            "{\"msg\":\"Oyun Basladi!\",\"opponent_name\":\"veli\",\"opponent_elo\":1250}";

        [Test]
        public void QuickMatchEmitsJoinWithIdentity()
        {
            LoginAsAli();
            _app.StartQuickMatch();
            Assert.That(_transport.ConnectUrls.Count, Is.EqualTo(1));
            _transport.RaiseConnected();

            var sent = _transport.EmittedOf("quick_match_join");
            Assert.That(sent.Count, Is.EqualTo(1));
            Assert.That(sent[0].GetString("user_id"), Is.EqualTo("Ali"));
            Assert.That(sent[0].GetString("token"), Is.EqualTo("tok-1"));

            _app.StartQuickMatch();
            Assert.That(_transport.EmittedOf("quick_match_join").Count, Is.EqualTo(1), "cift tiklama ikinci istegi gondermez");
        }

        [Test]
        public void QuickMatchWaitingShowsSearchingScreen()
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Waiting));
            Assert.That(_app.QuickMatchSearching, Is.True);
            Assert.That(_app.RoomId, Is.Null, "aranirken oda kodu yok");
            Assert.That(_app.Status, Is.EqualTo("Rakip aranıyor..."));

            _transport.RaiseConnected();
            _transport.Receive("quick_match_waiting", "{}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Waiting));
            Assert.That(_app.QuickMatchSearching, Is.True);
            Assert.That(_app.Status, Is.EqualTo("Rakip aranıyor..."));
        }

        [Test]
        public void CancelEmitsCancelAndReturnsToMenu()
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            _transport.RaiseConnected();
            _transport.Receive("quick_match_waiting", "{}");

            _app.CancelQuickMatch();
            Assert.That(_transport.EmittedOf("quick_match_cancel").Count, Is.EqualTo(1));
            Assert.That(_transport.EmittedOf("leave_game"), Is.Empty, "odasi olmayan arama leave_game gondermez");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.QuickMatchSearching, Is.False);
            Assert.That(_app.Status, Is.EqualTo(""));

            // Sunucunun gec gelen cevabi eski sokete gelir, yeni durumu bozmaz
            _transport.Receive("quick_match_cancelled", "{}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.Status, Is.EqualTo(""));
        }

        [Test]
        public void BackOnSearchingScreenCancelsToMenu()
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            _transport.RaiseConnected();
            _app.RequestBack();
            Assert.That(_transport.EmittedOf("quick_match_cancel").Count, Is.EqualTo(1));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu), "hizli mac menuden baslar, menuye doner");
        }

        [Test]
        public void OldServerNeverAnswersButCancelStillWorks()
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            _transport.RaiseConnected();   // eski sunucu quick_match_join'i bilmez: cevap yok
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Waiting));
            _app.CancelQuickMatch();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.QuickMatchSearching, Is.False);

            _app.StartQuickMatch();
            Assert.That(_app.QuickMatchSearching, Is.True, "iptalden sonra tekrar aranabilir");
        }

        [Test]
        public void CancelBeforeConnectSendsNothing()
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            Assert.That(_transport.ConnectUrls.Count, Is.EqualTo(1));
            _app.CancelQuickMatch();
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("quick_match_join"), Is.Empty);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
        }

        [Test]
        public void MatchedGameJoinedStartsOnlineGame()
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            _transport.RaiseConnected();
            _transport.Receive("quick_match_waiting", "{}");
            _transport.Receive("game_joined", QuickJoinedAsP2);
            _transport.Receive("game_start", QuickStart);

            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.QuickMatchSearching, Is.False);
            Assert.That(_app.MyPiece, Is.EqualTo(Board.Player2));
            Assert.That(_app.RoomId, Is.EqualTo("QM123"));
            Assert.That(_app.OpponentName, Is.EqualTo("veli"));
            Assert.That(_app.IsSpectator, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Oyun başladı! Rakibin sırası."));

            // Hamle gonderilen oda ve tas eslesmeden gelir
            _transport.Receive("move_made", ServerMessages.MoveMade(3));
            _app.HandleColumnClick(2);
            var move = _transport.EmittedOf("make_move")[0];
            Assert.That(move.GetString("room_id"), Is.EqualTo("QM123"));
            Assert.That(move.GetInt("player_piece"), Is.EqualTo(Board.Player2));

            // Koltuk anahtari saklandi: kopup geri baglaninca sunucuya gonderilir
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            var rejoin = _transport.EmittedOf("join_game");
            Assert.That(rejoin.Count, Is.EqualTo(1));
            Assert.That(rejoin[0].GetString("room_id"), Is.EqualTo("QM123"));
            Assert.That(rejoin[0].GetString("rejoin_token"), Is.EqualTo("seat-q"));
        }

        [Test]
        public void ConnectionFailureWhileSearchingReturnsToMenuWithStatus()
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            _transport.RaiseConnectError("timeout");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.QuickMatchSearching, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Sunucuya bağlanılamadı!"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        [Test]
        public void ConnectionLostWhileSearchingReturnsToMenuWithStatus()
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            _transport.RaiseConnected();
            _transport.Receive("quick_match_waiting", "{}");
            _transport.RaiseDisconnected("transport close");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu), "sunucu kopan soketi kuyruktan dusurur");
            Assert.That(_app.QuickMatchSearching, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Bağlantı koptu, arama iptal edildi."));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        [Test]
        public void ServerCancelledSearchReturnsToMenuNeutral()
        {
            LoginAsAli();
            _app.StartQuickMatch();
            _transport.RaiseConnected();
            _transport.Receive("quick_match_waiting", "{}");
            // Ayni kayitli kullanicinin yeni baglantisi bu aramanin yerini aldi
            _transport.Receive("quick_match_cancelled", "{}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.QuickMatchSearching, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Rakip arama sona erdi."));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Neutral));
        }

        [Test]
        public void QuickMatchCancelledOutsideSearchIsIgnored()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("quick_match_cancelled", "{}");
            _transport.Receive("quick_match_waiting", "{}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.QuickMatchSearching, Is.False);
        }

        [TestCase("already_in_game", "Zaten bir oyundasiniz")]
        [TestCase("guest_name_taken", "Bu misafir adi kullanimda")]
        public void ServerErrorWhileSearchingReturnsToMenu(string code, string msg)
        {
            _app.GuestLogin();
            _app.StartQuickMatch();
            _transport.RaiseConnected();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Waiting));
            _transport.Receive("error", "{\"msg\":\"" + msg + "\",\"code\":\"" + code + "\"}");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.QuickMatchSearching, Is.False);
            Assert.That(_app.Status, Is.EqualTo("Hata: " + msg));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        [Test]
        public void NormalRoomWaitingIsNotSearching()
        {
            _app.GuestLogin();
            _app.CreateOnlineGame();
            _transport.RaiseConnected();
            _transport.Receive("game_created", Created);
            Assert.That(_app.QuickMatchSearching, Is.False);
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Lobby), "normal oda beklemesi lobiye doner");
            Assert.That(_transport.EmittedOf("quick_match_cancel"), Is.Empty);
        }
    }
}
