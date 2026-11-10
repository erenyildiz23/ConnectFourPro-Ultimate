// Oda baglantisi (Net/GameSocket.cs): kimlik alanlari, bekleyen istek, yeniden katilma.
using System.Collections.Generic;
using ConnectFourPro.Net;
using NUnit.Framework;
using UnityEngine;

namespace ConnectFourPro.Tests
{
    public class GameSocketTests
    {
        private const string Url = "http://test";
        private FakeTransport _transport;
        private GameSocket _socket;

        [SetUp]
        public void SetUp()
        {
            UnityStubs.Reset();
            _transport = new FakeTransport();
            _socket = new GameSocket(_transport, Url);
        }

        [Test]
        public void CreateGameConnectsFirstThenSendsPendingRequest()
        {
            _socket.CreateGame("ali");
            Assert.That(_transport.ConnectUrls, Is.EqualTo(new[] { Url }));
            Assert.That(_transport.Emitted, Is.Empty);

            _transport.RaiseConnected();
            Assert.That(_transport.Emitted.Count, Is.EqualTo(1));
            Assert.That(_transport.Emitted[0].name, Is.EqualTo("create_game"));
        }

        [Test]
        public void GuestCreatePayloadHasUserIdButNoToken()
        {
            _socket.CreateGame("Misafir_000123");
            _transport.RaiseConnected();
            var data = _transport.EmittedOf("create_game")[0];
            Assert.That(data.GetString("user_id"), Is.EqualTo("Misafir_000123"));
            Assert.That(data.Has("token"), Is.False);
        }

        [Test]
        public void CreatePayloadCarriesToken()
        {
            _socket.CreateGame("ali", "tok-1");
            _transport.RaiseConnected();
            var data = _transport.EmittedOf("create_game")[0];
            Assert.That(data.GetString("user_id"), Is.EqualTo("ali"));
            Assert.That(data.GetString("token"), Is.EqualTo("tok-1"));
        }

