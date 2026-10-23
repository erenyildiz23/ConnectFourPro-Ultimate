// =============================================================================
// AIEngine.cs - Connect Four Pro Ultimate
// AI motoru v2: negamax + alpha-beta, oyun teorisi sezgileri
// (src/ai_vs_human.py ile birebir ayni arama ve degerlendirme)
// =============================================================================
//
// Arama
// -----
// Negamax + alpha-beta budama, transpozisyon tablosu ve yinelemeli derinlestirme.
// Konum iki tam sayiyla tutulur: cur (sirasi gelen oyuncunun taslari) ve mask
// (dolu hucreler); hamle basina nesne kopyalanmaz.
//
// Her dugumde taktik kurallar uygulanir:
//   * Sirasi gelen tek hamlede kazanabiliyorsa -> kazanc.
//   * Rakibin oynanabilir kazanma hucresi varsa oraya oynamak zorunludur;
//     iki tane varsa pozisyon kayiptir.
//   * Rakibin kazanma hucresinin hemen altina oynanmaz (rakibe kapiyi acar).
//
// Degerlendirme (oyun teorisi)
// ----------------------------
// Allis'in "zugzwang" analizine gore oyun sonunda tehditlerin satir paritesi
// belirleyicidir: ilk oyuncu icin TEK satirlardaki (1, 3, 5), ikinci oyuncu icin
// CIFT satirlardaki (2, 4, 6) tehditler degerlidir. Ayrintilar: docs/AI.md.
//
// WebGL
// -----
// Tarayicida thread yoktur. Bu yuzden arama BeginSearch() ile adim adim
// yurutulebilir: her Step() kok dugumun tek bir cocugunu arar. Unity tarafindaki
// AIRunner her karede zaman butcesi dolana kadar Step() cagirir; kare donmaz.

using System;
using System.Collections.Generic;
using ConnectFourPro.Core;

namespace ConnectFourPro.AI
{
    /// <summary>Arama disaridan iptal edildi (orn. oyuncu menuye dondu).</summary>
    public sealed class SearchCancelledException : Exception
    {
    }

    public sealed class AIEngine
    {
        public const int MaxDepthDefault = 7;

        // --- Skorlar ---
        public const int WinScore = 1_000_000;          // Kazanc skoru; erken kazanc daha yuksek (WinScore - ply)
        public const int WinThreshold = WinScore - 1000;
        public const int ThreatGood = 8;                // Lehine pariteli tehdit; egitim kumesinde ayarlandi
        public const int ThreatOther = 4;               // Diger tehditler
        public const int ExactEndgamePlies = 12;        // ExactEndgame acikken kalan hamle <= esik ise sona kadar ara

        /// <summary>Zorluk seviyeleri (ad, derinlik); sira arayuzdeki siradir.</summary>
        public static readonly IReadOnlyList<(string name, int depth)> Difficulties = new[]
        {
            ("Kolay", 2),
            ("Orta", 4),
            ("Zor", 8),
        };

        // --- Bitboard sabitleri (GameState ile ayni yerlesim: bit = sutun * 7 + satir) ---
        private const int H1 = Board.Rows + 1;
        public static readonly ulong BottomMask;
        public static readonly ulong BoardMask;
        public static readonly ulong RowsOdd;     // 1., 3., 5. satirlar (satir 0 = alt = 1. satir)
        public static readonly ulong RowsEven;    // 2., 4., 6. satirlar
        private static readonly ulong[] ColumnMask = new ulong[Board.Cols];
        /// <summary>Merkezden disa sutun sirasi: 3, 2, 4, 1, 5, 0, 6.</summary>
        public static readonly int[] CenterOrder = { 3, 2, 4, 1, 5, 0, 6 };
        // Ayni agirliktaki hucreler tek maskede: popcount ile hizli konumsal skor
        private static readonly int[] WeightValues;
        private static readonly ulong[] WeightMasks;

