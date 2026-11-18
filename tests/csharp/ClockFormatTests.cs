// Satranc saati gosterimi (Game/ClockFormat.cs): kalan saniye -> "m:ss".
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class ClockFormatTests
    {
        [TestCase(180, "3:00")]
        [TestCase(9, "0:09")]
        [TestCase(0, "0:00")]
        [TestCase(-3, "0:00")]
        [TestCase(61, "1:01")]
        [TestCase(182, "3:02")]
        [TestCase(600, "10:00")]
        public void FormatsMinutesAndSeconds(int seconds, string expected) =>
            Assert.That(ClockFormat.Format(seconds), Is.EqualTo(expected));
    }
}
