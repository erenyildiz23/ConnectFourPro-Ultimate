// =============================================================================
// AIEngine.cs - Connect Four Pro
// Minimax + Alpha-Beta Pruning AI - Python ai_vs_human.py'nin C# karsiligi
// =============================================================================

using System;
using System.Collections.Generic;
using System.Linq;
using ConnectFourPro.Core;

namespace ConnectFourPro.AI
{
    public class AIEngine
    {
        // Heuristik skorlar
        private const long ScoreWin = 10000000000L;
        private const long ScoreBlock = -6000000L;
        private const long Score3Open = 5000L;
        private const long Score2Open = 300L;
        private const long ScoreCenter = 10L;

        public const int MaxDepthDefault = 7;

        public int PlayerId { get; private set; }
        public int OpponentId { get; private set; }
        public int Depth { get; private set; }

        private static readonly System.Random _random = new System.Random();

        // Acilis kitabi
        private static readonly Dictionary<string, int> OpeningBook = new Dictionary<string, int>
        {
            { "", 3 },
            { "3", 3 },
            { "3,3", 3 },
            { "3,2", 3 },
            { "3,4", 3 },
            { "3,3,3", 2 },
            { "0", 3 },
            { "1", 3 },
            { "2", 3 },
            { "4", 3 },
            { "5", 3 },
            { "6", 3 },
        };

        public AIEngine(int playerId, int depth = MaxDepthDefault)
        {
            PlayerId = playerId;
            OpponentId = playerId == GameConstants.Player2Piece
                ? GameConstants.Player1Piece
                : GameConstants.Player2Piece;
            Depth = depth;
        }

        public int EvaluateWindow(int[] window, int piece)
        {
            int score = 0;
            int pieceCount = window.Count(x => x == piece);
            int emptyCount = window.Count(x => x == GameConstants.Empty);
            int oppCount = window.Count(x => x == OpponentId);

            if (pieceCount == 4)
                score += (int)ScoreWin;
            else if (pieceCount == 3 && emptyCount == 1)
                score += (int)Score3Open;
            else if (pieceCount == 2 && emptyCount == 2)
                score += (int)Score2Open;

            if (oppCount == 3 && emptyCount == 1)
                score += (int)ScoreBlock;

            return score;
        }

        public long ScorePosition(ConnectFourGame game, int piece)
        {
            long score = 0;

            // 1. Merkez kontrolu
            int centerIdx = GameConstants.Cols / 2;
            int centerCount = 0;
            for (int r = 0; r < GameConstants.Rows; r++)
            {
                int idx = centerIdx * (GameConstants.Rows + 1) + r;
                if ((game.Bitboards[piece] >> idx & 1) == 1)
                    centerCount++;
            }
            score += centerCount * ScoreCenter;

            // 2. Tahta matrisini olustur
            int[,] board = game.GetBoardMatrix();

            // 3. Pencere tarama
            int[] window = new int[4];

            // Yatay
            for (int r = 0; r < GameConstants.Rows; r++)
            {
                for (int c = 0; c <= GameConstants.Cols - 4; c++)
                {
                    for (int i = 0; i < 4; i++)
                        window[i] = board[r, c + i];
                    score += EvaluateWindow(window, piece);
                }
            }

            // Dikey
            for (int c = 0; c < GameConstants.Cols; c++)
            {
                for (int r = 0; r <= GameConstants.Rows - 4; r++)
                {
                    for (int i = 0; i < 4; i++)
                        window[i] = board[r + i, c];
                    score += EvaluateWindow(window, piece);
                }
            }

            // Capraz /
            for (int r = 0; r <= GameConstants.Rows - 4; r++)
            {
                for (int c = 0; c <= GameConstants.Cols - 4; c++)
                {
                    for (int i = 0; i < 4; i++)
                        window[i] = board[r + i, c + i];
                    score += EvaluateWindow(window, piece);
                }
            }

            // Capraz \
            for (int r = 3; r < GameConstants.Rows; r++)
            {
                for (int c = 0; c <= GameConstants.Cols - 4; c++)
                {
                    for (int i = 0; i < 4; i++)
                        window[i] = board[r - i, c + i];
                    score += EvaluateWindow(window, piece);
                }
            }

            return score;
        }

        public bool IsTerminalNode(ConnectFourGame game)
        {
            if (game.CheckWin(PlayerId) || game.CheckWin(OpponentId))
                return true;
            if (game.GetValidLocations().Count == 0)
                return true;
            return false;
        }

        public (int? col, long score) Minimax(ConnectFourGame game, int depth, long alpha, long beta, bool maximizingPlayer)
        {
            var validLocations = game.GetValidLocations();
            bool isTerminal = IsTerminalNode(game);

            if (depth == 0 || isTerminal)
            {
                if (isTerminal)
                {
                    if (game.CheckWin(PlayerId))
                        return (null, 100000000000L);
                    if (game.CheckWin(OpponentId))
                        return (null, -100000000000L);
                    return (null, 0); // Beraberlik
                }
                return (null, ScorePosition(game, PlayerId));
            }

            if (validLocations.Count == 0)
                return (null, 0);

            // Budama icin sezgisel siralama (merkeze yakin sutunlar once)
            validLocations.Sort((a, b) => Math.Abs(a - GameConstants.Cols / 2).CompareTo(Math.Abs(b - GameConstants.Cols / 2)));

            if (maximizingPlayer)
            {
                long value = long.MinValue;
                int bestCol = validLocations[_random.Next(validLocations.Count)];

                foreach (int col in validLocations)
                {
                    var tempGame = game.Clone();
                    tempGame.MakeMove(col);
                    long newScore = Minimax(tempGame, depth - 1, alpha, beta, false).score;

                    if (newScore > value)
                    {
                        value = newScore;
                        bestCol = col;
                    }
                    alpha = Math.Max(alpha, value);
                    if (alpha >= beta) break;
                }
                return (bestCol, value);
            }
            else
            {
                long value = long.MaxValue;
                int bestCol = validLocations[_random.Next(validLocations.Count)];

                foreach (int col in validLocations)
                {
                    var tempGame = game.Clone();
                    tempGame.MakeMove(col);
                    long newScore = Minimax(tempGame, depth - 1, alpha, beta, true).score;

                    if (newScore < value)
                    {
                        value = newScore;
                        bestCol = col;
                    }
                    beta = Math.Min(beta, value);
                    if (alpha >= beta) break;
                }
                return (bestCol, value);
            }
        }

        public int? FindBestMove(ConnectFourGame game)
        {
            // 0. Dolu tahta kontrolu
            var validMoves = game.GetValidLocations();
            if (validMoves.Count == 0)
                return null;

            // 1. Acilis kitabi
            string historyKey = string.Join(",", game.MoveHistory);
            if (OpeningBook.TryGetValue(historyKey, out int bookMove))
            {
                if (game.IsValidLocation(bookMove))
                    return bookMove;
            }

            // 2. Minimax
            var gameCopy = game.Clone();
            try
            {
                var (col, score) = Minimax(gameCopy, Depth, long.MinValue, long.MaxValue, true);
                if (col.HasValue)
                    return col.Value;
            }
            catch (Exception e)
            {
                UnityEngine.Debug.LogError($"[AI ERROR] Minimax crashed: {e.Message}");
            }

            // 3. Fallback (guvenlik agi)
            return validMoves[_random.Next(validMoves.Count)];
        }
    }
}
