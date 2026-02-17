// =============================================================================
// GameManager.cs - Connect Four Pro
// Ana oyun yoneticisi ve durum makinesi
// Python gui_app.py'deki ConnectFourGUI sinifinin Unity karsiligi
// =============================================================================

using System;
using System.Threading;
using UnityEngine;
using ConnectFourPro.Core;
using ConnectFourPro.AI;
using ConnectFourPro.Network;
using ConnectFourPro.UI;

namespace ConnectFourPro.Managers
{
    public enum GameAppState
    {
        Login,
        Menu,
        AISelect,
        Lobby,
        Waiting,
        Leaderboard,
        PlayingAI,
        PlayingOnline,
        Spectating
    }

    public class GameManager : MonoBehaviour
    {
        public static GameManager Instance { get; private set; }

        [Header("References")]
        public BoardController Board;
        public UIManager UI;
        public NetworkClient Network;

        // Oyun durumu
        public GameAppState AppState { get; private set; } = GameAppState.Login;
        public ConnectFourGame Game { get; private set; }
        public AIEngine AI { get; private set; }

        // Oyuncu bilgileri
        public string Username { get; set; } = "";
        public int? UserId { get; set; }
        public int UserElo { get; set; } = 1200;
        public bool IsGuest { get; set; }
        public string OpponentName { get; set; } = "Rakip";
        public int OpponentElo { get; set; } = 1200;

        // Online oyun bilgileri
        public int MyPiece { get; set; } = GameConstants.Player1Piece;
        public string RoomId { get; set; }
        public bool IsSpectator { get; set; }

        // AI yonetimi
        private int _aiSessionId;
        private readonly object _aiLock = new object();
        private bool _aiThinking;
        private int? _pendingAIMove;
        private int _pendingAISession = -1;

        // Animasyon durumu
        public bool IsAnimating { get; set; }

        // Events
        public event Action<string> OnStatusChanged;
        public event Action<GameAppState> OnStateChanged;
        public event Action OnGameUpdated;
        public event Action OnGameOver;

        private string _statusText = "";
        public string StatusText
        {
            get => _statusText;
            private set
            {
                _statusText = value;
                OnStatusChanged?.Invoke(value);
            }
        }

        public bool AIThinking => _aiThinking;

        private void Awake()
        {
            if (Instance == null)
            {
                Instance = this;
                DontDestroyOnLoad(gameObject);
            }
            else
            {
                Destroy(gameObject);
                return;
            }

            Game = new ConnectFourGame();
        }

        private void Update()
        {
            // AI hamlesini ana thread'de isle
            if (_pendingAIMove.HasValue)
            {
                bool valid;
                int col;
                lock (_aiLock)
                {
                    valid = AI != null &&
                            AppState == GameAppState.PlayingAI &&
                            _pendingAISession == _aiSessionId;
                    col = _pendingAIMove.Value;
                }

                if (valid)
                {
                    _pendingAIMove = null;
                    _pendingAISession = -1;
                    ExecuteAIMove(col);
                }
                else
                {
                    Debug.Log($"[GameManager] Stale AI move discarded (state={AppState})");
                    _pendingAIMove = null;
                    _pendingAISession = -1;
                }
            }
        }

        // =========================================================================
        // DURUM YONETIMI
        // =========================================================================

        public void SetState(GameAppState newState)
        {
            Debug.Log($"[GameManager] State: {AppState} -> {newState}");
            AppState = newState;
            OnStateChanged?.Invoke(newState);
        }

        public void SetStatus(string text)
        {
            StatusText = text;
        }

        // =========================================================================
        // AI OTURUM YONETIMI
        // =========================================================================

        public void InvalidateAISession()
        {
            lock (_aiLock)
            {
                _aiSessionId++;
                _pendingAIMove = null;
                _pendingAISession = -1;
                _aiThinking = false;
                AI = null;
                Debug.Log($"[GameManager] AI invalidated, new session: {_aiSessionId}");
            }
        }

