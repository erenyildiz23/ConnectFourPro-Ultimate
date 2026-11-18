// Hazir sohbet (Game/AppController.cs, Game/QuickChat.cs): chat_quick gonderimi, yerel 2 sn
// siniri, gelen chat_message'in gonderenin adinin yaninda 3 sn balon olarak gorunmesi.
// Eski sunucu chat_quick'e cevap vermez; gonderim yine de hata vermemelidir.
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using NUnit.Framework;
using UnityEngine;

namespace ConnectFourPro.Tests
{
    public partial class AppControllerTests
    {
        private static string Chat(int fromPiece, int msgId, string roomId = "AB12C") =>
            "{\"room_id\":\"" + roomId + "\",\"from_piece\":" + fromPiece + ",\"msg_id\":" + msgId + "}";

        [Test]
        public void QuickChatHasEightMessagesInSpecOrder()
        {
            Assert.That(QuickChat.Messages, Is.EqualTo(new[]
            {
                "İyi oyun!", "Bol şans!", "Güzel hamle!", "Hay aksi!",
                "Düşünüyorum...", "Teşekkürler!", "Rövanş?", "Selam!",
            }));
        }

        [Test]
        public void SendQuickChatEmitsId()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Assert.That(_app.CanChat, Is.True);

            _app.SendQuickChat(8);
            _app.SendQuickChat(-1);
            Assert.That(_transport.EmittedOf("chat_quick"), Is.Empty, "gecersiz numara gonderilmez");

            _app.SendQuickChat(0);
            var sent = _transport.EmittedOf("chat_quick");
            Assert.That(sent.Count, Is.EqualTo(1));
            Assert.That(sent[0].GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(sent[0].GetInt("msg_id", -1), Is.EqualTo(0));
            Assert.That(_app.ChatBubble, Is.Null, "kendi balonumuz sunucunun yankisiyla gelir");

            // Sunucu odaya (bize de) yayinlar
            _transport.Receive("chat_message", Chat(Board.Player1, 0));
            Assert.That(_app.ChatBubble, Is.EqualTo(((int, int)?)(Board.Player1, 0)));
        }

        [Test]
        public void LocalRateLimitBlocksSecondSendWithin2s()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Time.unscaledTime = 10f;
            _app.SendQuickChat(1);
            Time.unscaledTime = 11.9f;
            _app.SendQuickChat(2);
            Assert.That(_transport.EmittedOf("chat_quick").Count, Is.EqualTo(1), "2 sn dolmadan ikinci mesaj gitmez");
            Time.unscaledTime = 12f;
            _app.SendQuickChat(2);
            var sent = _transport.EmittedOf("chat_quick");
            Assert.That(sent.Count, Is.EqualTo(2));
            Assert.That(sent[1].GetInt("msg_id", -1), Is.EqualTo(2));
        }

        [Test]
        public void IncomingChatShowsBubbleForSender()
        {
            _app.GuestLogin();
            StartOnlineGameAsP2();
            _transport.Receive("chat_message", Chat(Board.Player1, 3));
            Assert.That(_app.ChatBubble, Is.EqualTo(((int, int)?)(Board.Player1, 3)));

            // Yeni mesaj eskisinin yerini alir
            _transport.Receive("chat_message", Chat(Board.Player2, 5));
            Assert.That(_app.ChatBubble, Is.EqualTo(((int, int)?)(Board.Player2, 5)));
        }

        [Test]
        public void BubbleExpiresAfter3s()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Time.unscaledTime = 20f;
            _transport.Receive("chat_message", Chat(Board.Player2, 7));
            Time.unscaledTime = 22.9f;
            _app.Tick();
            Assert.That(_app.ChatBubble, Is.EqualTo(((int, int)?)(Board.Player2, 7)));
            Time.unscaledTime = 23f;
            _app.Tick();
            Assert.That(_app.ChatBubble, Is.Null);
        }

        [Test]
        public void SpectatorHasNoChatButton()
        {
            _app.GuestLogin();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3 })));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Spectating));
            Assert.That(_app.CanChat, Is.False);
            _app.SendQuickChat(0);
            Assert.That(_transport.EmittedOf("chat_quick"), Is.Empty);

            // Seyirci baloncuklari gorur
            _transport.Receive("chat_message", Chat(Board.Player2, 1));
            Assert.That(_app.ChatBubble, Is.EqualTo(((int, int)?)(Board.Player2, 1)));
        }

        [Test]
        public void InvalidIncomingIdIgnored()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _transport.Receive("chat_message", Chat(Board.Player2, 8));
            _transport.Receive("chat_message", Chat(Board.Player2, -1));
            _transport.Receive("chat_message", "{\"room_id\":\"AB12C\",\"from_piece\":2}");
            _transport.Receive("chat_message", "{\"room_id\":\"AB12C\",\"from_piece\":2,\"msg_id\":\"x\"}");
            _transport.Receive("chat_message", Chat(0, 1));
            _transport.Receive("chat_message", Chat(Board.Player2, 1, "XY9Z0"));
            Assert.That(_app.ChatBubble, Is.Null);
        }

        [Test]
        public void ChatWorksAfterGameOverButNotInAIGames()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer();
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.CanChat, Is.True, "Iyi oyun! / Rovans? mesajlari mac bitince de gider");
            _app.SendQuickChat(6);
            Assert.That(_transport.EmittedOf("chat_quick").Count, Is.EqualTo(1));
            _transport.Receive("chat_message", Chat(Board.Player2, 0));
            Assert.That(_app.ChatBubble, Is.Not.Null);

            _app.ResetToMenu();
            Assert.That(_app.CanChat, Is.False);
            Assert.That(_app.ChatBubble, Is.Null, "ekran degisince balon silinir");
            _transport.Receive("chat_message", Chat(Board.Player2, 0));
            Assert.That(_app.ChatBubble, Is.Null, "oyun ekrani disinda gelen mesaj yok sayilir");

            _app.StartAIGame(1);
            Assert.That(_app.CanChat, Is.False);
            _app.SendQuickChat(0);
            Assert.That(_transport.EmittedOf("chat_quick").Count, Is.EqualTo(1));
        }

        [Test]
        public void RematchClearsBubble()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            FinishOnNewServer();
            _transport.Receive("chat_message", Chat(Board.Player2, 6));
            Assert.That(_app.ChatBubble, Is.Not.Null);
            _transport.Receive("game_start", ServerMessages.RematchStart(Board.Player2, "veli", 1250, "Misafir", 1200));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.ChatBubble, Is.Null);
        }
    }
}
