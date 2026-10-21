// =============================================================================
// EditorSocketTransport.cs - Connect Four Pro Ultimate
// Editor ve masaustu: C# SocketIOClient; olaylar ana thread'e tasinir
// =============================================================================

using System;
using System.Collections.Concurrent;
using UnityEngine;

namespace ConnectFourPro.Net
{
    public sealed class EditorSocketTransport : MonoBehaviour, ISocketTransport
    {
        private SocketIOClient _client;
        // Arka plan thread'inden gelen olaylar Update'te ana thread'de islenir
        private readonly ConcurrentQueue<Action> _mainThread = new ConcurrentQueue<Action>();

        public bool IsConnected => _client != null && _client.IsConnected;

        public event Action Connected;
        public event Action<string> Disconnected;
        public event Action<string> ConnectError;
        public event Action<string, string> EventReceived;

        public void Connect(string serverUrl)
        {
            DisposeClient();
            var client = new SocketIOClient();
            client.Connected += () => _mainThread.Enqueue(() => Connected?.Invoke());
            client.Disconnected += reason => _mainThread.Enqueue(() => Disconnected?.Invoke(reason));
            client.ConnectError += error => _mainThread.Enqueue(() => ConnectError?.Invoke(error));
            client.EventReceived += (name, data) => _mainThread.Enqueue(() => EventReceived?.Invoke(name, data));
            _client = client;
            client.Connect(serverUrl);
        }

        public void Emit(string eventName, string jsonData) => _client?.Emit(eventName, jsonData);

        public void Disconnect() => _client?.Disconnect();

        private void Update()
        {
            while (_mainThread.TryDequeue(out Action action))
            {
                try
                {
                    action();
                }
                catch (Exception e)
                {
                    Debug.LogException(e);
                }
            }
        }

        private void DisposeClient()
        {
            _client?.Dispose();
            _client = null;
        }

        private void OnDestroy() => DisposeClient();
        private void OnApplicationQuit() => DisposeClient();
    }
}
