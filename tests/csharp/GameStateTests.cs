// tests/unit/test_game_core.py'nin C# karsiligi.
using System.Collections.Generic;
using System.Linq;
using ConnectFourPro.Core;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public static class Fixtures
    {
        public static readonly int[] DrawSequence =
        {
            3, 4, 4, 6, 0, 3, 5, 2, 6, 5, 0, 6, 5, 0, 3, 6, 5, 6, 1, 3, 1, 3, 6, 5, 2, 0,
            5, 3, 4, 4, 0, 1, 1, 1, 0, 1, 4, 2, 4, 2, 2, 2,
        };

        public static readonly int[] P1VerticalWin = { 0, 1, 0, 1, 0, 1, 0 };
    }

    public class GameStateTests
    {
        [Test]
        public void NewGameIsEmptyAndPlaying()
        {
            var g = new GameState();
            Assert.That(g.CurrentPlayer, Is.EqualTo(Board.Player1));
            Assert.That(g.Status, Is.EqualTo(GameStatus.Playing));
            Assert.That(g.GameOver, Is.False);
            Assert.That(g.Winner, Is.EqualTo(0));
            Assert.That(g.GetValidLocations(), Is.EqualTo(Enumerable.Range(0, 7)));
        }

        [Test]
        public void CustomStartingPlayer() => Assert.That(new GameState(Board.Player2).CurrentPlayer, Is.EqualTo(2));

        [Test]
        public void PieceFallsAndTurnAlternates()
        {
            var g = new GameState();
            Assert.That(g.MakeMove(3));
            Assert.That(g.GetCell(3, 0), Is.EqualTo(Board.Player1));
            Assert.That(g.CurrentPlayer, Is.EqualTo(Board.Player2));
            Assert.That(g.MakeMove(3));
            Assert.That(g.GetCell(3, 1), Is.EqualTo(Board.Player2));
            Assert.That(g.MoveHistory, Is.EqualTo(new[] { 3, 3 }));
            Assert.That(g.NextRow(3), Is.EqualTo(2));
        }

        [Test]
        public void FullColumnIsRejected()
        {
            var g = GameState.FromMoves(Enumerable.Repeat(2, 6));
            Assert.That(g.IsValidLocation(2), Is.False);
            Assert.That(g.MakeMove(2), Is.False);
            Assert.That(g.MoveCount, Is.EqualTo(6));
        }

        [TestCase(-1)]
        [TestCase(7)]
        [TestCase(99)]
        public void InvalidColumnsAreRejected(int col)
        {
            var g = new GameState();
            Assert.That(g.MakeMove(col), Is.False);
            Assert.That(g.MoveCount, Is.EqualTo(0));
        }

        [Test]
        public void NoMovesAfterGameOver()
        {
            var g = GameState.FromMoves(Fixtures.P1VerticalWin);
            Assert.That(g.GameOver);
            Assert.That(g.MakeMove(5), Is.False);
        }

        [Test]
        public void FromMovesThrowsOnIllegalSequence() =>
            Assert.Throws<System.ArgumentException>(() => GameState.FromMoves(Enumerable.Repeat(0, 7)));

        private static IEnumerable<TestCaseData> WinCases()
        {
            yield return new TestCaseData(new[] { 0, 1, 0, 1, 0, 1, 0 }, new[] { (0, 0), (0, 1), (0, 2), (0, 3) }).SetName("vertical");
            yield return new TestCaseData(new[] { 0, 0, 1, 1, 2, 2, 3 }, new[] { (0, 0), (1, 0), (2, 0), (3, 0) }).SetName("horizontal");
            yield return new TestCaseData(new[] { 0, 1, 1, 2, 2, 3, 2, 3, 3, 6, 3 }, new[] { (0, 0), (1, 1), (2, 2), (3, 3) }).SetName("diagonal_up");
            yield return new TestCaseData(new[] { 3, 2, 2, 1, 1, 0, 1, 0, 0, 6, 0 }, new[] { (0, 3), (1, 2), (2, 1), (3, 0) }).SetName("diagonal_down");
        }

        [TestCaseSource(nameof(WinCases))]
        public void FourInARowWins(int[] moves, (int, int)[] expected)
        {
            var g = GameState.FromMoves(moves);
            Assert.That(g.GameOver && g.Status == GameStatus.Win);
            Assert.That(g.Winner, Is.EqualTo(Board.Player1));
            Assert.That(g.GetWinningPositions().Select(p => (p.col, p.row)), Is.EquivalentTo(expected));
        }

        [Test]
        public void PlayerTwoCanWin()
        {
            var g = GameState.FromMoves(new[] { 0, 1, 0, 1, 0, 1, 6, 1 });
            Assert.That(g.Winner, Is.EqualTo(Board.Player2));
        }

        [Test]
        public void ThreeInARowIsNotAWin() => Assert.That(GameState.FromMoves(new[] { 0, 1, 0, 1, 0 }).GameOver, Is.False);

        [Test]
        public void FullBoardWithoutWinnerIsDraw()
        {
            var g = GameState.FromMoves(Fixtures.DrawSequence);
            Assert.That(g.GameOver && g.Status == GameStatus.Draw);
            Assert.That(g.Winner, Is.EqualTo(0));
            Assert.That(g.GetValidLocations(), Is.Empty);
            Assert.That(g.GetWinningPositions(), Is.Empty);
        }

        [Test]
        public void CloneIsIndependent()
        {
            var g = GameState.FromMoves(new[] { 3, 4 });
            var c = g.Clone();
            c.MakeMove(0);
            Assert.That(g.MoveHistory, Is.EqualTo(new[] { 3, 4 }));
            Assert.That(c.MoveHistory, Is.EqualTo(new[] { 3, 4, 0 }));
            Assert.That(g.CurrentPlayer, Is.EqualTo(Board.Player1));
        }

        [Test]
        public void ToStringShowsPieces()
        {
            string text = GameState.FromMoves(new[] { 3, 3 }).ToString();
            Assert.That(text.Count(ch => ch == 'X'), Is.EqualTo(1));
            Assert.That(text.Count(ch => ch == 'O'), Is.EqualTo(1));
        }
    }
}