        public void StartAIGame(int depth)
        {
            Debug.Log($"[GameManager] Starting AI game, depth={depth}");
            InvalidateAISession();
            Game = new ConnectFourGame();

            lock (_aiLock)
            {
                AI = new AIEngine(GameConstants.Player2Piece, depth);
            }

            MyPiece = GameConstants.Player1Piece;
            IsSpectator = false;
            SetState(GameAppState.PlayingAI);
            SetStatus("Senin siran!");
            Board?.RefreshBoard();
        }

        // =========================================================================
        // OYUNCU HAMLESI
        // =========================================================================

        public void HandleColumnClick(int col)
        {
            if (IsAnimating || Game.GameOver || IsSpectator)
                return;

            if (AppState == GameAppState.PlayingAI)
            {
                if (Game.CurrentPlayer != GameConstants.Player1Piece)
                    return;
                if (_aiThinking)
                    return;
                lock (_aiLock)
                {
                    if (AI == null) return;
                }
            }
            else if (AppState == GameAppState.PlayingOnline)
            {
                if (Game.CurrentPlayer != MyPiece)
                    return;
            }
            else
            {
                return;
            }

            if (!Game.IsValidLocation(col))
                return;

            Debug.Log($"[GameManager] Player click: col={col}, state={AppState}");
            int row = Game.GetColumnHeight(col);
            Board?.AnimateDrop(col, row, Game.CurrentPlayer, () => FinishMove(col));
        }

        private void FinishMove(int col)
        {
            Debug.Log($"[GameManager] FinishMove: col={col}, state={AppState}");

            if (!Game.MakeMove(col))
                return;

            OnGameUpdated?.Invoke();

            // ONLINE MOD
            if (AppState == GameAppState.PlayingOnline)
            {
                Debug.Log("[GameManager] Online mode - sending move to server");
                Network?.SendMove(col);

                if (Game.GameOver)
                {
                    Debug.Log("[GameManager] Game ended - waiting for server confirmation");
                }
                else
                {
                    SetStatus("Rakibin sirasi...");
                }
                return;
            }

            // AI MOD
            if (AppState == GameAppState.PlayingAI)
            {
                Board?.RefreshBoard();

                if (Game.GameOver)
                {
                    HandleGameOver();
                    return;
                }

                lock (_aiLock)
                {
                    if (AI != null && Game.CurrentPlayer == GameConstants.Player2Piece)
                    {
                        Debug.Log("[GameManager] AI mode - starting AI thread");
                        SetStatus("AI dusunuyor...");
                        _aiThinking = true;
                        int sid = _aiSessionId;
                        var thread = new Thread(() => AIMove(sid));
                        thread.IsBackground = true;
                        thread.Start();
                    }
                }
            }
        }

        // =========================================================================
        // AI HAMLESI
        // =========================================================================

        private void AIMove(int sid)
        {
            Debug.Log($"[AI] Thread started, session={sid}");
            Thread.Sleep(300);

            // ON KONTROL
            lock (_aiLock)
            {
                if (AI == null || sid != _aiSessionId || AppState != GameAppState.PlayingAI)
                {
                    Debug.Log("[AI] Thread aborted in pre-check");
                    _aiThinking = false;
                    return;
                }
            }

            // HESAPLA
            int? col;
            try
            {
                col = AI.FindBestMove(Game);
            }
            catch (Exception e)
            {
                Debug.LogError($"[AI ERROR] {e.Message}");
                col = null;
            }

            // SON KONTROL
            lock (_aiLock)
            {
                if (AI == null || sid != _aiSessionId || AppState != GameAppState.PlayingAI)
                {
                    Debug.Log("[AI] Thread aborted in post-check");
                    _aiThinking = false;
                    return;
                }

                _aiThinking = false;
                if (col.HasValue && !Game.GameOver)
                {
                    Debug.Log($"[AI] Move ready: col={col.Value}");
                    _pendingAIMove = col.Value;
                    _pendingAISession = sid;
                }
            }
        }

