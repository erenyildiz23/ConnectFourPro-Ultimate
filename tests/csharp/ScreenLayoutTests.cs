// Ekran yonu secimi, portre sabitleri ve satir yerlesimlerinin sigmasi (Game/ScreenLayout.cs).
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class ScreenLayoutTests
    {
        private static readonly LayoutOrientation[] Both = { LayoutOrientation.Landscape, LayoutOrientation.Portrait };

        [TestCase(1280, 720, LayoutOrientation.Landscape)]
        [TestCase(390, 844, LayoutOrientation.Portrait)]
        [TestCase(800, 800, LayoutOrientation.Landscape)]
        [TestCase(0, 0, LayoutOrientation.Landscape)]
        public void OrientationFromSize(int w, int h, LayoutOrientation expected)
            => Assert.That(ScreenLayout.For(w, h), Is.EqualTo(expected));

        [Test]
        public void PortraitFontHasMinimum()
        {
            Assert.That(ScreenLayout.FontSize(13, LayoutOrientation.Portrait), Is.EqualTo(18));
            Assert.That(ScreenLayout.FontSize(21, LayoutOrientation.Portrait), Is.EqualTo(21));
            Assert.That(ScreenLayout.FontSize(13, LayoutOrientation.Landscape), Is.EqualTo(13));
        }

        [Test]
        public void ContentEndsAboveStatusBar()
        {
            // Durum cubugu: yatay 52 px (720 - 52), dikey 72 px (960 - 72)
            Assert.That(ScreenLayout.ContentBottom(LayoutOrientation.Landscape), Is.EqualTo(668f));
            Assert.That(ScreenLayout.ContentBottom(LayoutOrientation.Portrait), Is.EqualTo(888f));
        }

        [Test]
        public void RowLayoutGeometry()
        {
            var r = new RowLayout(100, 50, 40, 3);
            Assert.That(r.Center(0), Is.EqualTo(100f));
            Assert.That(r.Center(2), Is.EqualTo(200f));
            Assert.That(r.Top, Is.EqualTo(80f));
            Assert.That(r.Bottom, Is.EqualTo(220f));
            Assert.That(ScreenLayout.Fits(new RowLayout(600, 40, 40, 2), LayoutOrientation.Landscape), Is.True);    // 660
            Assert.That(ScreenLayout.Fits(new RowLayout(600, 50, 40, 2), LayoutOrientation.Landscape), Is.False);   // 670
            Assert.That(ScreenLayout.Fits(new RowLayout(600, 50, 40, 2), LayoutOrientation.Portrait), Is.True);
        }

        // Menu: WebGL'de 7 dugme (e2e adim 66 / dikey 78 bekler), masaustunde 8 ("Oyunu Kapat")
        [TestCase(7)]
        [TestCase(8)]
        public void MenuFitsInBothOrientations(int items)
        {
            foreach (var o in Both)
            {
                var m = ScreenLayout.Menu(items, o);
                Assert.That(m.Count, Is.EqualTo(items));
                Assert.That(ScreenLayout.Fits(m, o), Is.True, $"{o} {items} dugme: alt kenar {m.Bottom}");
                Assert.That(m.Step, Is.GreaterThan(m.Height), "dugmeler ust uste binmez");
            }
        }

        [Test]
        public void WebGLMenuKeepsE2ECoordinates()
        {
            var land = ScreenLayout.Menu(7, LayoutOrientation.Landscape);
            Assert.That(land.Center(0), Is.EqualTo(200f));
            Assert.That(land.Step, Is.EqualTo(66f));
            var port = ScreenLayout.Menu(7, LayoutOrientation.Portrait);
            Assert.That(port.Center(0), Is.EqualTo(340f));
            Assert.That(port.Step, Is.EqualTo(78f));
        }

        [Test]
        public void TournamentListFitsInBothOrientations()
        {
            foreach (var o in Both)
            {
                var r = ScreenLayout.TournamentList(o);
                Assert.That(r.Count, Is.GreaterThanOrEqualTo(6), o.ToString());
                Assert.That(ScreenLayout.Fits(r, o), Is.True, $"{o}: alt kenar {r.Bottom}");
                Assert.That(r.Step, Is.GreaterThanOrEqualTo(r.Height), o.ToString());
                // Ust: dugme satirinin altinda (yatay 110 +- 24, dikey 220 +- 26)
                float buttonsBottom = o == LayoutOrientation.Portrait ? 246f : 134f;
                Assert.That(r.Top, Is.GreaterThan(buttonsBottom), o.ToString());
            }
            // Dikeyde satir iki yazi satiri ve 48 px'lik dokunma hedefi tasir
            Assert.That(ScreenLayout.TournamentList(LayoutOrientation.Portrait).Height, Is.GreaterThanOrEqualTo(56f));
        }

        [Test]
        public void StandingsFitInBothOrientations()
        {
            foreach (var o in Both)
            {
                var r = ScreenLayout.Standings(o);
                Assert.That(r.Count, Is.GreaterThanOrEqualTo(8), o.ToString());
                Assert.That(ScreenLayout.Fits(r, o), Is.True, $"{o}: alt kenar {r.Bottom}");
                Assert.That(r.Step, Is.GreaterThanOrEqualTo(r.Height), o.ToString());
                // Ust: baslik satirinin (StandingsHeaderY +- 18) altinda
                Assert.That(r.Top, Is.GreaterThanOrEqualTo(ScreenLayout.StandingsHeaderY(o) + 18f), o.ToString());
            }
            // Dikeyde en kucuk yazi 18 pt: satir en az 40 px
            Assert.That(ScreenLayout.Standings(LayoutOrientation.Portrait).Height, Is.GreaterThanOrEqualTo(40f));
        }
    }
}
