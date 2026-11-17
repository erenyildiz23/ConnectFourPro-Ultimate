// Sunucu adresi cozumleme (Net/ServerConfig.cs): ?server= yalnizca yerel sayfada gecerli;
// server-config.js adresi (itch.io gibi baska siteden sunulan build) release build'de de gecerli.
using ConnectFourPro.Net;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class ServerConfigTests
    {
        [TestCase("http://localhost:5000")]
        [TestCase("https://localhost")]
        [TestCase("http://127.0.0.1:5000/play/")]
        [TestCase("http://[::1]:5000")]
        [TestCase("  http://localhost:5000  ")]
        public void LoopbackAddresses(string url) => Assert.That(ServerConfig.IsLoopback(url), Is.True);

        [TestCase("http://localhost@evil.example")]
        [TestCase("http://localhost:5000@evil.example/")]
        [TestCase("http://localhost.evil.example")]
        [TestCase("https://game.example")]
        [TestCase("http://192.168.1.10:5000")]
        [TestCase("ftp://localhost")]
        [TestCase("localhost:5000")]
        [TestCase("/play/")]
        [TestCase("")]
        [TestCase(null)]
        public void NonLoopbackAddresses(string url) => Assert.That(ServerConfig.IsLoopback(url), Is.False);

        [Test]
        public void QueryOverrideOnlyFromLoopbackPageOrDevelopmentBuild()
        {
            Assert.That(ServerConfig.AllowQueryOverride("http://localhost:5000", false), Is.True);
            Assert.That(ServerConfig.AllowQueryOverride("https://game.example", false), Is.False);
            Assert.That(ServerConfig.AllowQueryOverride("http://localhost@evil.example", false), Is.False);
            Assert.That(ServerConfig.AllowQueryOverride(null, false), Is.False);
            Assert.That(ServerConfig.AllowQueryOverride("https://game.example", true), Is.True);
        }

        [Test]
        public void LoopbackPageHonoursQuery() =>
            Assert.That(ServerConfig.ResolveWeb("http://127.0.0.1:6000/", "http://localhost:5000", false),
                        Is.EqualTo("http://127.0.0.1:6000"));

        [Test]
        public void PublicPageIgnoresQuery() =>
            Assert.That(ServerConfig.ResolveWeb("https://evil.example", "https://game.example", false),
                        Is.EqualTo("https://game.example"));

        [Test]
        public void UserInfoTrickDoesNotEnableQuery() =>
            Assert.That(ServerConfig.ResolveWeb("https://evil.example", "http://localhost@evil.example", false),
                        Is.EqualTo("http://localhost@evil.example"));

        [Test]
        public void DevelopmentBuildHonoursQuery() =>
            Assert.That(ServerConfig.ResolveWeb("staging.example:5000", "https://game.example", true),
                        Is.EqualTo("http://staging.example:5000"));

        [Test]
        public void WithoutQueryUsesPageOrigin() =>
            Assert.That(ServerConfig.ResolveWeb("  ", "https://game.example/", false), Is.EqualTo("https://game.example"));

        [TestCase(null)]
        [TestCase("")]
        [TestCase("file://")]
        public void UnusableOriginFallsBackToDefault(string origin) =>
            Assert.That(ServerConfig.ResolveWeb(null, origin, false), Is.EqualTo(ServerConfig.DefaultUrl));

        [TestCase(null, "http://localhost:5000")]
        [TestCase("   ", "http://localhost:5000")]
        [TestCase("example.com:5000/", "http://example.com:5000")]
        [TestCase(" HTTPS://example.com// ", "HTTPS://example.com")]
        public void Normalize(string input, string expected) =>
            Assert.That(ServerConfig.Normalize(input), Is.EqualTo(expected));

        // --- server-config.js (window.CF4_SERVER_URL): build ile yayinlanan adres ---

        private const string Itch = "https://html-classic.itch.zone";
        private const string Api = "https://connect4.example.com";

        [Test]
        public void BakedUrlWinsOnPublicOrigin() =>
            Assert.That(ServerConfig.ResolveWeb(null, Itch, false, Api), Is.EqualTo(Api));

        [Test]
        public void BakedUrlWinsOverQueryOnPublicReleasePage() =>
            Assert.That(ServerConfig.ResolveWeb("https://evil.example", Itch, false, Api), Is.EqualTo(Api));

        [Test]
        public void QueryStillOverridesBakedUrlOnLoopbackPage() =>
            Assert.That(ServerConfig.ResolveWeb("http://127.0.0.1:6000", "http://localhost:8123", false, Api),
                        Is.EqualTo("http://127.0.0.1:6000"));

        [Test]
        public void QueryStillOverridesBakedUrlInDevelopmentBuild() =>
            Assert.That(ServerConfig.ResolveWeb("https://staging.example", Itch, true, Api),
                        Is.EqualTo("https://staging.example"));

        [Test]
        public void QueryIgnoredOnPublicOriginWithoutBakedUrl() =>
            Assert.That(ServerConfig.ResolveWeb("https://evil.example", Itch, false, ""), Is.EqualTo(Itch));

        [TestCase(null)]
        [TestCase("")]
        [TestCase("   ")]
        public void EmptyBakedUrlUsesPageOrigin(string baked)
        {
            Assert.That(ServerConfig.ResolveWeb(null, "https://game.example/", false, baked), Is.EqualTo("https://game.example"));
            Assert.That(ServerConfig.ParseConfiguredServer(baked, "https://game.example", out string warning), Is.Null);
            Assert.That(warning, Is.Null);
        }

        [TestCase("connect4.example.com")]                 // sema yok (goreli)
        [TestCase("/api")]                                 // goreli yol
        [TestCase("//connect4.example.com")]
        [TestCase("ftp://connect4.example.com")]
        [TestCase("javascript:alert(1)")]
        [TestCase("file:///etc/passwd")]
        [TestCase("https://user:pw@connect4.example.com")] // kimlik bilgisi
        [TestCase("https://connect4.example.com/socket")]  // yol: Socket.IO namespace sayilirdi
        [TestCase("https://connect4.example.com/?x=1")]
        [TestCase("https://connect4.example.com/#a")]
        [TestCase("not a url")]
        public void InvalidBakedUrlIsIgnored(string baked)
        {
            Assert.That(ServerConfig.ParseConfiguredServer(baked, Itch, out string warning), Is.Null);
            Assert.That(warning, Does.Contain("CF4_SERVER_URL"));
            Assert.That(ServerConfig.ResolveWeb(null, Itch, false, baked), Is.EqualTo(Itch));
        }

        [Test]
        public void HttpBakedUrlOnHttpsPageIsRefused()
        {
            Assert.That(ServerConfig.ParseConfiguredServer("http://connect4.example.com", Itch, out string warning), Is.Null);
            Assert.That(warning, Does.Contain("mixed content"));
            Assert.That(ServerConfig.ResolveWeb(null, Itch, false, "http://connect4.example.com"), Is.EqualTo(Itch));
        }

        [Test]
        public void HttpBakedUrlOnHttpPageIsAllowed() =>
            Assert.That(ServerConfig.ResolveWeb(null, "http://localhost:8123", false, "http://192.168.1.10:5000"),
                        Is.EqualTo("http://192.168.1.10:5000"));

        [TestCase("https://connect4.example.com/", "https://connect4.example.com")]
        [TestCase("  https://Connect4.Example.com:8443  ", "https://connect4.example.com:8443")]
        [TestCase("HTTPS://connect4.example.com", "https://connect4.example.com")]
        [TestCase("https://connect4.example.com:443", "https://connect4.example.com")]
        public void BakedUrlIsNormalized(string baked, string expected)
        {
            Assert.That(ServerConfig.ParseConfiguredServer(baked, Itch, out string warning), Is.EqualTo(expected));
            Assert.That(warning, Is.Null);
        }
    }
}