        private void ExecuteAIMove(int col)
        {
            Debug.Log($"[GameManager] ExecuteAIMove: col={col}");
            lock (_aiLock)
            {
                if (AI == null || AppState != GameAppState.PlayingAI)
                    return;
            }

            if (Game.GameOver || !Game.IsValidLocation(col))
                return;

            int row = Game.GetColumnHeight(col);
            Board?.AnimateDrop(col, row, GameConstants.Player2Piece, () => FinishAIMove(col));
        }

        private void FinishAIMove(int col)
        {
            Debug.Log($"[GameManager] FinishAIMove: col={col}");
            lock (_aiLock)
            {
                if (AI == null || AppState != GameAppState.PlayingAI)
                    return;
            }

            if (!Game.MakeMove(col))
                return;

            OnGameUpdated?.Invoke();
            Board?.RefreshBoard();

            if (Game.GameOver)
            {
                HandleGameOver();
            }
            else
            {
                SetStatus("Senin siran!");
            }
        }

        // =========================================================================
        // OYUN SONU
        // =========================================================================

        public void HandleGameOver()
        {
            int? w = Game.Winner;
            Debug.Log($"[GameManager] Game over: winner={w}");

            if (w == GameConstants.Player1Piece)
            {
                if (AppState == GameAppState.PlayingAI || MyPiece == GameConstants.Player1Piece)
                    SetStatus("Kazandin!");
                else
                    SetStatus($"{OpponentName} kazandi!");
            }
            else if (w == GameConstants.Player2Piece)
            {
                if (AppState == GameAppState.PlayingAI)
                    SetStatus("AI kazandi!");
                else if (MyPiece == GameConstants.Player2Piece)
                    SetStatus("Kazandin!");
                else
                    SetStatus($"{OpponentName} kazandi!");
            }
            else
            {
                SetStatus("Berabere!");
            }

            OnGameOver?.Invoke();
            Board?.RefreshBoard();
        }

        // =========================================================================
        // ONLINE OYUN YONETIMI
        // =========================================================================

        public void CreateOnlineGame()
        {
            Debug.Log("[GameManager] Creating online game");
            InvalidateAISession();
            Network?.CreateGame(Username);
        }

        public void JoinOnlineGame(string roomId)
        {
            Debug.Log($"[GameManager] Joining game: {roomId}");
            InvalidateAISession();
            RoomId = roomId.ToUpper();
            IsSpectator = false;
            Network?.JoinGame(RoomId, Username);
        }

        public void SpectateGame(string roomId)
        {
            Debug.Log($"[GameManager] Spectating game: {roomId}");
            InvalidateAISession();
            RoomId = roomId.ToUpper();
            IsSpectator = true;
            Network?.JoinGame(RoomId, Username);
            SetState(GameAppState.Spectating);
        }

        // =========================================================================
        // NETWORK EVENT HANDLER'LARI
        // =========================================================================

        public void OnNetworkGameCreated(string roomId, int playerPiece)
        {
            RoomId = roomId;
            MyPiece = playerPiece;
            IsSpectator = false;
            SetState(GameAppState.Waiting);
            SetStatus($"Oda: {RoomId}");
        }

        public void OnNetworkGameJoined(string roomId, int playerPiece, string role, string oppName, int oppElo)
        {
            RoomId = roomId;
            MyPiece = playerPiece;
            if (role == "spectator")
            {
                IsSpectator = true;
                SetState(GameAppState.Spectating);
            }
            else
            {
                IsSpectator = false;
                OpponentName = oppName;
                OpponentElo = oppElo;
            }
        }

        public void OnNetworkGameStart(string oppName, int oppElo)
        {
            Debug.Log("=== ONLINE GAME STARTING ===");
            InvalidateAISession();

            Game = new ConnectFourGame();
            IsSpectator = false;
            OpponentName = oppName;
            OpponentElo = oppElo;

            SetState(GameAppState.PlayingOnline);
            Board?.RefreshBoard();

            string turnMsg = Game.CurrentPlayer == MyPiece ? " Senin siran." : " Rakibin sirasi.";
            SetStatus("Oyun basladi!" + turnMsg);
        }

