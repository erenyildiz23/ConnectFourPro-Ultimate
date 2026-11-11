// Runtime testleri (AppController, GameSocket) icin sahte tasiyici ve sunucu mesaji yardimcilari.
using System;
using System.Collections.Generic;
using ConnectFourPro.Core;
using ConnectFourPro.Net;

namespace ConnectFourPro.Tests
{
    /// <summary>Ag yerine: cagrilari kaydeder, olaylari test tetikler.</summary>
    internal sealed class FakeTransport : ISocketTransport
    {
        public bool IsConnected { get; private set; }

        public event Action Connected;
        public event Action<string> Disconnected;
        public event Action<string> ConnectError;
        public event Action<string, string> EventReceived;

        public readonly List<string> ConnectUrls = new List<string>();
        public readonly List<(string name, JsonObject data)> Emitted = new List<(string, JsonObject)>();
        public int DisconnectCalls;

        public void Connect(string serverUrl) => ConnectUrls.Add(serverUrl);
        public void Emit(string eventName, string jsonData) => Emitted.Add((eventName, JsonObject.ParseObject(jsonData)));

        // Gercek tasiyicilar gibi: bagliyken kapatilirsa Disconnected tetiklenir
        public void Disconnect()
        {
            DisconnectCalls++;
            bool was = IsConnected;
            IsConnected = false;
            if (was)
                Disconnected?.Invoke("io client disconnect");
        }

        public void RaiseConnected()
        {
            IsConnected = true;
            Connected?.Invoke();
        }

        public void RaiseDisconnected(string reason)
        {
            IsConnected = false;
            Disconnected?.Invoke(reason);
        }

        public void RaiseConnectError(string error) => ConnectError?.Invoke(error);
        public void Receive(string name, string json) => EventReceived?.Invoke(name, json);

        public List<JsonObject> EmittedOf(string name)
        {
            var result = new List<JsonObject>();
            foreach (var (n, data) in Emitted)
                if (n == name)
                    result.Add(data);
            return result;
        }
    }

    internal static class ServerMessages
    {
        /// <summary>ConnectFourGame.to_dict() bicimi (src/game_core.py); col verilirse move_made.</summary>
        public static string Snapshot(GameState g, int? col = null)
        {
            var heights = new List<int>();
            for (int c = 0; c < Board.Cols; c++)
                heights.Add(c * Board.ColStride + g.NextRow(c));
            var data = new Dictionary<string, object>
            {
                ["bitboards"] = new Dictionary<string, object> { ["1"] = g.GetBitboard(1), ["2"] = g.GetBitboard(2) },
                ["heights"] = heights,
                ["history"] = new List<int>(g.MoveHistory),
                ["current"] = g.CurrentPlayer,
                ["state"] = (int)g.Status,
                ["game_over"] = g.GameOver,
                ["winner"] = g.Winner == 0 ? null : (object)g.Winner,
                ["winning_mask"] = g.WinningMask,
            };
            if (col != null)
                data["col"] = col.Value;
            return Json.Serialize(data);
        }

        public static string MoveMade(params int[] moves) =>
            Snapshot(GameState.FromMoves(moves), moves[moves.Length - 1]);

        /// <summary>Yeni sunucunun move_made'i: hamle suresi alanlariyla (sure yoksa secondsLeft null).</summary>
        public static string MoveMadeTimed(int? secondsLeft, int moveTime, params int[] moves) =>
            WithFields(MoveMade(moves), Clock(secondsLeft, moveTime));

        /// <summary>_finish_game yukuyle ayni bicim; detail null ise alan yine gonderilir (yeni sunucu).</summary>
        public static string GameOver(int? winner, string reason = "normal", string detail = null,
                                      int eloP1 = 0, int eloP2 = 0, int? ratingP1 = null, int? ratingP2 = null)
        {
            return Json.Serialize(GameOverFields(winner, reason, detail, eloP1, eloP2, ratingP1, ratingP2));
        }

        public static Dictionary<string, object> GameOverFields(int? winner, string reason = "normal", string detail = null,
                                                                int eloP1 = 0, int eloP2 = 0, int? ratingP1 = null, int? ratingP2 = null)
        {
            return new Dictionary<string, object>
            {
                ["winner"] = winner,
                ["elo_changes"] = new Dictionary<string, object> { ["p1"] = eloP1, ["p2"] = eloP2 },
                ["new_ratings"] = new Dictionary<string, object> { ["p1"] = ratingP1, ["p2"] = ratingP2 },
                ["reason"] = reason,
                ["detail"] = detail,
            };
        }

        /// <summary>Rovansta her koltuga giden game_start (player_piece yeni koltuk).</summary>
        public static string RematchStart(int piece, string opponent, int opponentElo, string me, int myElo,
                                          int? secondsLeft = null, int moveTime = 0, string roomId = "AB12C")
        {
            var mine = new Dictionary<string, object> { ["username"] = me, ["rating"] = myElo };
            var theirs = new Dictionary<string, object> { ["username"] = opponent, ["rating"] = opponentElo };
            var data = new Dictionary<string, object>
            {
                ["msg"] = "Rovans basladi!", ["room_id"] = roomId, ["player_piece"] = piece,
                ["rematch"] = true, ["game_no"] = 2,
                ["p1_info"] = piece == Board.Player1 ? mine : theirs,
                ["p2_info"] = piece == Board.Player1 ? theirs : mine,
                ["opponent_name"] = opponent, ["opponent_elo"] = opponentElo,
            };
            foreach (var kv in Clock(secondsLeft, moveTime))
                data[kv.Key] = kv.Value;
            return Json.Serialize(data);
        }

        /// <summary>Odaya giden rematch_started (seyirciler icin bos tahta).</summary>
        public static string RematchStarted(string p1, string p2, int? secondsLeft = null, int moveTime = 0, string roomId = "AB12C")
        {
            var data = new Dictionary<string, object>
            {
                ["room_id"] = roomId, ["game_no"] = 2,
                ["p1_info"] = new Dictionary<string, object> { ["username"] = p1, ["rating"] = 1250 },
                ["p2_info"] = new Dictionary<string, object> { ["username"] = p2, ["rating"] = 1300 },
                ["current_state"] = Json.Parse(Snapshot(new GameState())),
            };
            foreach (var kv in Clock(secondsLeft, moveTime))
                data[kv.Key] = kv.Value;
            return Json.Serialize(data);
        }

        public static Dictionary<string, object> Clock(int? secondsLeft, int moveTime) =>
            new Dictionary<string, object> { ["move_time"] = moveTime, ["turn_seconds_left"] = secondsLeft };

        /// <summary>JSON nesnesine alan ekler.</summary>
        public static string WithFields(string json, Dictionary<string, object> fields)
        {
            var d = (Dictionary<string, object>)Json.Parse(json);
            foreach (var kv in fields)
                d[kv.Key] = kv.Value;
            return Json.Serialize(d);
        }
    }
}
