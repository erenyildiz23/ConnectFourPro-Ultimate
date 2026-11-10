// AI zamanlayici (Game/AIRunner.cs): aramalar Tick ile ilerler. Saat gercek
// (Stopwatch) oldugundan testler sonuc gelene kadar Tick cagirir.
using System;
using System.Diagnostics;
using ConnectFourPro.AI;
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class AIRunnerTests
    {
        // P1 0. sutunda uc tas dizdi; P2 kapatmak zorunda
        private static readonly int[] MustBlockColumn0 = { 0, 1, 0, 1, 0 };

        internal static bool TickUntil(Action tick, Func<bool> done, double timeoutSeconds = 20)
        {
            var clock = Stopwatch.StartNew();
            while (!done())
            {
                if (clock.Elapsed.TotalSeconds > timeoutSeconds)
                    return false;
                tick();
            }
            return true;
        }

        [Test]
        public void MoveSearchDeliversEngineMove()
        {
            var game = GameState.FromMoves(MustBlockColumn0);
            int expected = new AIEngine(Board.Player2, 3).FindBestMove(game.Clone());
            Assert.That(expected, Is.EqualTo(0));

            var runner = new AIRunner();
            int result = -99;
            runner.RequestMove(new AIEngine(Board.Player2, 3), game, 0, col => result = col);
            Assert.That(runner.IsThinking, Is.True);
            Assert.That(TickUntil(runner.Tick, () => result != -99), "AI hamlesi gelmedi");
            Assert.That(result, Is.EqualTo(expected));
            Assert.That(runner.IsThinking, Is.False);
        }

        [Test]
        public void SearchWaitsForDelay()
        {
            var runner = new AIRunner();
            bool called = false;
            runner.RequestMove(new AIEngine(Board.Player2, 1), GameState.FromMoves(MustBlockColumn0), 3600, _ => called = true);
            for (int i = 0; i < 20; i++)
                runner.Tick();
            Assert.That(called, Is.False);
            Assert.That(runner.IsThinking, Is.True);
        }

        [Test]
        public void CancelledMoveNeverReports()
        {
            var runner = new AIRunner();
            bool called = false;
            runner.RequestMove(new AIEngine(Board.Player2, 3), GameState.FromMoves(MustBlockColumn0), 0, _ => called = true);
            runner.CancelMove();
            Assert.That(runner.IsThinking, Is.False);
            for (int i = 0; i < 20; i++)
                runner.Tick();
            Assert.That(called, Is.False);
        }

        [Test]
        public void AnalysisQueueReportsBestMoveForSideToMove()
        {
            var runner = new AIRunner();
            int best = -99;
            runner.EnqueueAnalysis(GameState.FromMoves(MustBlockColumn0), 3, col => best = col);
            Assert.That(runner.PendingAnalyses, Is.EqualTo(1));
            Assert.That(TickUntil(runner.Tick, () => best != -99), "analiz bitmedi");
            Assert.That(best, Is.EqualTo(0));
            Assert.That(runner.PendingAnalyses, Is.EqualTo(0));
        }

        [Test]
        public void CancelAnalysisDropsQueuedWork()
        {
            var runner = new AIRunner();
            bool called = false;
            runner.EnqueueAnalysis(GameState.FromMoves(MustBlockColumn0), 3, _ => called = true);
            runner.CancelAnalysis();
            Assert.That(runner.PendingAnalyses, Is.EqualTo(0));
            for (int i = 0; i < 20; i++)
                runner.Tick();
            Assert.That(called, Is.False);
        }
    }
}