        static AIEngine()
        {
            for (int c = 0; c < Board.Cols; c++)
            {
                BottomMask |= 1UL << (c * H1);
                ColumnMask[c] = ((1UL << Board.Rows) - 1) << (c * H1);
                for (int r = 0; r < Board.Rows; r++)
                {
                    if (r % 2 == 0)
                        RowsOdd |= 1UL << (c * H1 + r);
                    else
                        RowsEven |= 1UL << (c * H1 + r);
                }
            }
            BoardMask = BottomMask * ((1UL << Board.Rows) - 1);

            var byWeight = new SortedDictionary<int, ulong>();
            for (int c = 0; c < Board.Cols; c++)
                for (int r = 0; r < Board.Rows; r++)
                {
                    int w = LinesThrough(c, r);
                    byWeight.TryGetValue(w, out ulong m);
                    byWeight[w] = m | (1UL << (c * H1 + r));
                }
            WeightValues = new int[byWeight.Count];
            WeightMasks = new ulong[byWeight.Count];
            int i = 0;
            foreach (var kv in byWeight)
            {
                WeightValues[i] = kv.Key;
                WeightMasks[i] = kv.Value;
                i++;
            }
        }

        /// <summary>(sutun, satir) hucresinden gecen olasi 4'lu hat sayisi.</summary>
        internal static int LinesThrough(int col, int row)
        {
            int count = 0;
            int[,] dirs = { { 1, 0 }, { 0, 1 }, { 1, 1 }, { 1, -1 } };
            for (int k = 0; k < 4; k++)
            {
                int dc = dirs[k, 0], dr = dirs[k, 1];
                for (int start = -3; start <= 0; start++)
                {
                    bool inside = true;
                    for (int i = 0; i < 4 && inside; i++)
                    {
                        int c = col + (start + i) * dc, r = row + (start + i) * dr;
                        inside = c >= 0 && c < Board.Cols && r >= 0 && r < Board.Rows;
                    }
                    if (inside)
                        count++;
                }
            }
            return count;
        }

        /// <summary>position taslarinin tamamlarsa dortlu yapacagi BOS hucrelerin maskesi.</summary>
        public static ulong WinningCells(ulong position, ulong mask)
        {
            // Dikey: alttaki uc tas
            ulong r = (position << 1) & (position << 2) & (position << 3);
            // Yatay ve iki capraz: dort konumdan herhangisi eksik olabilir
            for (int k = 0; k < 3; k++)
            {
                int d = k == 0 ? H1 : (k == 1 ? H1 - 1 : H1 + 1);
                ulong p = (position << d) & (position << (2 * d));
                r |= p & (position << (3 * d));
                r |= p & (position >> d);
                p = (position >> d) & (position >> (2 * d));
                r |= p & (position << d);
                r |= p & (position >> (3 * d));
            }
            return r & (BoardMask ^ mask);
        }

        // Kazanma yonleri: dikey, yatay, capraz /, capraz \ (GameState ile ayni)
        private static readonly int[] Directions = { 1, H1, H1 + 1, H1 - 1 };

        public static bool HasFour(ulong position)
        {
            foreach (int d in Directions)
            {
                ulong m = position & (position >> d);
                if ((m & (m >> (2 * d))) != 0)
                    return true;
            }
            return false;
        }

        /// <summary>Terminal olmayan pozisyon; sirasi gelen oyuncunun bakis acisindan.</summary>
        public static int Evaluate(ulong cur, ulong mask)
        {
            ulong opp = cur ^ mask;
            bool sideIsFirst = Board.PopCount(mask) % 2 == 0;   // ilk oyuncu cift sayida tas varken oynar
            ulong myGood = sideIsFirst ? RowsOdd : RowsEven;
            ulong oppGood = sideIsFirst ? RowsEven : RowsOdd;

            ulong myThreats = WinningCells(cur, mask);
            ulong oppThreats = WinningCells(opp, mask);
            int score = ThreatGood * (Board.PopCount(myThreats & myGood) - Board.PopCount(oppThreats & oppGood))
                      + ThreatOther * (Board.PopCount(myThreats & ~myGood) - Board.PopCount(oppThreats & ~oppGood));
            for (int i = 0; i < WeightMasks.Length; i++)
                score += WeightValues[i] * (Board.PopCount(cur & WeightMasks[i]) - Board.PopCount(opp & WeightMasks[i]));
            return score;
        }

        // ------------------------------------------------------------------
        // Durum ve metrikler
        // ------------------------------------------------------------------

        private struct TTEntry
        {
            public int Depth;
            public int Flag;      // 0 kesin, 1 alt sinir, -1 ust sinir
            public int Value;
            public ulong Move;
        }

