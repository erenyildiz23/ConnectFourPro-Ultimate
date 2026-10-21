// SocketIOClient'in gercek Flask-SocketIO sunucusuyla (src/server.py) uctan uca testi.
// Sunucu gerektirdigi icin istege baglidir:
//   CONNECT4_TEST_SERVER=http://localhost:5000 dotnet test tests/csharp
using System;
using System.Collections.Concurrent;
using System.Threading;
using ConnectFourPro.Net;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    [Category("Integration")]
    public class SocketIOIntegrationTests
    {
        private sealed class Client : IDisposable
        {
            public readonly SocketIOClient Socket = new SocketIOClient();
            public readonly BlockingCollection<(string name, JsonObject data)> Events = new BlockingCollection<(string, JsonObject)>();
            public readonly ManualResetEventSlim ConnectedSignal = new ManualResetEventSlim();

            public Client(string url)
            {
                Socket.Connected += () => ConnectedSignal.Set();
                Socket.ConnectError += e => Events.Add(("connect_error", JsonObject.ParseObject("{}")));
                Socket.EventReceived += (n, d) => Events.Add((n, JsonObject.From(Json.Parse(d))));
                Socket.Connect(url);
                Assert.That(ConnectedSignal.Wait(TimeSpan.FromSeconds(5)), "baglanti kurulamadi");
            }

            public JsonObject WaitFor(string name)
            {
                var deadline = DateTime.UtcNow.AddSeconds(5);
                while (DateTime.UtcNow < deadline)
                    if (Events.TryTake(out var e, TimeSpan.FromMilliseconds(100)) && e.name == name)
                        return e.data;
                Assert.Fail("olay gelmedi: " + name);
                return null;
            }

            public void Dispose() => Socket.Dispose();
        }

        private static string ServerUrl()
        {
            string url = Environment.GetEnvironmentVariable("CONNECT4_TEST_SERVER");
            if (string.IsNullOrEmpty(url))
                Assert.Ignore("CONNECT4_TEST_SERVER tanimli degil");
            return url;
        }

        [Test]
        public void FullOnlineGameFlow()
        {
            string url = ServerUrl();
            using var a = new Client(url);
            using var b = new Client(url);

            a.Socket.Emit(SocketEvents.LatencyPing, "{\"t\":42}");
            Assert.That(a.WaitFor(SocketEvents.LatencyPong).GetInt("t"), Is.EqualTo(42));

            a.Socket.Emit(SocketEvents.CreateGame, "{\"user_id\":\"Misafir_100001\"}");
            var created = a.WaitFor(SocketEvents.GameCreated);
            string room = created.GetString("room_id");
            Assert.That(room, Has.Length.EqualTo(5));
            Assert.That(created.GetInt("player_piece"), Is.EqualTo(1));

            b.Socket.Emit(SocketEvents.JoinGame, Json.Serialize(new System.Collections.Generic.Dictionary<string, object>
            {
                ["room_id"] = room, ["user_id"] = "Misafir_100002",
            }));
            Assert.That(b.WaitFor(SocketEvents.GameJoined).GetInt("player_piece"), Is.EqualTo(2));
            Assert.That(a.WaitFor(SocketEvents.GameStart).GetString("opponent_name"), Is.EqualTo("Misafir_100002"));
            b.WaitFor(SocketEvents.GameStart);

            // P1 dikey dortlu yapar
            int[] moves = { 0, 1, 0, 1, 0, 1, 0 };
            for (int i = 0; i < moves.Length; i++)
            {
                var mover = i % 2 == 0 ? a : b;
                mover.Socket.Emit(SocketEvents.MakeMove, $"{{\"room_id\":\"{room}\",\"col\":{moves[i]},\"player_piece\":{i % 2 + 1}}}");
                var made = a.WaitFor(SocketEvents.MoveMade);
                b.WaitFor(SocketEvents.MoveMade);
                var synced = new Core.GameState();
                GameSnapshot.Apply(synced, made);
                Assert.That(synced.MoveCount, Is.EqualTo(i + 1));
            }
            var over = GameOverInfo.From(a.WaitFor(SocketEvents.GameOver));
            Assert.That(over.Winner, Is.EqualTo(1));
            Assert.That(over.Reason, Is.EqualTo("normal"));
        }

        [Test]
        public void ServerErrorIsDelivered()
        {
            using var a = new Client(ServerUrl());
            a.Socket.Emit(SocketEvents.JoinGame, "{\"room_id\":\"ZZZZZ\",\"user_id\":\"Misafir_100003\"}");
            Assert.That(a.WaitFor(SocketEvents.Error).GetString("msg"), Is.EqualTo("Oda bulunamadi"));
        }

        [Test]
        public void DisconnectRaisesEvent()
        {
            using var a = new Client(ServerUrl());
            var gone = new ManualResetEventSlim();
            a.Socket.Disconnected += _ => gone.Set();
            a.Socket.Disconnect();
            Assert.That(gone.Wait(2000) && !a.Socket.IsConnected);
        }
    }
}
