// =============================================================================
// OpeningBook.cs - Connect Four Pro Ultimate
// Acilis kitabi: ilk iki yari-hamlenin tum pozisyonlari (57)
// =============================================================================
//
// En iyi hamleler kusursuz cozucuyle (Pons, connect4.gamesolver.org) hesaplandi;
// birden fazla en iyi hamle varsa merkeze en yakin olani secildi (0 tabanli sutun).
// Kaynak: src/ai_vs_human.py -> OPENING_BOOK (birebir ayni).

using System.Collections.Generic;

namespace ConnectFourPro.AI
{
    public static class OpeningBook
    {
        // Ilk hamle -> [ikinci hamle 0..6 icin cevap]
        private static readonly int[,] SecondReply =
        {
            { 3, 3, 2, 3, 3, 5, 3 },   // (0, x)
            { 4, 4, 2, 3, 3, 3, 3 },   // (1, x)
            { 3, 5, 3, 3, 2, 3, 3 },   // (2, x)
            { 3, 1, 5, 3, 1, 1, 3 },   // (3, x)
            { 3, 3, 2, 3, 3, 1, 3 },   // (4, x)
            { 3, 3, 3, 3, 4, 2, 2 },   // (5, x)
            { 3, 1, 3, 3, 4, 3, 3 },   // (6, x)
        };

        // (x,) -> cevap
        private static readonly int[] FirstReply = { 3, 2, 3, 3, 3, 4, 3 };

        public const int EmptyBoardMove = 3;

        /// <summary>Kitaptaki pozisyon sayisi (1 + 7 + 49).</summary>
        public const int Count = 57;

        /// <summary>Hamle gecmisi kitapta varsa en iyi sutun, yoksa -1.</summary>
        public static int Lookup(IReadOnlyList<int> history)
        {
            switch (history.Count)
            {
                case 0:
                    return EmptyBoardMove;
                case 1:
                    return InRange(history[0]) ? FirstReply[history[0]] : -1;
                case 2:
                    return InRange(history[0]) && InRange(history[1]) ? SecondReply[history[0], history[1]] : -1;
                default:
                    return -1;
            }
        }

        /// <summary>Tum kitap girdileri (testler icin).</summary>
        public static IEnumerable<(int[] history, int move)> Entries()
        {
            yield return (new int[0], EmptyBoardMove);
            for (int a = 0; a < 7; a++)
                yield return (new[] { a }, FirstReply[a]);
            for (int a = 0; a < 7; a++)
                for (int b = 0; b < 7; b++)
                    yield return (new[] { a, b }, SecondReply[a, b]);
        }

        private static bool InRange(int col) => col >= 0 && col < 7;
    }
}
