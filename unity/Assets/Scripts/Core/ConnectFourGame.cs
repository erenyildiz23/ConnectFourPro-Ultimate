// =============================================================================
// ConnectFourGame.cs - Connect Four Pro
// Bitboard tabanli oyun motoru - Python game_core.py'nin C# karsiligi
// =============================================================================

using System.Collections.Generic;

namespace ConnectFourPro.Core
{
    public class ConnectFourGame
    {
        // Bitboard representation - her oyuncu icin 64-bit tam sayi
        public long[] Bitboards { get; private set; } = new long[3]; // index 1 = P1, index 2 = P2
        public int[] Heights { get; private set; } = new int[GameConstants.Cols];
        public List<int> MoveHistory { get; private set; } = new List<int>();
        public int MoveCount { get; private set; }
        public int CurrentPlayer { get; private set; }
        public int GameState { get; private set; }
        public bool GameOver { get; private set; }
        public int? Winner { get; private set; }
        public long WinningMask { get; private set; }

        public ConnectFourGame(int startingPlayer = GameConstants.Player1Piece)
        {
            Reset(startingPlayer);
        }

        public void Reset(int startingPlayer = GameConstants.Player1Piece)
        {
            Bitboards[GameConstants.Player1Piece] = 0;
            Bitboards[GameConstants.Player2Piece] = 0;

            for (int c = 0; c < GameConstants.Cols; c++)
            {
                Heights[c] = c * (GameConstants.Rows + 1);
            }

            MoveHistory = new List<int>();
            MoveCount = 0;
            CurrentPlayer = startingPlayer;
            GameState = GameConstants.StatePlaying;
            GameOver = false;
            Winner = null;
            WinningMask = 0;
        }

        public bool MakeMove(int col)
        {
            if (GameOver)
                return false;

            if (!IsValidLocation(col))
                return false;

            // 1. Bitboard guncelle
            long moveBit = 1L << Heights[col];
            Bitboards[CurrentPlayer] ^= moveBit;

            // 2. State guncelle
            Heights[col]++;
            MoveHistory.Add(col);
            MoveCount++;

            // 3. Kazanma/Beraberlik kontrolu
            if (CheckWin(CurrentPlayer))
            {
                GameState = GameConstants.StateWin;
                GameOver = true;
                Winner = CurrentPlayer;
            }
            else if (MoveCount >= GameConstants.Rows * GameConstants.Cols)
            {
                GameState = GameConstants.StateDraw;
                GameOver = true;
                Winner = null;
            }
            else
            {
                SwitchPlayer();
            }

            return true;
        }

        public void SwitchPlayer()
        {
            CurrentPlayer = CurrentPlayer == GameConstants.Player2Piece
                ? GameConstants.Player1Piece
                : GameConstants.Player2Piece;
        }

        public bool IsValidLocation(int col)
        {
            if (col < 0 || col >= GameConstants.Cols)
                return false;

            int topIndex = col * (GameConstants.Rows + 1) + GameConstants.Rows - 1;
            return Heights[col] <= topIndex;
        }

        public List<int> GetValidLocations()
        {
            var valid = new List<int>();
            for (int c = 0; c < GameConstants.Cols; c++)
            {
                if (IsValidLocation(c))
                    valid.Add(c);
            }
            return valid;
        }

        public bool CheckWin(int player)
        {
            long bb = Bitboards[player];

            // Yonler: Dikey, Yatay, Capraz /, Capraz \
            int[] directions = { 1, GameConstants.Rows + 1, GameConstants.Rows + 2, GameConstants.Rows };

            foreach (int d in directions)
            {
                long m = bb & (bb >> d);
                if ((m & (m >> (2 * d))) != 0)
                {
                    long tempMask = bb & (bb >> d) & (bb >> (2 * d)) & (bb >> (3 * d));
                    if (tempMask != 0)
                    {
                        WinningMask = tempMask | (tempMask << d) | (tempMask << (2 * d)) | (tempMask << (3 * d));
                        return true;
                    }
                }
            }
            return false;
        }

        public ConnectFourGame Clone()
        {
            var newGame = new ConnectFourGame(CurrentPlayer);
            newGame.Bitboards[GameConstants.Player1Piece] = Bitboards[GameConstants.Player1Piece];
            newGame.Bitboards[GameConstants.Player2Piece] = Bitboards[GameConstants.Player2Piece];
            System.Array.Copy(Heights, newGame.Heights, Heights.Length);
            newGame.MoveHistory = new List<int>(MoveHistory);
            newGame.MoveCount = MoveCount;
            newGame.GameState = GameState;
            newGame.GameOver = GameOver;
            newGame.Winner = Winner;
            newGame.WinningMask = WinningMask;
            return newGame;
        }

        /// <summary>
        /// Bitboard'dan 2D tahta matrisini olusturur (AI skorlama icin)
        /// </summary>
        public int[,] GetBoardMatrix()
        {
            var board = new int[GameConstants.Rows, GameConstants.Cols];
            for (int c = 0; c < GameConstants.Cols; c++)
            {
                for (int r = 0; r < GameConstants.Rows; r++)
                {
                    int idx = c * (GameConstants.Rows + 1) + r;
                    if ((Bitboards[GameConstants.Player1Piece] >> idx & 1) == 1)
                        board[r, c] = GameConstants.Player1Piece;
                    else if ((Bitboards[GameConstants.Player2Piece] >> idx & 1) == 1)
                        board[r, c] = GameConstants.Player2Piece;
                }
            }
            return board;
        }

        /// <summary>
        /// Belirli bir pozisyonun kazanan pozisyon olup olmadigini kontrol eder
        /// </summary>
        public bool IsWinningPosition(int col, int row)
        {
            if (WinningMask == 0) return false;
            int idx = col * (GameConstants.Rows + 1) + row;
            return ((WinningMask >> idx) & 1) == 1;
        }

        /// <summary>
        /// Belirli bir hucredeki tasi dondurur (0=bos, 1=P1, 2=P2)
        /// </summary>
        public int GetCell(int col, int row)
        {
            int idx = col * (GameConstants.Rows + 1) + row;
            if ((Bitboards[GameConstants.Player1Piece] >> idx & 1) == 1)
                return GameConstants.Player1Piece;
            if ((Bitboards[GameConstants.Player2Piece] >> idx & 1) == 1)
                return GameConstants.Player2Piece;
            return GameConstants.Empty;
        }

        /// <summary>
        /// Belirli bir sutundaki mevcut satir yuksekligini dondurur
        /// </summary>
        public int GetColumnHeight(int col)
        {
            return Heights[col] - col * (GameConstants.Rows + 1);
        }
    }
}
