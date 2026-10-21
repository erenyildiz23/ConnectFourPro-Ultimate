// =============================================================================
// WebGLSocketTransport.cs - Connect Four Pro Ultimate
// WebGL: tarayicidaki resmi socket.io-client (Plugins/WebGL/SocketBridge.jslib)
// =============================================================================
//
// JS tarafi olaylari SendMessage ile bu GameObject'e iletir; bu yuzden nesnenin
// adi benzersiz olmali ve sahne degisiminde yok edilmemelidir.

using System;
using System.Runtime.InteropServices;
using UnityEngine;
using UnityEngine.Scripting;

namespace ConnectFourPro.Net
{
    public sealed class WebGLSocketTransport : MonoBehaviour, ISocketTransport
    {
#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")] private static extern void CF4_SocketConnect(string url, string gameObjectName);
        [DllImport("__Internal")] private static extern void CF4_SocketEmit(string eventName, string jsonData);
        [DllImport("__Internal")] private static extern void CF4_SocketDisconnect();
#else
        private static void CF4_SocketConnect(string url, string gameObjectName) =>
            throw new PlatformNotSupportedException("WebGLSocketTransport yalnizca WebGL build'inde calisir");
        private static void CF4_SocketEmit(string eventName, string jsonData) { }
        private static void CF4_SocketDisconnect() { }
#endif

        public bool IsConnected { get; private set; }

        public event Action Connected;
        public event Action<string> Disconnected;
        public event Action<string> ConnectError;
        public event Action<string, string> EventReceived;

        public void Connect(string serverUrl) => CF4_SocketConnect(serverUrl ?? "", gameObject.name);

        public void Emit(string eventName, string jsonData)
        {
            if (IsConnected)
                CF4_SocketEmit(eventName, string.IsNullOrEmpty(jsonData) ? "null" : jsonData);
        }

        public void Disconnect()
        {
            bool was = IsConnected;
            IsConnected = false;
            CF4_SocketDisconnect();
            if (was)
                Disconnected?.Invoke("io client disconnect");
        }

        // --- jslib'den SendMessage ile cagrilir ([Preserve]: kod ayiklama silmesin) ---

        [Preserve]
        private void OnSocketConnected(string _)
        {
            IsConnected = true;
            Connected?.Invoke();
        }

        [Preserve]
        private void OnSocketDisconnected(string reason)
        {
            IsConnected = false;
            Disconnected?.Invoke(reason);
        }

        [Preserve]
        private void OnSocketError(string message) => ConnectError?.Invoke(message);

        /// <summary>"olay_adi\n{json}" bicimindeki mesaj.</summary>
        [Preserve]
        private void OnSocketEvent(string packed)
        {
            int nl = packed.IndexOf('\n');
            if (nl < 0)
                return;
            EventReceived?.Invoke(packed.Substring(0, nl), packed.Substring(nl + 1));
        }
    }
}
