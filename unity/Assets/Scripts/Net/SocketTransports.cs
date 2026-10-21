// =============================================================================
// SocketTransports.cs - Connect Four Pro Ultimate
// Platforma gore Socket.IO tasima katmani secimi
// =============================================================================

using UnityEngine;

namespace ConnectFourPro.Net
{
    public static class SocketTransports
    {
        /// <summary>WebGL build'inde tarayici koprusu, digerlerinde C# istemcisi.</summary>
        public static ISocketTransport Create(GameObject host)
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            // jslib olaylari SendMessage ile bu nesnenin adina gonderir: ad benzersiz olmali
            var go = new GameObject("CF4_SocketBridge");
            go.transform.SetParent(host.transform, false);
            return go.AddComponent<WebGLSocketTransport>();
#else
            return host.AddComponent<EditorSocketTransport>();
#endif
        }
    }
}
