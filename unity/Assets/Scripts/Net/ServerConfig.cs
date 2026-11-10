// =============================================================================
// ServerConfig.cs - Connect Four Pro Ultimate
// Sunucu adresinin cozumlenmesi
// =============================================================================
//
// WebGL: oyun Flask'in /play rotasindan sunuldugu icin sayfanin kendi adresi
//        kullanilir (ayni origin: CORS gerekmez). ?server=http://... yalnizca sayfa
//        localhost'tan sunuluyorsa (yerel gelistirme) veya development build'de gecerlidir.
//        Aksi halde https://site/play/?server=https://saldirgan gibi bir baglanti, sayfa
//        gercek adresi gosterirken kullanici adi ve sifreyi baska sunucuya gonderirdi.
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

        /// <summary>Adres bu bilgisayari mi gosteriyor (localhost, 127.x.x.x, [::1])?</summary>
        public static bool IsLoopback(string url)
        {
            if (string.IsNullOrWhiteSpace(url))
                return false;
            // Uri, http://localhost@saldirgan.com gibi adreslerde gercek host'u verir
            if (!Uri.TryCreate(url.Trim(), UriKind.Absolute, out Uri uri))
                return false;
            if (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps)
                return false;
            return uri.IsLoopback;
        }

        /// <summary>?server= parametresine guvenilebilir mi?</summary>
        public static bool AllowQueryOverride(string pageOrigin, bool developmentBuild)
        {
            return developmentBuild || IsLoopback(pageOrigin);
        }

        /// <summary>WebGL'de sunucu adresi: izin varsa ?server=, yoksa sayfanin adresi.</summary>
        public static string ResolveWeb(string query, string pageOrigin, bool developmentBuild)
        {
            if (!string.IsNullOrWhiteSpace(query) && AllowQueryOverride(pageOrigin, developmentBuild))
                return Normalize(query);
            if (!string.IsNullOrEmpty(pageOrigin) && pageOrigin.StartsWith("http", StringComparison.OrdinalIgnoreCase))
                return Normalize(pageOrigin);
            return DefaultUrl;
        }

        private static string Resolve()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            string query = CF4_QueryParam("server");
            string origin = CF4_PageOrigin();
            bool development = UnityEngine.Debug.isDebugBuild;
            if (!string.IsNullOrWhiteSpace(query) && !AllowQueryOverride(origin, development))
                UnityEngine.Debug.LogWarning("[CF4] ?server= yok sayildi: yalnizca localhost'tan sunulan sayfada gecerlidir");
            return ResolveWeb(query, origin, development);
#else
            return Normalize(Environment.GetEnvironmentVariable("CONNECT4_SERVER"));
#endif
        }
    }
}
