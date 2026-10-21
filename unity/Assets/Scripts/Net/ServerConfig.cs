// =============================================================================
// ServerConfig.cs - Connect Four Pro Ultimate
// Sunucu adresinin cozumlenmesi
// =============================================================================
//
// WebGL: oyun Flask'in /play rotasindan sunuldugu icin sayfanin kendi adresi
//        kullanilir (ayni origin: CORS gerekmez). ?server=http://... ile degistirilebilir.
// Editor/masaustu: CONNECT4_SERVER ortam degiskeni, yoksa http://localhost:5000
// (Python istemcisiyle ayni kural, bkz. src/config.py).

using System;
using System.Runtime.InteropServices;

namespace ConnectFourPro.Net
{
    public static class ServerConfig
    {
        public const string DefaultUrl = "http://localhost:5000";

#if UNITY_WEBGL && !UNITY_EDITOR
        [DllImport("__Internal")] private static extern string CF4_PageOrigin();
        [DllImport("__Internal")] private static extern string CF4_QueryParam(string name);
#endif

        private static string _url;

        public static string Url
        {
            get => _url ??= Resolve();
            set => _url = Normalize(value);
        }

        public static string Normalize(string url)
        {
            if (string.IsNullOrWhiteSpace(url))
                return DefaultUrl;
            url = url.Trim();
            if (!url.StartsWith("http://", StringComparison.OrdinalIgnoreCase)
                && !url.StartsWith("https://", StringComparison.OrdinalIgnoreCase))
                url = "http://" + url;
            return url.TrimEnd('/');
        }

        private static string Resolve()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            string query = CF4_QueryParam("server");
            if (!string.IsNullOrEmpty(query))
                return Normalize(query);
            string origin = CF4_PageOrigin();
            if (!string.IsNullOrEmpty(origin) && origin.StartsWith("http"))
                return Normalize(origin);
            return DefaultUrl;
#else
            return Normalize(Environment.GetEnvironmentVariable("CONNECT4_SERVER"));
#endif
        }
    }
}
