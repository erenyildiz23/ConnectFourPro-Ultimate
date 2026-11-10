// Sunucu adresi cozumleme (Net/ServerConfig.cs): ?server= yalnizca yerel sayfada gecerli.
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
    }
}