        private readonly Dictionary<ulong, TTEntry> _tt = new Dictionary<ulong, TTEntry>();
        private readonly ulong[] _moveBuffer = new ulong[(Board.Size + 2) * Board.Cols];
        private readonly Random _rng;
        private Func<bool> _cancel;

        public int PlayerId { get; }
        public int OpponentId { get; }
        public int Depth { get; }
        public bool UseOpeningBook { get; set; }
        public bool ExactEndgame { get; set; }

        // Metrikler
        public long NodesEvaluated { get; private set; }
        public long Cutoffs { get; private set; }
        public bool LastMoveFromBook { get; private set; }
        /// <summary>Son aramanin kok skoru; arama yapilmadiysa null.</summary>
        public int? LastScore { get; private set; }
        public int LastDepthReached { get; private set; }

        /// <param name="playerId">AI'nin oynadigi tas</param>
        /// <param name="depth">Arama derinligi (yari-hamle)</param>
        /// <param name="useOpeningBook">Dogrulanmis acilis kitabini kullan</param>
        /// <param name="exactEndgame">Kalan hamle ExactEndgamePlies altina dusunce sona kadar ara.
        /// null: derinlik &gt;= 6 ise acik (Zor seviye)</param>
        /// <param name="seed">Esit skorlu hamleler arasinda secim icin tohum (null: deterministik).
        /// Not: C# ve Python rastgele sayi uretecleri farklidir; tohumlu secim Python'la ayni olmaz.</param>
        public AIEngine(int playerId, int depth = MaxDepthDefault, bool useOpeningBook = true,
                        bool? exactEndgame = null, int? seed = null)
        {
            if (depth < 1)
                throw new ArgumentException("depth en az 1 olmali", nameof(depth));
            PlayerId = playerId;
            OpponentId = Board.OtherPlayer(playerId);
            Depth = depth;
            UseOpeningBook = useOpeningBook;
            ExactEndgame = exactEndgame ?? depth >= 6;
            _rng = seed.HasValue ? new Random(seed.Value) : null;
        }

        public void ResetMetrics()
        {
            NodesEvaluated = 0;
            Cutoffs = 0;
            LastMoveFromBook = false;
            LastScore = null;
            LastDepthReached = 0;
        }

        /// <summary>Transpozisyon tablosunu bosaltir (her arama basinda otomatik yapilir).</summary>
        public void ClearTranspositionTable() => _tt.Clear();

        // ------------------------------------------------------------------
        // Arama
        // ------------------------------------------------------------------

        /// <summary>Adaylari sirala: TT hamlesi, sonra yeni tehdit sayisi, sonra merkeze yakinlik.</summary>
        private static int OrderedMoves(ulong cur, ulong mask, ulong candidates, ulong first, ulong[] output, int o)
        {
            // Python: (bit != first, -threats, sira, bit) demetlerinin sozluk sirasi
            Span<int> keyA = stackalloc int[Board.Cols];
            Span<int> keyB = stackalloc int[Board.Cols];
            int n = 0;
            foreach (int col in CenterOrder)
            {
                ulong bit = candidates & ColumnMask[col];
                if (bit == 0)
                    continue;
                int threats = bit == first ? 0 : Board.PopCount(WinningCells(cur | bit, mask | bit));
                int a = bit != first ? 1 : 0, b = -threats;
                // Kararli eklemeli siralama (esitlikte ekleme sirasi korunur)
                int j = n;
                while (j > 0 && (keyA[j - 1] > a || (keyA[j - 1] == a && keyB[j - 1] > b)))
                {
                    keyA[j] = keyA[j - 1];
                    keyB[j] = keyB[j - 1];
                    output[o + j] = output[o + j - 1];
                    j--;
                }
                keyA[j] = a;
                keyB[j] = b;
                output[o + j] = bit;
                n++;
            }
            return n;
        }

