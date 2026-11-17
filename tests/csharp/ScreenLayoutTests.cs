// Ekran yonu secimi ve portre sabitleri (Game/ScreenLayout.cs).
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class ScreenLayoutTests
    {
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
    }
}
