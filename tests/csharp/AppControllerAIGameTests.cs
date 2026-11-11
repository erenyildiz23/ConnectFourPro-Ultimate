// AI oyunu (Game/AppController.cs), pygame istemcisiyle esdeger davranis
// (tests/gui/test_gui_feedback.py: TestKolaySlip, TestAIFirstMoveAndNewGame, TestUndo,
// TestOnboarding, TestAccuracyMetric). AIRunner gercek saatle calisir.
using System;
using System.Collections.Generic;
using ConnectFourPro.AI;
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public partial class AppControllerTests
    {
        private bool TickUntil(Func<bool> done, double timeout = 20) => AIRunnerTests.TickUntil(_app.Tick, done, timeout);

        /// <summary>Insan hamlesi yapar ve AI cevabini bekler (oyun bitmediyse).</summary>
        private void HumanMove(int col)
        {
            int before = _app.Game.MoveCount;
            _app.HandleColumnClick(col);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(before + 1), "hamle yapilamadi");
            if (!_app.Game.GameOver)
                Assert.That(TickUntil(() => _app.CanHumanMove() || _app.Game.GameOver), "AI hamle yapmadi");
        }

        /// <summary>Animasyonlari elle bitirmek icin: AnimateDrop geri cagrilari biriktirilir.</summary>
        private List<Action> HoldAnimations()
        {
            var pending = new List<Action>();
            _app.AnimateDrop = (col, row, piece, done) => pending.Add(done);
            return pending;
        }

        private static uint SeedWhere(Func<int, bool> slipIs)
        {
            var game = GameState.FromMoves(new[] { 0 });
            uint seed = 0;
            while (!slipIs(SlipPolicy.SlipMove(game, 2, seed)))
                seed++;
            return seed;
        }

        // ---------------------------------------------------------------------
        // Kolay seviyesinin hatalari
        // ---------------------------------------------------------------------

        [Test]
        public void KolayReplyAppliesTheSlipAfterTheSearch()
        {
            uint slipSeed = SeedWhere(c => c >= 0 && c != 3);
            uint calmSeed = SeedWhere(c => c < 0);
            _app.GuestLogin();
            _app.NewSeed = () => slipSeed;
            _app.StartAIGame(2, false);
            Assert.That(_app.AISeed, Is.EqualTo(slipSeed));
            HumanMove(0);
            int slip = SlipPolicy.SlipMove(GameState.FromMoves(new[] { 0 }), 2, slipSeed);
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 0, slip }), "kitap hamlesi (3) yerine hata sutunu");

            _app.NewSeed = () => calmSeed;
            _app.StartAIGame(2, false);
            HumanMove(0);
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 0, 3 }));
        }

        [Test]
        public void OrtaNeverSlips()
        {
            uint slipSeed = SeedWhere(c => c >= 0 && c != 3);
            _app.GuestLogin();
            _app.NewSeed = () => slipSeed;
            _app.StartAIGame(4, false);
            HumanMove(0);
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 0, 3 }));
        }

        [Test]
        public void EachAIGameDrawsAFreshSeed()
        {
            _app.GuestLogin();
            uint next = 7;
            _app.NewSeed = () => next++;
            _app.StartAIGame(2, false);
            Assert.That(_app.AISeed, Is.EqualTo(7u));
            _app.NewAIGame();
            Assert.That(_app.AISeed, Is.EqualTo(8u));
        }

        // ---------------------------------------------------------------------
        // Ilk hamle secimi ve Yeni Oyun / Tekrar Oyna
        // ---------------------------------------------------------------------

        [Test]
        public void ToggleOnDifficultyScreenDecidesTheStarter()
        {
            _app.GuestLogin();
            _app.OpenAISelect();
            Assert.That(_app.AIStartsNext, Is.False, "varsayilan: insan baslar");
            Assert.That(_app.AIStartsLabel, Is.EqualTo("İlk hamle: Sen"));
            _app.ToggleAIStartsNext();
            Assert.That(_app.AIStartsNext, Is.True);
            Assert.That(_app.AIStartsLabel, Is.EqualTo("İlk hamle: AI"));

            _app.StartAIGame(4);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingAI));
            Assert.That(_app.AIStarts, Is.True);
            Assert.That(_app.Game.CurrentPlayer, Is.EqualTo(Board.Player2));
            Assert.That(_app.AIThinking, Is.True);
            Assert.That(_app.Status, Is.EqualTo("AI düşünüyor..."));
            Assert.That(_app.CanHumanMove(), Is.False);
            Assert.That(TickUntil(_app.CanHumanMove), "AI ilk hamleyi yapmadi");
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3 }));
            Assert.That(_app.Status, Is.EqualTo("Senin sıran!"));
            Assert.That(_app.MyPiece, Is.EqualTo(Board.Player1));
            Assert.That(_app.HumanPiece, Is.EqualTo(Board.Player1), "insan hep kirmizi");
            Assert.That(_app.Game.GetCell(3, 0), Is.EqualTo(Board.Player2));

            _app.ToggleAIStartsNext();
            _app.RequestBack();
            _app.StartAIGame(4);
            Assert.That(_app.AIStarts, Is.False);
        }

        [Test]
        public void HumanFirstByDefaultWithCoachingLine()
        {
            _app.GuestLogin();
            _app.StartAIGame(4);
            Assert.That(_app.AIStarts, Is.False);
            Assert.That(_app.CanHumanMove(), Is.True);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(_app.Status, Is.EqualTo(AppController.CoachText));
            Assert.That(_app.Status, Does.Contain("Kırmızı sensin"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Good));
            HumanMove(3);
            Assert.That(_app.Status, Is.EqualTo("Senin sıran!"));
        }

        [Test]
        public void NewGameAlternatesTheStarterAndKeepsDepth()
        {
            _app.GuestLogin();
            _app.StartAIGame(4, false);
            HumanMove(0);
            Assert.That(_app.NewGameLabel, Is.EqualTo("Yeni Oyun"), "oyun surerken de kullanilabilir");
            _app.PlayAgain();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingAI));
            Assert.That(_app.Engine.Depth, Is.EqualTo(4));
            Assert.That(_app.AIStarts, Is.True);
            Assert.That(TickUntil(_app.CanHumanMove), "AI ilk hamleyi yapmadi");
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3 }));
            _app.NewAIGame();
            Assert.That(_app.AIStarts, Is.False);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(_app.CanHumanMove(), Is.True);
            Assert.That(_app.Engine.Depth, Is.EqualTo(4));
        }

        [Test]
        public void NewGameOutsideAnAIGameDoesNothing()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.NewAIGame();
            _app.PlayAgain();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
        }

        [Test]
        public void NewGameWhileDiscFallsLeavesNoStaleMove()
        {
            var pending = HoldAnimations();
            _app.GuestLogin();
            _app.StartAIGame(4, false);
            _app.HandleColumnClick(0);
            Assert.That(pending.Count, Is.EqualTo(1));
            var stale = pending[0];
            pending.Clear();
            _app.NewAIGame();                         // AI baslar
            stale();                                  // eski tasin geri cagrisi yeni oyuna sizmamali
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(TickUntil(() => pending.Count == 1), "AI hamle yapmadi");
            pending[0]();
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3 }));
            Assert.That(_app.CanHumanMove(), Is.True);
        }

        [Test]
        public void NewGameWhileAIThinksDiscardsItsOldMove()
        {
            _app.GuestLogin();
            _app.StartAIGame(6, false);
            _app.HandleColumnClick(0);
            Assert.That(_app.AIThinking, Is.True);
            _app.NewAIGame();
            Assert.That(TickUntil(_app.CanHumanMove, 30), "AI hamle yapmadi");
            for (int i = 0; i < 60; i++)
                _app.Tick();
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3 }));
        }

        // ---------------------------------------------------------------------
        // Geri Al
        // ---------------------------------------------------------------------

        [Test]
        public void UndoRestoresTheExactPosition()
        {
            _app.GuestLogin();
            _app.StartAIGame(4, false);
            Assert.That(_app.CanUndo, Is.False);
            HumanMove(3);
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3, 3 }));
            Assert.That(_app.CanUndo, Is.True);
            _app.UndoAIMove();
            Assert.That(_app.Game.MoveCount, Is.EqualTo(0));
            Assert.That(_app.Game.Mask, Is.EqualTo(0UL));
            Assert.That(_app.Game.CurrentPlayer, Is.EqualTo(Board.Player1));
            Assert.That(_app.CanHumanMove(), Is.True);
            Assert.That(_app.Status, Is.EqualTo("Hamle geri alındı. Senin sıran!"));
            Assert.That(_app.Engine.Depth, Is.EqualTo(4));
            Assert.That(_app.CanUndo, Is.False);
        }

        [Test]
        public void UndoTakesBackOnlyTheLastRound()
        {
            _app.GuestLogin();
            _app.StartAIGame(4, false);
            HumanMove(3);
            HumanMove(1);
            var firstRound = new List<int>(_app.Game.MoveHistory).GetRange(0, 2);
            _app.UndoAIMove();
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(firstRound));
            Assert.That(_app.Game.CurrentPlayer, Is.EqualTo(Board.Player1));
        }

        [Test]
        public void UndoIsRefusedWhileDiscFallsAIThinksOrAIMoveIsPending()
        {
            var pending = HoldAnimations();
            _app.GuestLogin();
            _app.StartAIGame(4, false);
            _app.HandleColumnClick(3);
            pending[0]();
            Assert.That(TickUntil(() => pending.Count == 2), "AI hamle yapmadi");
            pending[1]();
            Assert.That(_app.CanUndo, Is.True);

            _app.HandleColumnClick(1);                 // insan tasi dusuyor
            Assert.That(_app.CanUndo, Is.False);
            _app.UndoAIMove();
            Assert.That(_app.Game.MoveCount, Is.EqualTo(2));
            pending[2]();
            Assert.That(_app.AIThinking, Is.True);     // AI dusunuyor
            Assert.That(_app.CanUndo, Is.False);
            _app.UndoAIMove();
            Assert.That(_app.Game.MoveCount, Is.EqualTo(3));
            Assert.That(TickUntil(() => pending.Count == 4), "AI hamle yapmadi");
            Assert.That(_app.AIThinking, Is.False);    // AI tasi dusuyor (hamle bekliyor)
            Assert.That(_app.CanUndo, Is.False);
            _app.UndoAIMove();
            Assert.That(_app.Game.MoveCount, Is.EqualTo(3));
            pending[3]();
            Assert.That(_app.Game.MoveCount, Is.EqualTo(4));
            Assert.That(_app.CanUndo, Is.True);

            _app.IsAnimating = () => true;             // UI animasyonu (BoardView) da engeller
            Assert.That(_app.CanUndo, Is.False);
        }

        [Test]
        public void UndoAfterGameOverReopensTheGame()
        {
            _app.GuestLogin();
            _app.StartAIGame(1, false);
            // Basit strateji: hep ilk gecerli sutun; derinlik 1 AI'ya karsi oyun kisa surer
            while (!_app.Game.GameOver)
                HumanMove(_app.Game.GetValidLocations()[0]);
            Assert.That(_app.ResultHeadline, Is.Not.Null);
            var history = new List<int>(_app.Game.MoveHistory);
            int lastHuman = history.Count % 2 == 1 ? history.Count - 1 : history.Count - 2;
            Assert.That(_app.CanUndo, Is.True);
            _app.UndoAIMove();
            Assert.That(_app.Game.GameOver, Is.False);
            Assert.That(_app.Game.GetWinningPositions(), Is.Empty);
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(history.GetRange(0, lastHuman)));
            Assert.That(_app.Game.CurrentPlayer, Is.EqualTo(Board.Player1));
            Assert.That(_app.CanHumanMove(), Is.True);
            Assert.That(_app.ResultHeadline, Is.Null);
        }

        [Test]
        public void UndoWhenTheAIStarted()
        {
            _app.GuestLogin();
            _app.StartAIGame(4, true);
            Assert.That(TickUntil(_app.CanHumanMove), "AI ilk hamleyi yapmadi");
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3 }));
            Assert.That(_app.CanUndo, Is.False, "henuz insan hamlesi yok");
            HumanMove(0);
            Assert.That(_app.Game.MoveCount, Is.EqualTo(3));
            Assert.That(_app.CanUndo, Is.True);
            _app.UndoAIMove();
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3 }));
            Assert.That(_app.Game.CurrentPlayer, Is.EqualTo(Board.Player1));
            Assert.That(_app.CanHumanMove(), Is.True);
            Assert.That(_app.AIStarts, Is.True);
        }

        [Test]
        public void UndoIsNotARerollOnKolay()
        {
            uint seed = SeedWhere(c => c >= 0 && c != 3);
            _app.GuestLogin();
            _app.NewSeed = () => seed;
            _app.StartAIGame(2, false);
            HumanMove(0);
            int reply = _app.Game.MoveHistory[1];
            _app.NewSeed = () => seed + 1;            // geri alma yeni tohum cekmemeli
            _app.UndoAIMove();
            Assert.That(_app.AISeed, Is.EqualTo(seed));
            HumanMove(0);
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 0, reply }));
        }

        [Test]
        public void UndoIsNotAvailableOnlineOrForSpectators()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            _app.HandleColumnClick(3);
            _transport.Receive("move_made", ServerMessages.MoveMade(3, 4));
            Assert.That(_app.CanUndo, Is.False);
            _app.UndoAIMove();
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3, 4 }));

            _app.ResetToMenu();
            _app.SpectateGame("AB12C");
            _transport.RaiseConnected();
            _transport.Receive("game_joined", SpectatorJoined(GameState.FromMoves(new[] { 3, 4 })));
            Assert.That(_app.CanUndo, Is.False);
            _app.UndoAIMove();
            Assert.That(_app.Game.MoveHistory, Is.EqualTo(new[] { 3, 4 }));
        }

        // ---------------------------------------------------------------------
        // Sade zorluk etiketleri
        // ---------------------------------------------------------------------

        [Test]
        public void DifficultyLabelsArePlainLanguage()
        {
            Assert.That(AppController.DifficultyLabel("Kolay"), Is.EqualTo("Kolay - yeni başlayanlar için"));
            Assert.That(AppController.DifficultyLabel("Orta"), Is.EqualTo("Orta - dengeli rakip"));
            Assert.That(AppController.DifficultyLabel("Zor"), Is.EqualTo("Zor - en güçlü rakip"));
            foreach (var (name, _) in AIEngine.Difficulties)
                Assert.That(AppController.DifficultyLabel(name), Does.StartWith(name + " - ").And.Not.Contain("(D"));
            Assert.That(AppController.CoachText,
                        Is.EqualTo("Dört taşı yatay, dikey ya da çapraz diz. Kırmızı sensin - bir sütuna tıkla."));
        }

        [TestCase(2, "AI - Kolay")]
        [TestCase(4, "AI - Orta")]
        [TestCase(8, "AI - Zor")]
        [TestCase(1, "AI - D1")]
        public void OpponentLabelUsesTheLevelName(int depth, string expected)
        {
            _app.GuestLogin();
            _app.StartAIGame(depth, false);
            Assert.That(_app.PlayerLabels().p2, Is.EqualTo(expected));
        }

        // ---------------------------------------------------------------------
        // Isabet: esit iyi hamleler ve kitap hamlesi hata sayilmaz
        // ---------------------------------------------------------------------

        [Test]
        public void AccuracyCountsEveryEqualBestMove()
        {
            _app.AnalysisEnabled = true;
            _app.GuestLogin();
            StartOnlineGameAsP1();
            // Kirmizi 2,3,4 dizer; sonunda 5'te kazanir (1 de kazanirdi; motor 1'i doner)
            var moves = new List<int>();
            foreach (int col in new[] { 2, 3, 4 })
            {
                _app.HandleColumnClick(col);
                moves.Add(col);
                moves.Add(col);
                _transport.Receive("move_made", ServerMessages.MoveMade(moves.ToArray()));
            }
            var before = GameState.FromMoves(moves);
            Assert.That(new AIEngine(Board.Player1, AppController.AnalysisDepth, useOpeningBook: false).FindBestMove(before),
                        Is.EqualTo(1), "on kosul: motor tek basina 1'i secer");
            _app.HandleColumnClick(5);
            Assert.That(_app.Game.GameOver, Is.True);
            _transport.Receive("game_over", ServerMessages.GameOver(1));

            // Beklenen: her hamle MoveAnalysis kumesinde mi (Python best_columns ile ayni, bkz. vektorler)
            moves.Add(5);
            int mine = 0, mineBest = 0, theirs = 0, theirsBest = 0;
            for (int i = 0; i < moves.Count; i++)
            {
                var pos = GameState.FromMoves(moves.GetRange(0, i));
                bool best = MoveAnalysis.BestColumns(pos, AppController.AnalysisDepth).Contains(moves[i]);
                if (i % 2 == 0) { mine++; if (best) mineBest++; }
                else { theirs++; if (best) theirsBest++; }
            }
            Assert.That(TickUntil(() => _app.Summary != null && _app.Summary.TotalMoves == moves.Count, 60),
                        "analizler tamamlanmadi");
            Assert.That(_app.Summary.MyAccuracy, Is.EqualTo(100.0 * mineBest / mine));
            Assert.That(_app.Summary.OpponentAccuracy, Is.EqualTo(100.0 * theirsBest / theirs));
            Assert.That(MoveAnalysis.BestColumns(before, AppController.AnalysisDepth), Does.Contain(5),
                        "kazandiran 5 de isabetli");
        }
    }
}
