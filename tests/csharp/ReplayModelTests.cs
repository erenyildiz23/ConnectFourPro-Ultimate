// ReplayModel (tekrar ekraninin saf mantigi) testleri.
using System.Linq;
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class ReplayModelTests
    {
        private static ReplayModel Make(params int[] moves) => new ReplayModel(moves, "A", "B", "sonuc");

        [Test]
        public void StartsAtZeroWithEmptyBoard()
        {
            var m = Make(3, 3, 4);
            Assert.That(m.Index, Is.EqualTo(0));
            Assert.That(m.Count, Is.EqualTo(3));
            Assert.That(m.Playing, Is.False);
            Assert.That(m.State.MoveHistory, Is.Empty);
        }

        [Test]
        public void NextAndPrevClampToBounds()
        {
            var m = Make(3, 3, 4);
            for (int i = 0; i < 5; i++) m.Next();
            Assert.That(m.Index, Is.EqualTo(3));
            for (int i = 0; i < 5; i++) m.Prev();
            Assert.That(m.Index, Is.EqualTo(0));
        }

        [Test]
        public void StateMatchesPrefix()
        {
            var m = Make(3, 3, 4);
            m.Next(); m.Next();
            Assert.That(m.State.MoveHistory.ToArray(), Is.EqualTo(new[] { 3, 3 }));
        }

        [Test]
        public void FirstAndLastJump()
        {
            var m = Make(3, 3, 4);
            m.Last();
            Assert.That(m.Index, Is.EqualTo(3));
            m.First();
            Assert.That(m.Index, Is.EqualTo(0));
        }

        [Test]
        public void TickAdvancesEveryStepWhilePlaying()
        {
            var m = Make(0, 1, 2, 3, 4);
            m.TogglePlay();
            m.Tick(0.79f);
            Assert.That(m.Index, Is.EqualTo(0));
            m.Tick(0.02f);
            Assert.That(m.Index, Is.EqualTo(1));
            m.Tick(1.6f);
            Assert.That(m.Index, Is.EqualTo(3));
        }

        [Test]
        public void TickDoesNothingWhenPaused()
        {
            var m = Make(0, 1, 2);
            m.Tick(5f);
            Assert.That(m.Index, Is.EqualTo(0));
        }

        [Test]
        public void PlayingStopsAtEnd()
        {
            var m = Make(0, 1);
            m.TogglePlay();
            m.Tick(10f);
            Assert.That(m.Index, Is.EqualTo(2));
            Assert.That(m.Playing, Is.False);
        }

        [Test]
        public void TogglePlayAtEndRestartsFromZero()
        {
            var m = Make(0, 1);
            m.Last();
            m.TogglePlay();
            Assert.That(m.Index, Is.EqualTo(0));
            Assert.That(m.Playing, Is.True);
        }

        [Test]
        public void ManualNavigationPausesPlayback()
        {
            var m = Make(0, 1, 2);
            m.TogglePlay();
            m.Next();
            Assert.That(m.Playing, Is.False);
        }
    }
}
