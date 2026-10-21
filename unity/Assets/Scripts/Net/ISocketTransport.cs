// =============================================================================
// ISocketTransport.cs - Connect Four Pro Ultimate
// Socket.IO tasima katmani: WebGL'de tarayici (jslib), Editor/masaustunde C#
// =============================================================================

using System;

namespace ConnectFourPro.Net
{
    /// <summary>
    /// Olaylar her zaman Unity ana thread'inde tetiklenir.
    /// Veri JSON metni olarak tasinir ve JsonObject ile okunur.
    /// </summary>
    public interface ISocketTransport
    {
        bool IsConnected { get; }

        event Action Connected;
        event Action<string> Disconnected;
        event Action<string> ConnectError;
        /// <summary>(olay adi, JSON veri)</summary>
        event Action<string, string> EventReceived;

        void Connect(string serverUrl);
        void Emit(string eventName, string jsonData);
        void Disconnect();
    }
}
