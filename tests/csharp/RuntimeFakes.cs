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
    }
}
