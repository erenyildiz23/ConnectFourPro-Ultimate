// =============================================================================
// GameState.cs - Connect Four Pro Ultimate
// Bitboard tabanli oyun motoru (src/game_core.py ile birebir ayni kurallar)
// =============================================================================
//
// Tahta temsili (bitboard)
// ------------------------
// Her oyuncunun taslari tek bir ulong'da tutulur. Sutun c, satir r (0 = alt)
// icin bit indeksi c * (Rows + 1) + r'dir. Her sutunun ustunde bos birakilan
// "nobetci" bit, yatay/capraz kaydirmalarin sutunlar arasinda tasmasini engeller:
//
//      6 13 20 27 34 41 48   <- nobetci satir (her zaman 0)
//      5 12 19 26 33 40 47
//      4 11 18 25 32 39 46
//      3 10 17 24 31 38 45
//      2  9 16 23 30 37 44
//      1  8 15 22 29 36 43
//      0  7 14 21 28 35 42
//
// Kazanma kontrolu dort yonde (dikey=1, yatay=7, capraz /=8, capraz \=6) sabit
// sayida bit islemiyle yapilir: O(1). Python surumuyle ayni yerlesim kullanildigi
// icin sunucunun gonderdigi bitboard'lar dogrudan yuklenebilir.

using System;
using System.Collections.Generic;
using System.Text;

namespace ConnectFourPro.Core
{
    public enum GameStatus
    {
        Playing = 0,
        Win = 1,
        Draw = 2,
    }

    public static class Board
    {
        public const int Rows = 6;
        public const int Cols = 7;
        public const int Empty = 0;
        public const int Player1 = 1;
        public const int Player2 = 2;
        public const int ColStride = Rows + 1;
        public const int Size = Rows * Cols;

        // Kazanma yonleri: dikey, yatay, capraz /, capraz \
        internal static readonly int[] Directions = { 1, ColStride, ColStride + 1, ColStride - 1 };

        public static int OtherPlayer(int piece) => piece == Player2 ? Player1 : Player2;

        /// <summary>(sutun, satir) koordinatinin bitboard indeksi.</summary>
        public static int BitIndex(int col, int row) => col * ColStride + row;

        public static int PopCount(ulong x)
        {
            int count = 0;
            while (x != 0)
            {
                x &= x - 1;
                count++;
            }
            return count;
        }
    }

    /// <summary>
    /// Connect Four oyun durumu. Python'daki ConnectFourGame sinifinin karsiligi.
    /// </summary>
    public sealed class GameState
    {
        private readonly ulong[] _bitboards = new ulong[3];   // indeks 1 ve 2 kullanilir
        private readonly int[] _heights = new int[Board.Cols];
        private readonly List<int> _history = new List<int>();

        public int CurrentPlayer { get; set; }
        public GameStatus Status { get; private set; }
        public bool GameOver { get; set; }
        /// <summary>Kazanan oyuncu; beraberlik veya devam eden oyunda 0.</summary>
        public int Winner { get; set; }
        /// <summary>Kazanan dortlunun bit maskesi (yoksa 0).</summary>
        public ulong WinningMask { get; private set; }

        public IReadOnlyList<int> MoveHistory => _history;
        public int MoveCount => _history.Count;

        public GameState(int startingPlayer = Board.Player1)
        {
            Reset(startingPlayer);
        }

        public void Reset(int startingPlayer = Board.Player1)
        {
            _bitboards[Board.Player1] = 0;
            _bitboards[Board.Player2] = 0;
            for (int c = 0; c < Board.Cols; c++)
                _heights[c] = c * Board.ColStride;
            _history.Clear();
            CurrentPlayer = startingPlayer;
            Status = GameStatus.Playing;
            GameOver = false;
            Winner = 0;
            WinningMask = 0;
        }

        public ulong GetBitboard(int player) => _bitboards[player];

        /// <summary>Dolu hucrelerin maskesi.</summary>
        public ulong Mask => _bitboards[Board.Player1] | _bitboards[Board.Player2];

        // ------------------------------------------------------------------
        // Hamleler
        // ------------------------------------------------------------------

        /// <summary>Sirasi gelen oyuncu icin hamle yapar. Gecersizse false.</summary>
        public bool MakeMove(int col)
        {
            if (GameOver || !IsValidLocation(col))
                return false;

            _bitboards[CurrentPlayer] |= 1UL << _heights[col];
            _heights[col]++;
            _history.Add(col);

            if (CheckWin(CurrentPlayer))
            {
                Status = GameStatus.Win;
                GameOver = true;
                Winner = CurrentPlayer;
            }
            else if (_history.Count >= Board.Size)
            {
                Status = GameStatus.Draw;
                GameOver = true;
                Winner = 0;
            }
            else
            {
                SwitchPlayer();
            }
            return true;
        }

        public void SwitchPlayer() => CurrentPlayer = Board.OtherPlayer(CurrentPlayer);

