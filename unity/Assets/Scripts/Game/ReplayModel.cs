// Tekrar ekraninin saf mantigi: hamle listesi uzerinde gezinme ve otomatik oynatma.
// UnityEngine'e bagimli degil; Tick(dt) disaridan beslenir.
using System;
using System.Collections.Generic;
using ConnectFourPro.Core;

namespace ConnectFourPro.Game
{
    public sealed class ReplayModel
    {
        public const float StepSeconds = 0.8f;

        private readonly int[] _moves;
        private float _acc;
        private GameState _state;

        public string P1 { get; }
        public string P2 { get; }
        public string ResultText { get; }

        public int Index { get; private set; }
        public int Count => _moves.Length;
        public bool Playing { get; private set; }

        // Index konumundaki durum (ilk Index hamle uygulanmis).
        public GameState State => _state;

        public ReplayModel(IReadOnlyList<int> moves, string p1, string p2, string resultText)
        {
            var arr = new int[moves.Count];
            for (int i = 0; i < arr.Length; i++) arr[i] = moves[i];
            _moves = arr;
            P1 = p1;
            P2 = p2;
            ResultText = resultText;
            Rebuild();
        }

        public void First() { Pause(); SetIndex(0); }
        public void Prev() { Pause(); SetIndex(Index - 1); }
        public void Next() { Pause(); SetIndex(Index + 1); }
        public void Last() { Pause(); SetIndex(Count); }

        public void TogglePlay()
        {
            if (Playing) { Playing = false; return; }
            // Sondaysa bastan baslat.
            if (Index >= Count) SetIndex(0);
            _acc = 0f;
            Playing = Count > 0;
        }

        public void Tick(float dt)
        {
            if (!Playing) return;
            _acc += dt;
            while (_acc >= StepSeconds && Index < Count)
            {
                _acc -= StepSeconds;
                SetIndex(Index + 1);
            }
            if (Index >= Count) { Playing = false; _acc = 0f; }
        }

        private void Pause()
        {
            Playing = false;
            _acc = 0f;
        }

        private void SetIndex(int i)
        {
            i = Math.Max(0, Math.Min(Count, i));
            if (i == Index) return;
            Index = i;
            Rebuild();
        }

        private void Rebuild()
        {
            var prefix = new int[Index];
            Array.Copy(_moves, prefix, Index);
            _state = GameState.FromMoves(prefix);
        }
    }
}
