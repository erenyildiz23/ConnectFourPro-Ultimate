// Json ayristirici ve sunucu mesajlari (src/server.py ciktisi) testleri.
using System.Collections.Generic;
using ConnectFourPro.Core;
using ConnectFourPro.Net;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class JsonTests
    {
        [Test]
        public void ParsesNestedValues()
        {
            var o = JsonObject.ParseObject("{\"a\": [1, 2.5, \"x\\n\\u00e7\"], \"b\": {\"c\": null, \"d\": true}, \"e\": -3}");
            var a = o.GetArray("a");
            Assert.That(a[0], Is.EqualTo(1L));
            Assert.That(a[1], Is.EqualTo(2.5));
            Assert.That(a[2], Is.EqualTo("x\nç"));
            Assert.That(o.GetObject("b").IsNull("c"));
            Assert.That(o.GetObject("b").GetBool("d"));
            Assert.That(o.GetInt("e"), Is.EqualTo(-3));
        }

        [Test]
        public void LargeIntegersKeepPrecision() =>
            Assert.That(JsonObject.ParseObject("{\"x\": 562949953421311}").GetLong("x"), Is.EqualTo(562949953421311L));

        [TestCase("{")]
        [TestCase("{\"a\" 1}")]
        [TestCase("[1,]")]
        [TestCase("tru")]
        [TestCase("{} x")]
        public void RejectsInvalidJson(string text) => Assert.Throws<JsonException>(() => Json.Parse(text));

        [Test]
        public void SerializeRoundTrip()
        {
            var data = new Dictionary<string, object> { ["room_id"] = "AB12C", ["col"] = 3, ["ok"] = false, ["q"] = "a\"b" };
            string text = Json.Serialize(data);
            Assert.That(text, Is.EqualTo("{\"room_id\":\"AB12C\",\"col\":3,\"ok\":false,\"q\":\"a\\\"b\"}"));
            Assert.That(JsonObject.ParseObject(text).GetString("q"), Is.EqualTo("a\"b"));
        }

        [Test]
        public void MissingOrWrongTypedFieldsFallBack()
        {
            var o = JsonObject.ParseObject("{\"a\": \"x\", \"n\": null}");
            Assert.That(o.GetInt("a", 7), Is.EqualTo(7));
            Assert.That(o.GetInt("missing", 5), Is.EqualTo(5));
            Assert.That(o.GetNullableInt("n"), Is.Null);
            Assert.That(o.GetString("n", "d"), Is.EqualTo("d"));
            Assert.That(o.GetIntList("missing"), Is.Empty);
        }
    }

    public class ProtocolTests
    {
        // ConnectFourGame.from_moves([0,1,0,1,0,1,0]).to_dict() + 'col' (json.dumps ciktisi)
        private const string MoveMadeWin =
            "{\"bitboards\": {\"1\": 15, \"2\": 896}, \"heights\": [4, 10, 14, 21, 28, 35, 42], " +
            "\"history\": [0, 1, 0, 1, 0, 1, 0], \"current\": 1, \"state\": 1, \"game_over\": true, " +
            "\"winner\": 1, \"winning_mask\": 15, \"col\": 0}";

        [Test]
        public void SnapshotMatchesLocalGame()
        {
            var local = GameState.FromMoves(Fixtures.P1VerticalWin);
            var synced = new GameState();
            GameSnapshot.Apply(synced, JsonObject.ParseObject(MoveMadeWin));
            Assert.That(synced.ToString(), Is.EqualTo(local.ToString()));
            Assert.That(synced.MoveHistory, Is.EqualTo(local.MoveHistory));
            Assert.That(synced.GameOver && synced.Status == GameStatus.Win && synced.Winner == 1);
            Assert.That(synced.GetWinningPositions(), Is.EqualTo(local.GetWinningPositions()));
            Assert.That(synced.MakeMove(5), Is.False);
        }

        [Test]
        public void DrawDetectedAfterSync()
        {
            var before = GameState.FromMoves(System.Linq.Enumerable.Take(Fixtures.DrawSequence, 41));
            var heights = new List<object>();
            for (int c = 0; c < 7; c++) heights.Add(c * 7 + (c == 2 ? 5 : 6));
            var data = new Dictionary<string, object>
            {
                ["bitboards"] = new Dictionary<string, object> { ["1"] = before.GetBitboard(1), ["2"] = before.GetBitboard(2) },
                ["heights"] = heights,
                ["history"] = new List<int>(before.MoveHistory),
                ["current"] = before.CurrentPlayer, ["state"] = 0, ["game_over"] = false, ["winner"] = null, ["winning_mask"] = 0,
            };
            var synced = new GameState();
            GameSnapshot.Apply(synced, JsonObject.ParseObject(Json.Serialize(data)));
            Assert.That(synced.MoveCount, Is.EqualTo(41));
            Assert.That(synced.MakeMove(Fixtures.DrawSequence[41]));
            Assert.That(synced.Status, Is.EqualTo(GameStatus.Draw));
        }

        [Test]
        public void GameOverWithEloChanges()
        {
            var info = GameOverInfo.From(JsonObject.ParseObject(
                "{\"winner\": 2, \"winner_uid\": \"bob\", \"elo_changes\": {\"p1\": -15, \"p2\": 15}, " +
                "\"new_ratings\": {\"p1\": 1185, \"p2\": 1215}, \"move_count\": 9, \"reason\": \"forfeit\"}"));
            Assert.That(info.Winner, Is.EqualTo(2));
            Assert.That(info.Reason, Is.EqualTo("forfeit"));
            Assert.That(info.EloChangeFor(1), Is.EqualTo(-15));
            Assert.That(info.NewRatingFor(2), Is.EqualTo(1215));
        }

        [Test]
        public void DrawGameOverHasNoWinner()
        {
            var info = GameOverInfo.From(JsonObject.ParseObject(
                "{\"winner\": null, \"elo_changes\": {\"p1\": 0, \"p2\": 0}, \"new_ratings\": {\"p1\": null, \"p2\": null}, \"reason\": \"normal\"}"));
            Assert.That(info.Winner, Is.EqualTo(0));
            Assert.That(info.NewRatingFor(1), Is.Null);
        }

        [Test]
        public void ActiveGamesList()
        {
            var games = ActiveGame.ListFrom(Json.Parse(
                "[{\"room_id\": \"AB12C\", \"p1\": \"ali\", \"p1_elo\": 1250, \"p2\": \"Bekleniyor...\", \"p2_elo\": 0, \"status\": \"WAITING\", \"move_count\": 0}," +
                " {\"room_id\": \"XY9Z0\", \"p1\": \"a\", \"p1_elo\": 1200, \"p2\": \"b\", \"p2_elo\": 1190, \"status\": \"PLAYING\", \"move_count\": 4}]"));
            Assert.That(games.Count, Is.EqualTo(2));
            Assert.That(games[0].Waiting && games[0].RoomId == "AB12C");
            Assert.That(!games[1].Waiting && games[1].P2Elo == 1190);
        }

        [Test]
        public void HistoryEntries()
        {
            var list = HistoryEntry.ListFrom(JsonObject.ParseObject(
                "{\"games\": [{\"game_id\": 1, \"start_time\": \"2026-10-21T13:20:59.123\", \"moves\": \"[3, 3, 2]\", " +
                "\"end_reason\": \"forfeit\", \"player1\": \"ali\", \"player2\": \"veli\", \"winner\": \"ali\", \"result\": \"win\"}]}"));
            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list[0].MoveCount, Is.EqualTo(3));
            Assert.That(list[0].ShortDate, Is.EqualTo("2026-10-21 13:20"));
            Assert.That(list[0].OpponentOf("veli"), Is.EqualTo("ali"));
        }

        [Test]
        public void UserInfoDefaults()
        {
            var u = UserInfo.From(JsonObject.ParseObject("{\"username\": \"ali\"}"), "x");
            Assert.That(u.Username == "ali" && u.Rating == UserInfo.DefaultRating);
        }
    }
}