        /// <summary>Sutun tahta icinde ve dolu degilse true.</summary>
        public bool IsValidLocation(int col)
        {
            if (col < 0 || col >= Board.Cols)
                return false;
            return _heights[col] < Board.BitIndex(col, Board.Rows);
        }

        public List<int> GetValidLocations()
        {
            var result = new List<int>(Board.Cols);
            for (int c = 0; c < Board.Cols; c++)
                if (IsValidLocation(c))
                    result.Add(c);
            return result;
        }

        /// <summary>Sutuna atilacak tasin dusecegi satir (0 = alt).</summary>
        public int NextRow(int col) => _heights[col] - col * Board.ColStride;

        // ------------------------------------------------------------------
        // Kazanma kontrolu
        // ------------------------------------------------------------------

        /// <summary>
        /// Oyuncunun dortlu yapip yapmadigini kontrol eder (O(1)).
        /// Kazanma varsa WinningMask guncellenir.
        /// </summary>
        public bool CheckWin(int player)
        {
            ulong bb = _bitboards[player];
            foreach (int d in Board.Directions)
            {
                ulong m = bb & (bb >> d);
                if ((m & (m >> (2 * d))) != 0)
                {
                    ulong start = bb & (bb >> d) & (bb >> (2 * d)) & (bb >> (3 * d));
                    WinningMask = start | (start << d) | (start << (2 * d)) | (start << (3 * d));
                    return true;
                }
            }
            return false;
        }

        /// <summary>Hucredeki tas: Empty, Player1 veya Player2.</summary>
        public int GetCell(int col, int row)
        {
            ulong bit = 1UL << Board.BitIndex(col, row);
            if ((_bitboards[Board.Player1] & bit) != 0) return Board.Player1;
            if ((_bitboards[Board.Player2] & bit) != 0) return Board.Player2;
            return Board.Empty;
        }

        /// <summary>Kazanan taslarin (sutun, satir) listesi; oyun kazanilmadiysa bos.</summary>
        public List<(int col, int row)> GetWinningPositions()
        {
            var result = new List<(int, int)>();
            if (Status != GameStatus.Win || WinningMask == 0)
                return result;
            for (int c = 0; c < Board.Cols; c++)
                for (int r = 0; r < Board.Rows; r++)
                    if (((WinningMask >> Board.BitIndex(c, r)) & 1) != 0)
                        result.Add((c, r));
            return result;
        }

        // ------------------------------------------------------------------
        // Kopyalama ve senkronizasyon
        // ------------------------------------------------------------------

        public GameState Clone()
        {
            var g = new GameState();
            g.CopyFrom(this);
            return g;
        }

        private void CopyFrom(GameState other)
        {
            _bitboards[Board.Player1] = other._bitboards[Board.Player1];
            _bitboards[Board.Player2] = other._bitboards[Board.Player2];
            Array.Copy(other._heights, _heights, Board.Cols);
            _history.Clear();
            _history.AddRange(other._history);
            CurrentPlayer = other.CurrentPlayer;
            Status = other.Status;
            GameOver = other.GameOver;
            Winner = other.Winner;
            WinningMask = other.WinningMask;
        }

        /// <summary>
        /// Sunucunun to_dict() ciktisindaki alanlardan durumu geri yukler
        /// (Python from_dict karsiligi). winner yoksa 0 verilir.
        /// </summary>
        public void LoadSnapshot(ulong p1, ulong p2, IList<int> heights, IList<int> history,
                                 int current, int state, bool gameOver, int winner, ulong winningMask)
        {
            if (heights.Count != Board.Cols)
                throw new ArgumentException("heights uzunlugu " + Board.Cols + " olmali");
            _bitboards[Board.Player1] = p1;
            _bitboards[Board.Player2] = p2;
            for (int c = 0; c < Board.Cols; c++)
                _heights[c] = heights[c];
            _history.Clear();
            _history.AddRange(history);
            CurrentPlayer = current;
            Status = (GameStatus)state;
            GameOver = gameOver;
            Winner = winner;
            WinningMask = winningMask;
        }

        /// <summary>Hamle listesinden oyun olusturur. Gecersiz hamlede ArgumentException.</summary>
        public static GameState FromMoves(IEnumerable<int> moves, int startingPlayer = Board.Player1)
        {
            var g = new GameState(startingPlayer);
            int i = 0;
            foreach (int col in moves)
            {
                i++;
                if (!g.MakeMove(col))
                    throw new ArgumentException($"Gecersiz hamle #{i}: sutun {col}");
            }
            return g;
        }

        public override string ToString()
        {
            var sb = new StringBuilder();
            for (int r = Board.Rows - 1; r >= 0; r--)
            {
                sb.Append('|');
                for (int c = 0; c < Board.Cols; c++)
                {
                    int cell = GetCell(c, r);
                    sb.Append(' ').Append(cell == Board.Player1 ? 'X' : cell == Board.Player2 ? 'O' : '.').Append(" |");
                }
                sb.Append('\n');
            }
            sb.Append("| 0 | 1 | 2 | 3 | 4 | 5 | 6 |");
            return sb.ToString();
        }
    }
}
