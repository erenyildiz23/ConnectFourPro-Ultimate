// =============================================================================
// AIRunner.cs - Connect Four Pro Ultimate
// AI aramalarini kareler arasina bolerek ana thread'de yurutur (WebGL'de thread yok)
// =============================================================================
//
// Python istemcisindeki AI thread'i ve analiz isci thread'inin karsiligi:
//   * Hamle aramasi: oncelikli. Her karede en fazla FrameBudgetMs kadar calisir.
//   * Hamle analizi (Lichess tarzi isabet): hamle aramasi yokken sirayla yapilir.
// Oturum numaralari eski aramalarin sonuclarini eler (oyuncu menuye donduyse vb.).

using System;
using System.Collections.Generic;
using System.Diagnostics;
using ConnectFourPro.AI;
using ConnectFourPro.Core;

namespace ConnectFourPro.Game
{
    public sealed class AIRunner
    {
        /// <summary>Bir karede aramaya ayrilan sure (60 FPS'te kare 16,7 ms).</summary>
        public double FrameBudgetMs = 8.0;

        private sealed class Job
        {
            public AIEngine.Search Search;
            public double StartAt;
            public int Session;
            public Action<int> Done;
        }

        private Job _move;
        private Job _analysis;
        private readonly Queue<Job> _analysisQueue = new Queue<Job>();
        private readonly Stopwatch _clock = Stopwatch.StartNew();
        private int _moveSession;
        private int _analysisSession;

        public bool IsThinking => _move != null;
        public int PendingAnalyses => _analysisQueue.Count + (_analysis != null ? 1 : 0);

        private double Now => _clock.Elapsed.TotalSeconds;

        /// <summary>
        /// AI hamlesi ister. delaySeconds sonra arama baslar (hamleler arasi dogal duraklama).
        /// done(-1): tahta dolu. Iptal edilen aramalarda done cagrilmaz.
        /// </summary>
        public void RequestMove(AIEngine engine, GameState snapshot, double delaySeconds, Action<int> done)
        {
            CancelMove();
            _move = new Job
            {
                Search = engine.BeginSearch(snapshot),
                StartAt = Now + delaySeconds,
                Session = _moveSession,
                Done = done,
            };
        }

        public void CancelMove()
        {
            _moveSession++;
            _move?.Search.Cancel();
            _move = null;
        }

        /// <summary>Hamle oncesi pozisyonda en iyi hamleyi arka planda hesaplar.</summary>
        public void EnqueueAnalysis(GameState before, int depth, Action<int> done)
        {
            var engine = new AIEngine(before.CurrentPlayer, depth);
            _analysisQueue.Enqueue(new Job
            {
                Search = engine.BeginSearch(before),
                StartAt = 0,
                Session = _analysisSession,
                Done = done,
            });
        }

        public void CancelAnalysis()
        {
            _analysisSession++;
            _analysis?.Search.Cancel();
            _analysis = null;
            _analysisQueue.Clear();
        }

        public void CancelAll()
        {
            CancelMove();
            CancelAnalysis();
        }

        /// <summary>Her karede bir kez cagrilir.</summary>
        public void Tick()
        {
            var frameStart = _clock.Elapsed.TotalMilliseconds;
            while (_clock.Elapsed.TotalMilliseconds - frameStart < FrameBudgetMs)
            {
                if (_move != null)
                {
                    if (Now < _move.StartAt)
                        break;      // duraklama: analizi de bekletme ki AI hamlesi gecikmesin
                    StepJob(ref _move, _moveSession);
                    continue;
                }
                if (_analysis == null)
                {
                    if (_analysisQueue.Count == 0)
                        return;
                    _analysis = _analysisQueue.Dequeue();
                }
                StepJob(ref _analysis, _analysisSession);
            }
        }

        /// <summary>Isi bir adim ilerletir; bittiyse isi bosaltip geri cagriyi calistirir.</summary>
        private static void StepJob(ref Job job, int currentSession)
        {
            var current = job;
            if (current.Session != currentSession)
            {
                job = null;
                return;
            }
            if (!current.Search.Step())
                return;
            job = null;     // geri cagri yeni bir is baslatabilir
            if (!current.Search.Cancelled)
                current.Done?.Invoke(current.Search.Result);
        }
    }
}
