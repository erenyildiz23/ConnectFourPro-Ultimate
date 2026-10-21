// =============================================================================
// Protocol.cs - Connect Four Pro Ultimate
// Sunucu (src/server.py) mesajlarinin C# karsiliklari
// =============================================================================
//
// Unity'den bagimsizdir; tests/csharp altinda test edilir.
// Alan adlari sunucudakiyle birebir aynidir; sunucu protokolu degistirilmedi.

using System.Collections.Generic;
using ConnectFourPro.Core;

namespace ConnectFourPro.Net
{
    public static class SocketEvents
    {
        // Istemci -> sunucu
        public const string CreateGame = "create_game";
        public const string JoinGame = "join_game";
        public const string MakeMove = "make_move";
        public const string LeaveGame = "leave_game";
        public const string LatencyPing = "latency_ping";

        // Sunucu -> istemci
        public const string GameCreated = "game_created";
        public const string GameJoined = "game_joined";
        public const string GameStart = "game_start";
        public const string MoveMade = "move_made";
        public const string GameOver = "game_over";
        public const string EloUpdate = "elo_update";
        public const string OpponentDisconnected = "opponent_disconnected";
        public const string OpponentReconnected = "opponent_reconnected";
        public const string GameEnded = "game_ended";
        public const string Error = "error";
        public const string LatencyPong = "latency_pong";

        public static readonly string[] ServerEvents =
        {
            GameCreated, GameJoined, GameStart, MoveMade, GameOver, EloUpdate,
            OpponentDisconnected, OpponentReconnected, GameEnded, Error, LatencyPong,
        };
    }

    public sealed class UserInfo
    {
        public const int DefaultRating = 1200;

        public int UserId;
        public string Username;
        public int Rating = DefaultRating;
        public int Wins;
        public int Losses;

        public static UserInfo From(JsonObject o, string fallbackName)
        {
            return new UserInfo
            {
                UserId = o.GetInt("user_id"),
                Username = o.GetString("username", fallbackName),
                Rating = o.GetInt("rating", DefaultRating),
                Wins = o.GetInt("wins"),
                Losses = o.GetInt("losses"),
            };
        }
    }

    public sealed class ActiveGame
    {
        public string RoomId;
        public string P1;
        public int P1Elo;
        public string P2;
        public int P2Elo;
        public bool Waiting;
        public int MoveCount;

        public static List<ActiveGame> ListFrom(object parsed)
        {
            var result = new List<ActiveGame>();
            if (!(parsed is List<object> items))
                return result;
            foreach (object item in items)
            {
                var o = JsonObject.From(item);
                result.Add(new ActiveGame
                {
                    RoomId = o.GetString("room_id", "?"),
                    P1 = o.GetString("p1", "?"),
                    P1Elo = o.GetInt("p1_elo"),
                    P2 = o.GetString("p2", "?"),
                    P2Elo = o.GetInt("p2_elo"),
                    Waiting = o.GetString("status") == "WAITING",
                    MoveCount = o.GetInt("move_count"),
                });
            }
            return result;
        }
    }

    public sealed class HistoryEntry
    {
        public string StartTime;     // ISO 8601
        public string Player1;
        public string Player2;
        public string Winner;        // beraberlikte null
        public string Result;        // win / loss / draw
        public string EndReason;     // normal / forfeit
        public int MoveCount;

        public string OpponentOf(string me) => Player1 == me ? Player2 : Player1;

        /// <summary>"2026-10-21T13:20:59" -> "2026-10-21 13:20"</summary>
        public string ShortDate
        {
            get
            {
                string s = StartTime ?? "";
                if (s.Length > 16)
                    s = s.Substring(0, 16);
                return s.Replace('T', ' ');
            }
        }

        public static List<HistoryEntry> ListFrom(JsonObject response)
        {
            var result = new List<HistoryEntry>();
            foreach (JsonObject g in response.GetObjectList("games"))
            {
                int moves = 0;
                string movesText = g.GetString("moves");
                if (!string.IsNullOrEmpty(movesText))
                {
                    // Sunucu hamleleri str(list) olarak saklar: "[3, 3, 2]" (gecerli JSON)
                    try
                    {
                        moves = Json.Parse(movesText) is List<object> l ? l.Count : 0;
                    }
                    catch (JsonException)
                    {
                        moves = 0;
                    }
                }
                result.Add(new HistoryEntry
                {
                    StartTime = g.GetString("start_time"),
                    Player1 = g.GetString("player1"),
                    Player2 = g.GetString("player2"),
                    Winner = g.GetString("winner"),
                    Result = g.GetString("result"),
                    EndReason = g.GetString("end_reason"),
                    MoveCount = moves,
                });
            }
            return result;
        }
    }

    /// <summary>Sunucunun game_over olayi.</summary>
    public sealed class GameOverInfo
    {
        public int Winner;           // 0: beraberlik
        public string Reason;        // normal / forfeit
        public int EloChangeP1;
        public int EloChangeP2;
        public int? NewRatingP1;
        public int? NewRatingP2;

        public static GameOverInfo From(JsonObject o)
        {
            var changes = o.GetObject("elo_changes");
            var ratings = o.GetObject("new_ratings");
            return new GameOverInfo
            {
                Winner = o.GetNullableInt("winner") ?? 0,
                Reason = o.GetString("reason", "normal"),
                EloChangeP1 = changes.GetInt("p1"),
                EloChangeP2 = changes.GetInt("p2"),
                NewRatingP1 = ratings.GetNullableInt("p1"),
                NewRatingP2 = ratings.GetNullableInt("p2"),
            };
        }

        public int EloChangeFor(int piece) => piece == Board.Player1 ? EloChangeP1 : EloChangeP2;
        public int? NewRatingFor(int piece) => piece == Board.Player1 ? NewRatingP1 : NewRatingP2;
    }

    public static class GameSnapshot
    {
        /// <summary>
        /// ConnectFourGame.to_dict() ciktisini (move_made, game_joined.current_state)
        /// GameState'e yukler. Python from_dict karsiligi.
        /// </summary>
        public static void Apply(GameState game, JsonObject data)
        {
            var bitboards = data.GetObject("bitboards");
            game.LoadSnapshot(
                (ulong)bitboards.GetLong("1"),
                (ulong)bitboards.GetLong("2"),
                data.GetIntList("heights"),
                data.GetIntList("history"),
                data.GetInt("current", Board.Player1),
                data.GetInt("state"),
                data.GetBool("game_over"),
                data.GetNullableInt("winner") ?? 0,
                (ulong)data.GetLong("winning_mask"));
        }

        public static int HistoryLength(JsonObject data) => data.GetArray("history").Count;
    }
}
