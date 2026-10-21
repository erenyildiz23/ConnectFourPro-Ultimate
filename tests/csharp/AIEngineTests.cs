// tests/unit/test_ai.py'nin C# karsiligi + Python motoruyla altin vektor karsilastirmasi.
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using ConnectFourPro.AI;
using ConnectFourPro.Core;
using ConnectFourPro.Net;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    internal static class AIHelpers
    {
        public const int Inf = AIEngine.WinScore * 2;

        public static (ulong cur, ulong mask) Bits(GameState g) => (g.GetBitboard(g.CurrentPlayer), g.Mask);

        public static GameState RandomPosition(Random rng, int n)
        {
            var g = new GameState();
            for (int i = 0; i < n && !g.GameOver; i++)
            {
                var moves = g.GetValidLocations();
                g.MakeMove(moves[rng.Next(moves.Count)]);
            }
            return g;
        }

        public static GameState LivePosition(Random rng, int n)
        {
            while (true)
            {
                var g = RandomPosition(rng, n);
                if (!g.GameOver && g.MoveCount == n && g.GetValidLocations().Count >= 2)
                    return g;
            }
        }

        /// <summary>Budamasiz, TT'siz, siralamasiz tam genislikte negamax (dugum kurallari motorla ayni).</summary>
        public static int ReferenceNegamax(ulong cur, ulong mask, int depth, int ply)
        {
            ulong possible = (mask + AIEngine.BottomMask) & AIEngine.BoardMask;
            if (possible == 0) return 0;
            if ((AIEngine.WinningCells(cur, mask) & possible) != 0) return AIEngine.WinScore - ply - 1;
            ulong oppWins = AIEngine.WinningCells(cur ^ mask, mask);
            ulong forced = possible & oppWins;
            if ((forced & (forced - 1)) != 0) return -(AIEngine.WinScore - ply - 2);
            if (forced != 0) possible = forced;
            ulong candidates = possible & ~(oppWins >> 1);
            if (candidates == 0) return -(AIEngine.WinScore - ply - 2);
            if (Board.PopCount(mask) >= Board.Size - 1) return 0;
            if (depth <= 0) return AIEngine.Evaluate(cur, mask);
            int best = int.MinValue;
            for (int col = 0; col < Board.Cols; col++)
            {
                ulong bit = candidates & (((1UL << Board.Rows) - 1) << (col * 7));
                if (bit != 0)
                    best = Math.Max(best, -ReferenceNegamax(cur ^ mask, mask | bit, depth - 1, ply + 1));
            }
            return best;
        }

        /// <summary>Sonuna kadar kaba kuvvet: sirasi gelen icin +1 / 0 / -1.</summary>
        public static int ExactValue(GameState g)
        {
            if (g.Winner != 0) return -1;
            var moves = g.GetValidLocations();
            if (moves.Count == 0) return 0;
            int best = -1;
            foreach (int col in moves)
            {
                var child = g.Clone();
                child.MakeMove(col);
                best = Math.Max(best, child.Winner != 0 ? 1 : -ExactValue(child));
                if (best == 1) break;
            }
            return best;
        }

        public static int? ShortestWin(GameState game)
        {
            bool Search(GameState g, int limit)
            {
                if (limit <= 0) return false;
                foreach (int col in g.GetValidLocations())
                {
                    var child = g.Clone();
                    child.MakeMove(col);
                    if (child.Winner != 0) return true;
                    if (limit >= 3 && child.GetValidLocations().All(reply =>
                        {
                            var r = child.Clone();
                            r.MakeMove(reply);
                            return r.Winner == 0 && r.GetValidLocations().Count > 0 && Search(r, limit - 2);
                        }))
                        return true;
                }
                return false;
            }
            for (int plies = 1; plies < 43; plies += 2)
                if (Search(game, plies))
                    return plies;
            return null;
        }

        public static List<int> WinningMoves(GameState g, int player)
        {
            var result = new List<int>();
            foreach (int col in g.GetValidLocations())
            {
                var c = g.Clone();
                c.CurrentPlayer = player;
                c.MakeMove(col);
                if (c.Winner == player) result.Add(col);
            }
            return result;
        }
    }

    public class AIBasicsTests
    {
        [Test]
        public void DifficultyLevels() =>
            Assert.That(AIEngine.Difficulties, Is.EqualTo(new[] { ("Kolay", 2), ("Orta", 4), ("Zor", 8) }));

        [Test]
        public void InvalidDepthRejected() => Assert.Throws<ArgumentException>(() => new AIEngine(2, depth: 0));

        [TestCase(1)] [TestCase(2)] [TestCase(4)] [TestCase(8)]
        public void AlwaysReturnsAValidMove(int depth)
        {
            var rng = new Random(depth);
            foreach (int n in new[] { 0, 5, 15, 30, 38 })
            {
                var g = AIHelpers.RandomPosition(rng, n);
                if (g.GameOver) continue;
                Assert.That(g.GetValidLocations(), Does.Contain(new AIEngine(g.CurrentPlayer, depth).FindBestMove(g)));
            }
        }

        [Test]
        public void FullBoardReturnsMinusOne() =>
            Assert.That(new AIEngine(1, 3).FindBestMove(GameState.FromMoves(Fixtures.DrawSequence)), Is.EqualTo(-1));

        [Test]
        public void DoesNotModifyInputGame()
        {
            var g = GameState.FromMoves(new[] { 3, 3, 2 });
            string before = g + "|" + string.Join(",", g.MoveHistory) + g.CurrentPlayer;
            new AIEngine(2, 6).FindBestMove(g);
            Assert.That(g + "|" + string.Join(",", g.MoveHistory) + g.CurrentPlayer, Is.EqualTo(before));
        }

        [Test]
        public void SeededTieBreakingIsReproducible()
        {
            var g = GameState.FromMoves(new[] { 0, 6, 1 });
            Assert.That(new AIEngine(2, 4, seed: 7).FindBestMove(g), Is.EqualTo(new AIEngine(2, 4, seed: 7).FindBestMove(g)));
        }
    }

    public class AICancellationTests
    {
        [Test]
        public void CancelledSearchReturnsImmediately()
        {
            var ai = new AIEngine(2, 8, useOpeningBook: false);
            Assert.That(ai.FindBestMove(GameState.FromMoves(new[] { 3, 3, 2, 4, 1 }), () => true), Is.EqualTo(-1));
            Assert.That(ai.NodesEvaluated, Is.LessThanOrEqualTo(1));
        }

        [Test]
        public void CancelStopsRunningSearch()
        {
            var ai = new AIEngine(2, 16, useOpeningBook: false, exactEndgame: false);
            long calls = 0;
            Assert.That(ai.FindBestMove(new GameState(), () => ++calls > 5000), Is.EqualTo(-1));
            Assert.That(calls, Is.LessThan(5010));
        }

        [Test]
        public void EngineIsReusableAfterCancel()
        {
            var ai = new AIEngine(2, 4, useOpeningBook: false);
            var g = GameState.FromMoves(new[] { 3, 3, 2, 4, 1 });
            Assert.That(ai.FindBestMove(g, () => true), Is.EqualTo(-1));
            Assert.That(g.GetValidLocations(), Does.Contain(ai.FindBestMove(g)));
        }

        [Test]
        public void StepwiseSearchMatchesSynchronousSearch()
        {
            var g = GameState.FromMoves(new[] { 3, 2, 4, 4, 1, 5 });
            var sync = new AIEngine(1, 8, useOpeningBook: false);
            int expected = sync.FindBestMove(g);
            var stepped = new AIEngine(1, 8, useOpeningBook: false);
            var search = stepped.BeginSearch(g);
            int steps = 0;
            while (!search.Step()) steps++;
            Assert.That(search.Result, Is.EqualTo(expected));
            Assert.That(stepped.NodesEvaluated, Is.EqualTo(sync.NodesEvaluated));
            Assert.That(steps, Is.GreaterThan(1), "arama tek adimda bitmemeli (kare bolme)");
        }

        [Test]
        public void SearchCancelReturnsMinusOne()
        {
            var search = new AIEngine(1, 8, useOpeningBook: false).BeginSearch(GameState.FromMoves(new[] { 3, 2, 4 }));
            search.Step();
            search.Cancel();
            Assert.That(search.Done && search.Cancelled && search.Result == -1);
        }
    }

    public class AIOpeningBookTests
    {
        [Test]
        public void BookCoversFirstTwoPlies()
        {
            var entries = OpeningBook.Entries().ToList();
            Assert.That(entries.Count, Is.EqualTo(OpeningBook.Count));
            foreach (var (history, move) in entries)
                Assert.That(GameState.FromMoves(history).IsValidLocation(move));
        }

        [Test]
        public void BookMoveOnEmptyBoardIsCenter()
        {
            var ai = new AIEngine(1, 8);
            Assert.That(ai.FindBestMove(new GameState()), Is.EqualTo(3));
            Assert.That(ai.LastMoveFromBook && ai.NodesEvaluated == 0);
        }

        [Test]
        public void BookCanBeDisabled()
        {
            var ai = new AIEngine(1, 2, useOpeningBook: false);
            ai.FindBestMove(new GameState());
            Assert.That(!ai.LastMoveFromBook && ai.NodesEvaluated > 0);
        }
    }

    public class AITacticsTests
    {
        private static IEnumerable<TestCaseData> ImmediateWins()
        {
            foreach (int depth in new[] { 1, 2, 4, 8 })
            {
                yield return new TestCaseData(new[] { 3, 0, 3, 1, 3, 2 }, 3, depth);
                yield return new TestCaseData(new[] { 0, 0, 1, 1, 2, 2 }, 3, depth);
                yield return new TestCaseData(new[] { 1, 1, 2, 2, 3, 3 }, -1, depth);
                yield return new TestCaseData(new[] { 0, 1, 1, 2, 2, 3, 2, 3, 3, 6 }, 3, depth);
            }
        }

        [TestCaseSource(nameof(ImmediateWins))]
        public void TakesImmediateWin(int[] moves, int expected, int depth)
        {
            var g = GameState.FromMoves(moves);
            var wins = AIHelpers.WinningMoves(g, g.CurrentPlayer);
            Assert.That(wins, Is.Not.Empty);
            if (expected >= 0) Assert.That(wins, Does.Contain(expected));
            Assert.That(wins, Does.Contain(new AIEngine(g.CurrentPlayer, depth, useOpeningBook: false).FindBestMove(g)));
        }

        private static IEnumerable<TestCaseData> Blocks()
        {
            foreach (int depth in new[] { 1, 2, 4, 8 })
            {
                yield return new TestCaseData(new[] { 0, 3, 1, 3, 6, 3 }, 3, depth);
                yield return new TestCaseData(new[] { 6, 0, 6, 1, 5, 2 }, 3, depth);
                yield return new TestCaseData(new[] { 4, 0, 2, 3, 6, 5, 1, 2, 3, 4, 1, 5, 2, 2, 5, 4 }, 3, depth);
            }
        }

        [TestCaseSource(nameof(Blocks))]
        public void BlocksSingleOpponentThreat(int[] moves, int threat, int depth)
        {
            var g = GameState.FromMoves(moves);
            int me = g.CurrentPlayer;
            Assert.That(AIHelpers.WinningMoves(g, 3 - me), Is.EqualTo(new[] { threat }));
            Assert.That(new AIEngine(me, depth, useOpeningBook: false).FindBestMove(g), Is.EqualTo(threat));
        }

        [TestCase(1)] [TestCase(2)] [TestCase(4)]
        public void PrefersOwnWinOverBlocking(int depth) =>
            Assert.That(new AIEngine(1, depth, useOpeningBook: false).FindBestMove(GameState.FromMoves(new[] { 0, 6, 0, 6, 0, 6 })), Is.EqualTo(0));

        [TestCase(3)] [TestCase(4)] [TestCase(8)]
        public void CreatesDoubleThreat(int depth)
        {
            var g = GameState.FromMoves(new[] { 4, 0, 3, 1, 1, 6, 3, 1, 4, 6 });
            Assert.That(new[] { 2, 5 }, Does.Contain(new AIEngine(g.CurrentPlayer, depth, useOpeningBook: false).FindBestMove(g)));
        }

        [Test]
        public void ForcedWinDistanceIsExact()
        {
            var g = GameState.FromMoves(new[] { 4, 0, 3, 1, 1, 6, 3, 1, 4, 6 });
            var ai = new AIEngine(g.CurrentPlayer, 8, useOpeningBook: false);
            ai.FindBestMove(g);
            Assert.That(ai.LastScore, Is.EqualTo(AIEngine.WinScore - 3));
        }
    }

    public class AISearchCorrectnessTests
    {
        [TestCase(0)] [TestCase(1)] [TestCase(2)] [TestCase(3)]
        public void WinningCellsMatchBruteForce(int seed)
        {
            var rng = new Random(seed);
            for (int n = 4; n < 36; n += 4)
            {
                var g = AIHelpers.RandomPosition(rng, n);
                if (g.GameOver) continue;
                var (cur, mask) = AIHelpers.Bits(g);
                ulong expected = 0;
                for (int c = 0; c < 7; c++)
                    for (int r = 0; r < 6; r++)
                    {
                        ulong bit = 1UL << (c * 7 + r);
                        if ((mask & bit) == 0 && AIEngine.HasFour(cur | bit)) expected |= bit;
                    }
                Assert.That(AIEngine.WinningCells(cur, mask), Is.EqualTo(expected));
            }
        }

        [Test]
        public void HasFourDoesNotWrapAcrossColumnsOrRows()
        {
            Assert.That(AIEngine.HasFour((1UL << 3) | (1UL << 4) | (1UL << 5) | (1UL << 7)), Is.False);
            Assert.That(AIEngine.HasFour((1UL << 40) | (1UL << 47) | (1UL << 4) | (1UL << 11)), Is.False);
        }

        [Test, Combinatorial]
        public void AlphaBetaWithTTMatchesFullWidthNegamax([Range(0, 7)] int seed)
        {
            var rng = new Random(100 + seed);
            var g = AIHelpers.LivePosition(rng, rng.Next(2, 25));
            var (cur, mask) = AIHelpers.Bits(g);
            var engine = new AIEngine(g.CurrentPlayer, 4, useOpeningBook: false, exactEndgame: false);
            int expected = AIHelpers.ReferenceNegamax(cur, mask, 4, 0);
            engine.ClearTranspositionTable();
            Assert.That(engine.Negamax(cur, mask, 4, -AIHelpers.Inf, AIHelpers.Inf, 0), Is.EqualTo(expected));
        }

        [Test, Combinatorial]
        public void WindowSemanticsWithSharedTranspositionTable([Range(0, 5)] int seed)
        {
            var rng = new Random(400 + seed);
            var g = AIHelpers.LivePosition(rng, rng.Next(2, 11));
            var (cur, mask) = AIHelpers.Bits(g);
            var engine = new AIEngine(g.CurrentPlayer, 5, useOpeningBook: false, exactEndgame: false);
            int truth = AIHelpers.ReferenceNegamax(cur, mask, 5, 0);
            engine.ClearTranspositionTable();
            var windows = new[]
            {
                (truth - 1, truth), (truth, truth + 1), (truth - 1, truth + 1), (truth + 1, truth + 2),
                (truth - 2, truth - 1), (-AIHelpers.Inf, truth - 5), (truth + 5, AIHelpers.Inf), (truth - 50, truth + 50),
            };
            for (int rep = 0; rep < 3; rep++)
                foreach (var (alpha, beta) in windows)
                {
                    int result = engine.Negamax(cur, mask, 5, alpha, beta, 0);
                    if (truth <= alpha) Assert.That(result, Is.LessThanOrEqualTo(alpha));
                    else if (truth >= beta) Assert.That(result, Is.GreaterThanOrEqualTo(beta));
                    else Assert.That(result, Is.EqualTo(truth));
                }
        }

        [Test, Combinatorial]
        public void WinDistanceMatchesBruteForce([Range(0, 3)] int seed)
        {
            var rng = new Random(600 + seed);
            GameState g;
            int? shortest;
            while (true)
            {
                g = AIHelpers.LivePosition(rng, 30);
                if (AIHelpers.ExactValue(g) == 1 && (shortest = AIHelpers.ShortestWin(g)) >= 5) break;
            }
            var engine = new AIEngine(g.CurrentPlayer, 2, useOpeningBook: false);
            var (cur, mask) = AIHelpers.Bits(g);
            int value = engine.Negamax(cur, mask, Board.Size - g.MoveCount, -AIHelpers.Inf, AIHelpers.Inf, 0);
            Assert.That(value, Is.EqualTo(AIEngine.WinScore - shortest.Value));
        }

        [Test]
        public void LastEmptyCellIsADrawAtHorizon()
        {
            var g = GameState.FromMoves(Fixtures.DrawSequence.Take(41));
            var (cur, mask) = AIHelpers.Bits(g);
            Assert.That(new AIEngine(g.CurrentPlayer, 1, useOpeningBook: false).Negamax(cur, mask, 0, -AIHelpers.Inf, AIHelpers.Inf, 0), Is.EqualTo(0));
        }

        [Test, Combinatorial]
        public void ExactEndgameMatchesBruteForce([Range(0, 9)] int seed)
        {
            var rng = new Random(300 + seed);
            var g = AIHelpers.LivePosition(rng, 32);
            int truth = AIHelpers.ExactValue(g);
            int move = new AIEngine(g.CurrentPlayer, 2, useOpeningBook: false, exactEndgame: true).FindBestMove(g);
            var child = g.Clone();
            child.MakeMove(move);
            Assert.That(child.Winner != 0 ? 1 : -AIHelpers.ExactValue(child), Is.EqualTo(truth));
        }

        [Test]
        public void AIvsAIProducesLegalCompleteGame()
        {
            var g = new GameState();
            var players = new Dictionary<int, AIEngine> { [1] = new AIEngine(1, 4), [2] = new AIEngine(2, 2) };
            while (!g.GameOver)
                Assert.That(g.MakeMove(players[g.CurrentPlayer].FindBestMove(g)));
        }

        [Test]
        public void DeeperSearchBeatsShallow()
        {
            foreach (int first in new[] { 1, 2 })
            {
                var deep = new AIEngine(first, 6);
                var shallow = new AIEngine(3 - first, 1);
                var g = new GameState();
                while (!g.GameOver)
                    g.MakeMove((g.CurrentPlayer == first ? deep : shallow).FindBestMove(g));
                Assert.That(new[] { first, 0 }, Does.Contain(g.Winner));
            }
        }

        [Test]
        public void ThreatParityMasks()
        {
            Assert.That(AIEngine.ThreatGood, Is.GreaterThan(AIEngine.ThreatOther));
            Assert.That((AIEngine.RowsOdd & 1) != 0 && (AIEngine.RowsEven & 1) == 0);
            Assert.That(AIEngine.RowsOdd | AIEngine.RowsEven, Is.EqualTo(AIEngine.BoardMask));
            Assert.That(AIEngine.RowsOdd & AIEngine.RowsEven, Is.EqualTo(0UL));
        }

        [Test]
        public void CenterIsPreferred()
        {
            var (c1, m1) = AIHelpers.Bits(GameState.FromMoves(new[] { 3 }));
            var (c2, m2) = AIHelpers.Bits(GameState.FromMoves(new[] { 0 }));
            Assert.That(-AIEngine.Evaluate(c1, m1), Is.GreaterThan(-AIEngine.Evaluate(c2, m2)));
        }
    }

    /// <summary>
    /// scripts/export_ai_vectors.py ile Python motorundan uretilen sonuclar.
    /// Dugum ve budama sayilarinin da tutmasi, arama agacinin birebir ayni oldugunu gosterir.
    /// </summary>
    public class GoldenVectorTests
    {
        private static JsonObject Load()
        {
            string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "vectors", "ai_vectors.json");
            return JsonObject.ParseObject(File.ReadAllText(path));
        }

        [Test]
        public void SearchesMatchPythonEngine()
        {
            var searches = Load().GetObjectList("searches");
            Assert.That(searches.Count, Is.GreaterThan(50));
            foreach (var s in searches)
            {
                var g = GameState.FromMoves(s.GetIntList("moves"));
                bool? exact = s.IsNull("exact") ? (bool?)null : s.GetBool("exact");
                var ai = new AIEngine(g.CurrentPlayer, s.GetInt("depth"), s.GetBool("book"), exact);
                int move = ai.FindBestMove(g);
                string ctx = $"moves=[{string.Join(",", g.MoveHistory)}] depth={s.GetInt("depth")}";
                Assert.That(move, Is.EqualTo(s.GetInt("best")), ctx);
                Assert.That(ai.LastScore, Is.EqualTo(s.GetNullableInt("score")), ctx);
                Assert.That(ai.LastDepthReached, Is.EqualTo(s.GetInt("depth_reached")), ctx);
                Assert.That(ai.NodesEvaluated, Is.EqualTo(s.GetLong("nodes")), ctx);
                Assert.That(ai.Cutoffs, Is.EqualTo(s.GetLong("cutoffs")), ctx);
                Assert.That(ai.LastMoveFromBook, Is.EqualTo(s.GetBool("from_book")), ctx);
            }
        }

        [Test]
        public void EvaluationsMatchPythonEngine()
        {
            foreach (var e in Load().GetObjectList("evals"))
            {
                var g = GameState.FromMoves(e.GetIntList("moves"));
                var (cur, mask) = AIHelpers.Bits(g);
                Assert.That(AIEngine.Evaluate(cur, mask), Is.EqualTo(e.GetInt("eval")));
                Assert.That(AIEngine.WinningCells(cur, mask), Is.EqualTo(ulong.Parse(e.GetString("threats"))));
                Assert.That(AIEngine.WinningCells(cur ^ mask, mask), Is.EqualTo(ulong.Parse(e.GetString("opp_threats"))));
            }
        }
    }
}