        public void OnNetworkMoveMade(int col, int newCurrent, long[] bitboards, int[] heights, System.Collections.Generic.List<int> history)
        {
            int serverHistoryLen = history.Count;
            int localHistoryLen = Game.MoveHistory.Count;

            // Ben yaptim bu hamleyi - animasyon yapma, sadece sync et
            if (localHistoryLen == serverHistoryLen)
            {
                Debug.Log($"[GameManager] Skipping animation (local={localHistoryLen}, server={serverHistoryLen})");
                SyncGameState(bitboards, heights, history, newCurrent);

                if (Game.GameOver)
                    HandleGameOver();
                else
                    SetStatus("Rakibin sirasi...");
                return;
            }

            // Rakibin hamlesi - animasyon goster
            int moveMaker = newCurrent == GameConstants.Player1Piece
                ? GameConstants.Player2Piece
                : GameConstants.Player1Piece;

            int row = Game.GetColumnHeight(col);

            Debug.Log($"[GameManager] Opponent move - animating: col={col}, row={row}, piece={moveMaker}");
            Board?.AnimateDrop(col, row, moveMaker, () =>
            {
                SyncGameState(bitboards, heights, history, newCurrent);
                Board?.RefreshBoard();

                if (Game.GameOver)
                    HandleGameOver();
                else if (Game.CurrentPlayer == MyPiece)
                    SetStatus("Senin siran!");
                else
                    SetStatus("Rakibin sirasi...");
            });
        }

        private void SyncGameState(long[] bitboards, int[] heights, System.Collections.Generic.List<int> history, int current)
        {
            Game.Bitboards[GameConstants.Player1Piece] = bitboards[GameConstants.Player1Piece];
            Game.Bitboards[GameConstants.Player2Piece] = bitboards[GameConstants.Player2Piece];
            System.Array.Copy(heights, Game.Heights, heights.Length);
            Game.MoveHistory.Clear();
            Game.MoveHistory.AddRange(history);

            // GameOver kontrolu
            if (Game.CheckWin(GameConstants.Player1Piece) || Game.CheckWin(GameConstants.Player2Piece))
            {
                // game_over flag'ini set et - field'lara dogrudan erisim yok,
                // ama CheckWin zaten WinningMask'i set eder
            }

            OnGameUpdated?.Invoke();
        }

        public void OnNetworkGameOver(int? winner)
        {
            if (IsSpectator)
            {
                SetStatus(winner == 1 ? "Kirmizi kazandi!" : (winner == 2 ? "Sari kazandi!" : "Berabere!"));
            }
            else
            {
                SetStatus(winner == MyPiece ? "Kazandin!" : (winner == null ? "Berabere!" : "Kaybettin."));
            }
            OnGameOver?.Invoke();
        }

        public void OnNetworkEloUpdate(int newElo, int change)
        {
            UserElo = newElo;
            string result = change > 0 ? "Kazandin" : "Kaybettin";
            string sign = change > 0 ? "+" : "";
            SetStatus($"{result}! ELO {sign}{change} ({UserElo})");
        }

        public void OnNetworkOpponentDisconnected()
        {
            SetStatus("Rakip baglantisi koptu!");
        }

        // =========================================================================
        // MENU ISLEMLERI
        // =========================================================================

        public void ResetToMenu()
        {
            Debug.Log("[GameManager] Reset to menu");
            InvalidateAISession();
            Network?.Disconnect();
            RoomId = null;
            IsSpectator = false;
            Game = new ConnectFourGame();
            SetState(GameAppState.Menu);
        }

        public void GuestLogin()
        {
            Username = $"Misafir_{DateTime.Now.Ticks % 10000}";
            UserId = null;
            UserElo = 1200;
            IsGuest = true;
            SetState(GameAppState.Menu);
            SetStatus("");
            Debug.Log($"[GameManager] Guest login: {Username}");
        }

        public void Logout()
        {
            Debug.Log("[GameManager] Logout");
            Username = "";
            UserId = null;
            UserElo = 1200;
            IsGuest = false;
            SetState(GameAppState.Login);
            SetStatus("");
        }
    }
}
