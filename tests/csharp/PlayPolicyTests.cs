// Aramadan sonra uygulanan istemci politikalari (AI/PlayPolicies.cs): Kolay seviyesinin
// hatalari (SlipPolicy) ve isabet kumesi (MoveAnalysis). Altin vektorler Python
// istemcisinden (src/gui_app.py) uretilir: scripts/export_slip_vectors.py,
// scripts/export_analysis_vectors.py.
using System.Collections.Generic;
using System.IO;
using ConnectFourPro.AI;
using ConnectFourPro.Core;
using ConnectFourPro.Net;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class SlipPolicyTests
    {
        private static readonly int[] Cycle = BuildCycle();

        private static int[] BuildCycle()
        {
            var c = new int[20];
            for (int i = 0; i < c.Length; i++)
                c[i] = i % 7;      // kazanani olmayan 20 hamlelik gecerli dizi
            return c;
        }

        private static GameState Prefix(int ply) => GameState.FromMoves(new List<int>(Cycle).GetRange(0, ply));

        private static JsonObject Load()
        {
            string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "vectors", "slip_vectors.json");
            return JsonObject.ParseObject(File.ReadAllText(path));
        }

        [Test]
        public void Fmix32IsTheMurmur3Finalizer()
        {
            Assert.That(SlipPolicy.Fmix32(0), Is.EqualTo(0u));
            Assert.That(SlipPolicy.Fmix32(1), Is.EqualTo(0x514E28B7u));
        }

        [Test]
        public void ReproducesEveryPythonVector()
        {
            var data = Load();
            Assert.That(data.GetObject("slip_permille").GetInt("2"), Is.EqualTo(SlipPolicy.Permille(2)));
            foreach (var f in data.GetObjectList("fmix32"))
                Assert.That(SlipPolicy.Fmix32((uint)f.GetLong("in")), Is.EqualTo((uint)f.GetLong("out")), "fmix32");

            var cases = data.GetObjectList("cases");
            Assert.That(cases.Count, Is.GreaterThan(300));
            int slips = 0, wins = 0, full = 0, aiStart = 0;
            foreach (var c in cases)
            {
                var g = GameState.FromMoves(c.GetIntList("moves"), c.GetInt("start"));
                int depth = c.GetInt("depth");
                uint seed = (uint)c.GetLong("seed");
                int col = SlipPolicy.SlipMove(g, depth, seed);
                string ctx = $"moves=[{string.Join(",", g.MoveHistory)}] start={c.GetInt("start")} depth={depth} seed={seed}";
                Assert.That(col >= 0, Is.EqualTo(c.GetBool("slip")), ctx);
                Assert.That(col, Is.EqualTo(c.GetInt("col")), ctx);
                if (col >= 0)
                {
                    slips++;
                    Assert.That(g.IsValidLocation(col), ctx);
                    if (g.GetValidLocations().Count < Board.Cols)
                        full++;
                    if (c.GetInt("start") == Board.Player2)
                        aiStart++;
                }
                if (c.GetBool("immediate_win"))
                {
                    wins++;
                    Assert.That(col, Is.EqualTo(-1), "kazanan hamle varken hata yok: " + ctx);
                }
            }
            // Vektor kumesi gercekten ilginc durumlari kapsiyor
            Assert.That(slips, Is.GreaterThan(50));
            Assert.That(wins, Is.GreaterThan(20));
            Assert.That(full, Is.GreaterThan(5));
            Assert.That(aiStart, Is.GreaterThan(5));
        }

        [Test]
        public void OnlyKolaySlipsAtAboutFortyPercent()
        {
            var game = Prefix(3);
            foreach (int depth in new[] { 1, 3, 4, 8 })
                for (uint seed = 0; seed < 300; seed++)
                    Assert.That(SlipPolicy.SlipMove(game, depth, seed), Is.EqualTo(-1));
            int slips = 0;
            for (uint seed = 0; seed < 2000; seed++)
                if (SlipPolicy.SlipMove(game, 2, seed) >= 0)
                    slips++;
            Assert.That(slips, Is.InRange(720, 880));
        }

        [Test]
        public void SlipsAreValidSpreadAndPure()
        {
            var game = GameState.FromMoves(new[] { 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1 });   // 0 ve 1 dolu
            var cols = new HashSet<int>();
            for (uint seed = 0; seed < 400; seed++)
            {
                int col = SlipPolicy.SlipMove(game, 2, seed);
                Assert.That(SlipPolicy.SlipMove(game.Clone(), 2, seed), Is.EqualTo(col));
                if (col >= 0)
                {
                    Assert.That(game.IsValidLocation(col));
                    cols.Add(col);
                }
            }
            Assert.That(cols, Is.EquivalentTo(new[] { 2, 3, 4, 5, 6 }));
        }

        [Test]
        public void NeverSkipsItsOwnWinAndNotAfterGameOver()
        {
            var game = GameState.FromMoves(new[] { 0, 6, 1, 6, 2, 6, 5 });   // sari sirada, 6'da kazanir
            for (uint seed = 0; seed < 500; seed++)
                Assert.That(SlipPolicy.SlipMove(game, 2, seed), Is.EqualTo(-1));
            var quiet = GameState.FromMoves(new[] { 0, 6, 1, 6, 2, 3, 5 });
            bool any = false;
            for (uint seed = 0; seed < 50 && !any; seed++)
                any = SlipPolicy.SlipMove(quiet, 2, seed) >= 0;
            Assert.That(any, "kazanc yokken ayni tohumlar hata yapar");

            var over = GameState.FromMoves(new[] { 0, 1, 0, 1, 0, 1, 0 });
            Assert.That(over.GameOver);
            Assert.That(SlipPolicy.SlipMove(over, 2, 0), Is.EqualTo(-1));
        }

        [Test]
        public void ApplyKeepsSearchResultWithoutSlipOrResult()
        {
            var game = GameState.FromMoves(new[] { 0 });
            uint calm = 0, slip = 0;
            while (SlipPolicy.SlipMove(game, 2, calm) >= 0) calm++;
            while (SlipPolicy.SlipMove(game, 2, slip) < 0) slip++;
            Assert.That(SlipPolicy.Apply(game, 2, calm, 3), Is.EqualTo(3));
            Assert.That(SlipPolicy.Apply(game, 2, slip, 3), Is.EqualTo(SlipPolicy.SlipMove(game, 2, slip)));
            Assert.That(SlipPolicy.Apply(game, 2, slip, -1), Is.EqualTo(-1));
            Assert.That(SlipPolicy.Apply(game, 4, slip, 3), Is.EqualTo(3));
        }
    }

    public class MoveAnalysisTests
    {
        private static JsonObject Load()
        {
            string path = Path.Combine(TestContext.CurrentContext.TestDirectory, "vectors", "analysis_vectors.json");
            return JsonObject.ParseObject(File.ReadAllText(path));
        }

        [Test]
        public void ReproducesEveryPythonBestColumnsVector()
        {
            var data = Load();
            Assert.That(data.GetInt("analysis_depth"), Is.EqualTo(Game.AppController.AnalysisDepth));
            var cases = data.GetObjectList("cases");
            Assert.That(cases.Count, Is.GreaterThan(150));
            int multi = 0;
            foreach (var c in cases)
            {
                var g = GameState.FromMoves(c.GetIntList("moves"));
                var best = MoveAnalysis.BestColumns(g, c.GetInt("depth"));
                string ctx = $"moves=[{string.Join(",", g.MoveHistory)}] depth={c.GetInt("depth")}";
                Assert.That(best, Is.EqualTo(c.GetIntList("best")), ctx);
                if (best.Count > 1)
                    multi++;
            }
            Assert.That(multi, Is.GreaterThan(10));
        }

        [Test]
        public void EqualWinsBookMoveForcedBlockAndCancel()
        {
            Assert.That(MoveAnalysis.BestColumns(GameState.FromMoves(new[] { 2, 2, 3, 3, 4, 4 }), 2), Is.EqualTo(new[] { 1, 5 }));
            var book = MoveAnalysis.BestColumns(GameState.FromMoves(new[] { 1 }), Game.AppController.AnalysisDepth);
            Assert.That(book, Does.Contain(2).And.Contain(3));
            Assert.That(MoveAnalysis.BestColumns(GameState.FromMoves(new[] { 0, 6, 1, 6, 2 }), 2), Is.EqualTo(new[] { 3 }));
            Assert.That(MoveAnalysis.BestColumns(new GameState(), 2, () => true), Is.Null);
        }

        [Test]
        public void SearchResultIsAlwaysOneOfTheColumns()
        {
            foreach (var moves in new[] { new int[0], new[] { 3 }, new[] { 3, 3, 2 }, new[] { 0, 1, 2, 3, 4 } })
            {
                var g = GameState.FromMoves(moves);
                var best = MoveAnalysis.BestColumns(g, 3);
                int chosen = new AIEngine(g.CurrentPlayer, 3, useOpeningBook: false).FindBestMove(g);
                Assert.That(best, Does.Contain(chosen));
                Assert.That(best, Is.Ordered);
            }
        }

        [Test]
        public void ReadingRootResultsLeavesTheSearchUntouched()
        {
            // Analiz ayni motoru kullanir: hamle, skor ve dugum sayilari normal aramayla ayni
            foreach (var moves in new[] { new[] { 3, 3, 2 }, new[] { 0, 1, 2, 3, 4 }, new[] { 2, 2, 3, 3, 4, 4 } })
            {
                var g = GameState.FromMoves(moves);
                var plain = new AIEngine(g.CurrentPlayer, 6, useOpeningBook: false);
                int col = plain.FindBestMove(g);
                var engine = MoveAnalysis.NewEngine(g, 6);
                var search = engine.BeginSearch(g);
                while (!search.Step())
                {
                }
                var best = MoveAnalysis.FromSearch(g, engine, search);
                Assert.That(search.Result, Is.EqualTo(col));
                Assert.That(engine.LastScore, Is.EqualTo(plain.LastScore));
                Assert.That(engine.NodesEvaluated, Is.EqualTo(plain.NodesEvaluated));
                Assert.That(engine.Cutoffs, Is.EqualTo(plain.Cutoffs));
                Assert.That(best, Does.Contain(col));
            }
        }
    }
}