        [Test]
        public void JoinPayloadCarriesRoomUserAndToken()
        {
            _transport.RaiseConnected();
            _socket.JoinGame("AB12C", "ali", "tok-1");
            var data = _transport.EmittedOf("join_game")[0];
            Assert.That(data.GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(data.GetString("user_id"), Is.EqualTo("ali"));
            Assert.That(data.GetString("token"), Is.EqualTo("tok-1"));
            Assert.That(data.Has("rejoin_token"), Is.False);
            Assert.That(_transport.ConnectUrls, Is.Empty, "zaten bagliyken yeniden baglanmamali");
        }

        [Test]
        public void GuestJoinPayloadHasNoToken()
        {
            _transport.RaiseConnected();
            _socket.JoinGame("AB12C", "Misafir_000123");
            Assert.That(_transport.EmittedOf("join_game")[0].Has("token"), Is.False);
        }

        [TestCase("game_created", "{\"room_id\":\"AB12C\",\"player_piece\":1,\"rejoin_token\":\"seat-1\"}", 1)]
        [TestCase("game_joined", "{\"room_id\":\"AB12C\",\"player_piece\":2,\"role\":\"player\",\"rejoin_token\":\"seat-1\"}", 2)]
        public void RejoinTokenIsCapturedAndSentOnReconnect(string evt, string json, int piece)
        {
            _socket.CreateGame("Misafir_000123");
            _transport.RaiseConnected();
            _transport.Receive(evt, json);
            Assert.That(_socket.RejoinToken, Is.EqualTo("seat-1"));
            Assert.That(_socket.RoomId, Is.EqualTo("AB12C"));
            Assert.That(_socket.MyPiece, Is.EqualTo(piece));
            Assert.That(_socket.InGame, Is.True);

            _transport.RaiseDisconnected("transport close");
            Assert.That(_transport.EmittedOf("join_game"), Is.Empty);
            _transport.RaiseConnected();

            var rejoin = _transport.EmittedOf("join_game");
            Assert.That(rejoin.Count, Is.EqualTo(1));
            Assert.That(rejoin[0].GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(rejoin[0].GetString("user_id"), Is.EqualTo("Misafir_000123"));
            Assert.That(rejoin[0].GetString("rejoin_token"), Is.EqualTo("seat-1"));
            Assert.That(rejoin[0].Has("token"), Is.False);
        }

        [Test]
        public void RegisteredPlayerRejoinsWithAuthToken()
        {
            _socket.JoinGame("AB12C", "ali", "tok-1");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", "{\"room_id\":\"AB12C\",\"player_piece\":2,\"role\":\"player\",\"rejoin_token\":\"seat-2\"}");
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();

            var joins = _transport.EmittedOf("join_game");
            Assert.That(joins.Count, Is.EqualTo(2));
            Assert.That(joins[1].GetString("token"), Is.EqualTo("tok-1"));
            Assert.That(joins[1].GetString("rejoin_token"), Is.EqualTo("seat-2"));
        }

        [Test]
        public void DisconnectClearsRejoinTokenAndStopsRejoining()
        {
            _socket.CreateGame("Misafir_000123");
            _transport.RaiseConnected();
            _transport.Receive("game_created", "{\"room_id\":\"AB12C\",\"player_piece\":1,\"rejoin_token\":\"seat-1\"}");

            _socket.Disconnect();
            Assert.That(_socket.RejoinToken, Is.Null);
            Assert.That(_socket.RoomId, Is.Null);
            Assert.That(_socket.InGame, Is.False);
            Assert.That(_transport.DisconnectCalls, Is.EqualTo(1));

            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game"), Is.Empty);
        }

        [Test]
        public void NewRequestDropsOldRejoinToken()
        {
            _transport.RaiseConnected();
            _socket.CreateGame("Misafir_000123");
            _transport.Receive("game_created", "{\"room_id\":\"AB12C\",\"player_piece\":1,\"rejoin_token\":\"seat-1\"}");
            _socket.JoinGame("XY9Z0", "Misafir_000123");
            Assert.That(_socket.RejoinToken, Is.Null);
        }

        [Test]
        public void SpectatorDoesNotRejoin()
        {
            _socket.JoinGame("AB12C", "ali");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", "{\"room_id\":\"AB12C\",\"player_piece\":0,\"role\":\"spectator\"}");
            Assert.That(_socket.InGame, Is.False);
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game").Count, Is.EqualTo(1));
        }

        [Test]
        public void FinishedGameIsNotRejoined()
        {
            _socket.CreateGame("ali");
            _transport.RaiseConnected();
            _transport.Receive("game_created", "{\"room_id\":\"AB12C\",\"player_piece\":1,\"rejoin_token\":\"seat-1\"}");
            _transport.Receive("game_over", "{\"winner\":1,\"reason\":\"normal\"}");
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("join_game"), Is.Empty);
        }

        [Test]
        public void SendMoveCarriesRoomColumnAndPiece()
        {
            _socket.SendMove(3);
            Assert.That(_transport.Emitted, Is.Empty, "oda yokken hamle gonderilmemeli");

            _socket.JoinGame("AB12C", "ali");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", "{\"room_id\":\"AB12C\",\"player_piece\":2,\"role\":\"player\"}");
            _socket.SendMove(3);
            var move = _transport.EmittedOf("make_move")[0];
            Assert.That(move.GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(move.GetInt("col", -1), Is.EqualTo(3));
            Assert.That(move.GetInt("player_piece"), Is.EqualTo(2));
        }

        [Test]
        public void LeaveGameSendsRoomAndStopsRejoining()
        {
            _socket.CreateGame("ali");
            _transport.RaiseConnected();
            _transport.Receive("game_created", "{\"room_id\":\"AB12C\",\"player_piece\":1}");
            _socket.LeaveGame();
            Assert.That(_transport.EmittedOf("leave_game")[0].GetString("room_id"), Is.EqualTo("AB12C"));
            Assert.That(_socket.InGame, Is.False);
        }

        [Test]
        public void ConnectErrorWhileConnectingReportsFailureAndDropsRequest()
        {
            var failures = new List<string>();
            _socket.ConnectionFailed += failures.Add;
            _socket.CreateGame("ali");
            _transport.RaiseConnectError("timeout");
            Assert.That(failures, Is.EqualTo(new[] { "timeout" }));
            Assert.That(Debug.Warnings, Has.Some.Contains("timeout"));

            _transport.RaiseConnected();
            Assert.That(_transport.Emitted, Is.Empty, "basarisiz istek sonradan gonderilmemeli");
        }

        [Test]
        public void ServerEventsAreForwardedAndInvalidJsonIsDropped()
        {
            var seen = new List<string>();
            _socket.ServerEvent += (name, data) => seen.Add(name + ":" + data.GetString("msg"));
            _transport.Receive("error", "{\"msg\":\"Oda bulunamadi\"}");
            _transport.Receive("error", "{bozuk");
            Assert.That(seen, Is.EqualTo(new[] { "error:Oda bulunamadi" }));
            Assert.That(Debug.Warnings.Count, Is.EqualTo(1));
        }

        [Test]
        public void DetachStopsListening()
        {
            int events = 0;
            _socket.ServerEvent += (n, d) => events++;
            _socket.Detach();
            _transport.Receive("error", "{\"msg\":\"x\"}");
            Assert.That(events, Is.EqualTo(0));
        }
    }
}