        public int Negamax(ulong cur, ulong mask, int depth, int alpha, int beta, int ply)
        {
            NodesEvaluated++;
            if (_cancel != null && _cancel())
                throw new SearchCancelledException();

            ulong possible = (mask + BottomMask) & BoardMask;
            if (possible == 0)
                return 0;                                       // Tahta dolu: beraberlik
            if ((WinningCells(cur, mask) & possible) != 0)
                return WinScore - ply - 1;                      // Bir sonraki hamlede kazanir
            ulong oppWins = WinningCells(cur ^ mask, mask);
            ulong forced = possible & oppWins;
            if (forced != 0)
            {
                if ((forced & (forced - 1)) != 0)
                    return -(WinScore - ply - 2);               // Iki tehdit: engellenemez
                possible = forced;
            }
            ulong candidates = possible & ~(oppWins >> 1);
            if (candidates == 0)
                return -(WinScore - ply - 2);                   // Her hamle rakibe kazanc verir
            if (Board.PopCount(mask) >= Board.Size - 1)
                return 0;                                       // Son hamle: kimse kazanamaz
            if (depth <= 0)
                return Evaluate(cur, mask);

            // TT her aramada temizlenir; bir pozisyon ayni aramada hep ayni ply'da
            // gorulur (tas sayisi sabit), bu yuzden kazanc skorlari dogrudan saklanir.
            ulong key = cur + mask;
            ulong ttMove = 0;
            if (_tt.TryGetValue(key, out TTEntry entry))
            {
                ttMove = entry.Move;
                if (entry.Depth >= depth)
                {
                    if (entry.Flag == 0)
                        return entry.Value;
                    if (entry.Flag > 0 && entry.Value >= beta)
                        return entry.Value;
                    if (entry.Flag < 0 && entry.Value <= alpha)
                        return entry.Value;
                }
            }

            int alphaOrig = alpha;
            int bestValue = -WinScore * 2;
            ulong bestMove = 0;
            // Ply basina sabit tampon: WebGL'de (Boehm GC) dugum basina ayirma pahalidir
            int offset = ply * Board.Cols;
            int count = OrderedMoves(cur, mask, candidates, ttMove, _moveBuffer, offset);
            for (int i = 0; i < count; i++)
            {
                ulong bit = _moveBuffer[offset + i];
                int value = -Negamax(cur ^ mask, mask | bit, depth - 1, -beta, -alpha, ply + 1);
                if (value > bestValue)
                {
                    bestValue = value;
                    bestMove = bit;
                }
                if (value > alpha)
                    alpha = value;
                if (alpha >= beta)
                {
                    Cutoffs++;
                    break;
                }
            }

            int flag = bestValue >= beta ? 1 : (bestValue <= alphaOrig ? -1 : 0);
            _tt[key] = new TTEntry { Depth = depth, Flag = flag, Value = bestValue, Move = bestMove };
            return bestValue;
        }

        /// <summary>
        /// Mevcut pozisyon icin en iyi sutun; tahta doluysa veya arama iptal edildiyse -1.
        /// Senkron calisir; WebGL'de kareyi bolmek icin BeginSearch() kullanin.
        /// </summary>
        /// <param name="cancel">true donerse arama durur ve -1 doner (dugum basina kontrol edilir).</param>
        public int FindBestMove(GameState game, Func<bool> cancel = null)
        {
            var search = BeginSearch(game, cancel);
            while (!search.Step())
            {
            }
            return search.Result;
        }

        /// <summary>Adim adim yurutulecek bir arama baslatir.</summary>
        public Search BeginSearch(GameState game, Func<bool> cancel = null)
        {
            return new Search(this, game, cancel);
        }

        /// <summary>
        /// Adim adim arama. Her Step() kok dugumun tek bir cocugunu arar.
        /// Python'daki find_best_move ile ayni sonucu verir.
        /// </summary>
        public sealed class Search
        {
            private readonly AIEngine _engine;
            private readonly Func<bool> _cancel;
            private readonly ulong _cur;
            private readonly ulong _mask;
            private readonly int _target;
            private List<int> _order;
            private readonly List<(int col, int value)> _results = new List<(int, int)>();
            private int _depth;
            private int _index;
            private int _alpha;

            public bool Done { get; private set; }
            /// <summary>Secilen sutun; Done olana kadar veya iptalde -1.</summary>
            public int Result { get; private set; } = -1;
            public bool Cancelled { get; private set; }

