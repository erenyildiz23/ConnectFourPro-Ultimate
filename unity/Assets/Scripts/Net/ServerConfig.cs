// =============================================================================
// ServerConfig.cs - Connect Four Pro Ultimate
// Sunucu adresinin cozumlenmesi
// =============================================================================
//
// WebGL, oncelik sirasi:
//   1. ?server=http://...  yalnizca sayfa localhost'tan sunuluyorsa (yerel gelistirme)
//      veya development build'de gecerlidir. Aksi halde https://site/play/?server=https://saldirgan
//      gibi bir baglanti, sayfa gercek adresi gosterirken kullanici adi ve sifreyi baska
//      sunucuya gonderirdi.
//   2. server-config.js'teki window.CF4_SERVER_URL: build ile birlikte yayinlanan dosya
//      (oyun koduyla ayni guvende), bu yuzden release build'de de gecerlidir. Oyun baska
//      bir siteden (itch.io) sunulup sunucu baska yerde calistiginda kullanilir. Mutlak
//      http(s) adresi olmali; sayfa https iken http adres reddedilir (mixed content).
//   3. Sayfanin kendi adresi: oyun Flask'in /play rotasindan sunulur (ayni origin).
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
        [DllImport("__Internal")] private static extern string CF4_ConfiguredServer();
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

        /// <summary>
        /// server-config.js'te yazan adresi dogrular. Kullanilabilirse "sema://host[:port]"
        /// dondurur; bos ise null ve warning = null; gecersizse null ve nedeni warning'de.
        /// </summary>
        public static string ParseConfiguredServer(string configured, string pageOrigin, out string warning)
        {
            warning = null;
            if (string.IsNullOrWhiteSpace(configured))
                return null;
            string value = configured.Trim();
            if (!Uri.TryCreate(value, UriKind.Absolute, out Uri uri)
                || (uri.Scheme != Uri.UriSchemeHttp && uri.Scheme != Uri.UriSchemeHttps))
            {
                warning = "CF4_SERVER_URL mutlak bir http(s) adresi degil: " + value;
                return null;
            }
            // Socket.IO yolu adresten okunur (/yol namespace sayilir): yalnizca kok adres
            if (!string.IsNullOrEmpty(uri.UserInfo) || !string.IsNullOrEmpty(uri.Query)
                || !string.IsNullOrEmpty(uri.Fragment) || uri.AbsolutePath != "/")
            {
                warning = "CF4_SERVER_URL yalnizca sema://host[:port] olmali (kullanici, yol, sorgu yok): " + value;
                return null;
            }
            if (uri.Scheme == Uri.UriSchemeHttp && IsHttpsPage(pageOrigin))
            {
                warning = "CF4_SERVER_URL http, sayfa https: tarayici engeller (mixed content); https adres kullanin: " + value;
                return null;
            }
            return uri.GetLeftPart(UriPartial.Authority);
        }

        private static bool IsHttpsPage(string pageOrigin) =>
            !string.IsNullOrEmpty(pageOrigin)
            && pageOrigin.TrimStart().StartsWith("https://", StringComparison.OrdinalIgnoreCase);

        /// <summary>WebGL'de sunucu adresi: izin varsa ?server=, yoksa sayfanin adresi.</summary>
        public static string ResolveWeb(string query, string pageOrigin, bool developmentBuild) =>
            ResolveWeb(query, pageOrigin, developmentBuild, null);

        /// <summary>
        /// WebGL'de sunucu adresi: izin varsa ?server=, sonra gecerli CF4_SERVER_URL
        /// (server-config.js), en son sayfanin adresi.
        /// </summary>
        public static string ResolveWeb(string query, string pageOrigin, bool developmentBuild, string configured)
        {
            if (!string.IsNullOrWhiteSpace(query) && AllowQueryOverride(pageOrigin, developmentBuild))
                return Normalize(query);
            string baked = ParseConfiguredServer(configured, pageOrigin, out _);
            if (baked != null)
                return baked;
            if (!string.IsNullOrEmpty(pageOrigin) && pageOrigin.StartsWith("http", StringComparison.OrdinalIgnoreCase))
                return Normalize(pageOrigin);
            return DefaultUrl;
        }

        private static string Resolve()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            string query = CF4_QueryParam("server");
            string origin = CF4_PageOrigin();
            string configured = CF4_ConfiguredServer();
            bool development = UnityEngine.Debug.isDebugBuild;
            if (!string.IsNullOrWhiteSpace(query) && !AllowQueryOverride(origin, development))
                UnityEngine.Debug.LogWarning("[CF4] ?server= yok sayildi: yalnizca localhost'tan sunulan sayfada gecerlidir");
            ParseConfiguredServer(configured, origin, out string warning);
            if (warning != null)
                UnityEngine.Debug.LogWarning("[CF4] " + warning + " (sayfanin adresi kullaniliyor)");
            return ResolveWeb(query, origin, development, configured);
#else
            return Normalize(Environment.GetEnvironmentVariable("CONNECT4_SERVER"));
#endif
        }
    }
}