            internal Search(AIEngine engine, GameState game, Func<bool> cancel)
            {
                _engine = engine;
                _cancel = cancel;
                engine.ResetMetrics();

                var valid = game.GetValidLocations();
                if (valid.Count == 0 || (cancel != null && cancel()))
                {
                    Cancelled = valid.Count > 0;
                    Finish(-1);
                    return;
                }

                if (engine.UseOpeningBook)
                {
                    int move = OpeningBook.Lookup(game.MoveHistory);
                    if (move >= 0 && game.IsValidLocation(move))
                    {
                        engine.LastMoveFromBook = true;
                        Finish(move);
                        return;
                    }
                }

                _cur = game.GetBitboard(game.CurrentPlayer);
                _mask = game.Mask;
                ulong possible = (_mask + BottomMask) & BoardMask;

                // Taktik kisayollar (aramaya gerek yok)
                ulong wins = WinningCells(_cur, _mask) & possible;
                if (wins != 0)
                {
                    Finish(FirstInCenterOrder(wins));
                    return;
                }
                ulong forced = possible & WinningCells(_cur ^ _mask, _mask);
                if (forced != 0 && (forced & (forced - 1)) == 0)
                {
                    Finish(FirstInCenterOrder(forced));
                    return;
                }

                int remaining = Board.Size - Board.PopCount(_mask);
                int target = engine.ExactEndgame && remaining <= ExactEndgamePlies ? remaining : engine.Depth;
                _target = Math.Min(target, remaining);

                _order = new List<int>();
                foreach (int c in CenterOrder)
                    if (valid.Contains(c))
                        _order.Add(c);
                Result = _order[0];
                engine._tt.Clear();
                StartDepth(1);
            }

            private static int FirstInCenterOrder(ulong cells)
            {
                foreach (int c in CenterOrder)
                    if ((cells & ColumnMask[c]) != 0)
                        return c;
                return -1;
            }

            private void StartDepth(int depth)
            {
                _depth = depth;
                _index = 0;
                _alpha = -WinScore * 2;
                _results.Clear();
            }

            private void Finish(int result)
            {
                Result = result;
                Done = true;
                _engine._cancel = null;
                _engine._tt.Clear();
            }

            /// <summary>Bir kok cocugunu arar. Arama bittiyse true.</summary>
            public bool Step()
            {
                if (Done)
                    return true;

                _engine._cancel = _cancel;
                try
                {
                    int col = _order[_index];
                    ulong bit = ((_mask + BottomMask) & BoardMask) & ColumnMask[col];
                    // Esit skorlu hamleleri ayirt etmek icin pencere alpha-1'den baslar
                    int value = -_engine.Negamax(_cur ^ _mask, _mask | bit, _depth - 1,
                                                 -(WinScore * 2), -(_alpha - 1), 1);
                    _results.Add((col, value));
                    if (value > _alpha)
                        _alpha = value;
                }
                catch (SearchCancelledException)
                {
                    Cancelled = true;
                    Finish(-1);
                    return true;
                }
                finally
                {
                    _engine._cancel = null;
                }

                if (++_index < _order.Count)
                    return false;

                // Derinlik tamamlandi
                int best = _alpha;
                var bestMoves = new List<int>();
                foreach (var (c, v) in _results)
                    if (v == best)
                        bestMoves.Add(c);
                Result = _engine._rng != null ? bestMoves[_engine._rng.Next(bestMoves.Count)] : bestMoves[0];
                _engine.LastScore = best;
                _engine.LastDepthReached = _depth;

                // Sonraki tur icin kok siralamasi: iyi hamleler once (kararli siralama)
                var sorted = new List<(int col, int value, int idx)>();
                for (int i = 0; i < _results.Count; i++)
                    sorted.Add((_results[i].col, _results[i].value, i));
                sorted.Sort((x, y) => x.value != y.value ? y.value.CompareTo(x.value) : x.idx.CompareTo(y.idx));
                _order = new List<int>();
                foreach (var s in sorted)
                    _order.Add(s.col);

                if (Math.Abs(best) > WinThreshold || _depth >= _target)
                {
                    Finish(Result);
                    return true;
                }
                StartDepth(_depth + 1);
                return false;
            }

            /// <summary>Aramayi durdurur; Result -1 olur.</summary>
            public void Cancel()
            {
                if (Done)
                    return;
                Cancelled = true;
                Finish(-1);
            }
        }
    }
}
