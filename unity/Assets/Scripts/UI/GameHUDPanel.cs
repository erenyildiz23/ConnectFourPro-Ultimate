// =============================================================================
// GameHUDPanel.cs - Connect Four Pro
// Oyun icin bilgi paneli (HUD)
// Python gui_app.py draw_info_panel fonksiyonunun karsiligi
// =============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using ConnectFourPro.Core;
using ConnectFourPro.Managers;

namespace ConnectFourPro.UI
{
    public class GameHUDPanel : MonoBehaviour
    {
        [Header("Player 1 Info")]
        public Image Player1ColorIcon;
        public TMP_Text Player1NameText;
        public TMP_Text Player1EloText;
        public GameObject Player1TurnIndicator;

        [Header("Player 2 Info")]
        public Image Player2ColorIcon;
        public TMP_Text Player2NameText;
        public TMP_Text Player2EloText;
        public GameObject Player2TurnIndicator;

        [Header("Game Info")]
        public TMP_Text RoomIdText;
        public TMP_Text MoveCountText;
        public TMP_Text StatusText;
        public TMP_Text GameModeText;

        [Header("Buttons")]
        public Button MenuButton;

        [Header("Colors")]
        public Color RedColor = new Color(233f/255f, 69f/255f, 96f/255f);
        public Color YellowColor = new Color(241f/255f, 196f/255f, 15f/255f);
        public Color TurnActiveColor = new Color(46f/255f, 204f/255f, 113f/255f);

        private GameManager _gm;

        private void Start()
        {
            _gm = GameManager.Instance;

            MenuButton?.onClick.AddListener(() => _gm?.ResetToMenu());

            if (_gm != null)
            {
                _gm.OnGameUpdated += RefreshHUD;
                _gm.OnStatusChanged += OnStatusChanged;
                _gm.OnGameOver += RefreshHUD;
            }

            // Renk ikonlari
            if (Player1ColorIcon != null) Player1ColorIcon.color = RedColor;
            if (Player2ColorIcon != null) Player2ColorIcon.color = YellowColor;
        }

        private void OnEnable()
        {
            RefreshHUD();
        }

        private void Update()
        {
            // Sira gostergelerini guncelle
            UpdateTurnIndicators();
        }

        private void OnStatusChanged(string text)
        {
            if (StatusText != null)
                StatusText.text = text;
        }

        private void RefreshHUD()
        {
            if (_gm == null) return;

            var game = _gm.Game;
            if (game == null) return;

            // Oyun modu
            if (GameModeText != null)
            {
                switch (_gm.AppState)
                {
                    case GameAppState.PlayingAI:
                        GameModeText.text = "AI'ya Karsi";
                        break;
                    case GameAppState.PlayingOnline:
                        GameModeText.text = "Online Mac";
                        break;
                    case GameAppState.Spectating:
                        GameModeText.text = "CANLI YAYIN";
                        break;
                }
            }

            // Oyuncu 1 bilgisi
            if (_gm.AppState == GameAppState.PlayingAI || _gm.MyPiece == GameConstants.Player1Piece)
            {
                SetPlayerInfo(Player1NameText, Player1EloText, _gm.Username, _gm.UserElo);
            }
            else
            {
                SetPlayerInfo(Player1NameText, Player1EloText, _gm.OpponentName, _gm.OpponentElo);
            }

            // Oyuncu 2 bilgisi
            if (_gm.AppState == GameAppState.PlayingAI)
            {
                string aiName = _gm.AI != null ? $"AI (D{_gm.AI.Depth})" : "AI";
                SetPlayerInfo(Player2NameText, Player2EloText, aiName, 0, hideElo: true);
            }
            else if (_gm.MyPiece == GameConstants.Player2Piece)
            {
                SetPlayerInfo(Player2NameText, Player2EloText, _gm.Username, _gm.UserElo);
            }
            else
            {
                SetPlayerInfo(Player2NameText, Player2EloText, _gm.OpponentName, _gm.OpponentElo);
            }

            // Oda ve hamle bilgisi
            if (RoomIdText != null)
            {
                RoomIdText.text = !string.IsNullOrEmpty(_gm.RoomId) ? $"Oda: {_gm.RoomId}" : "";
            }

            if (MoveCountText != null)
            {
                MoveCountText.text = $"Hamle: {game.MoveHistory.Count}";
            }
        }

        private void SetPlayerInfo(TMP_Text nameText, TMP_Text eloText, string name, int elo, bool hideElo = false)
        {
            if (nameText != null)
            {
                nameText.text = name.Length > 10 ? name.Substring(0, 10) : name;
            }
            if (eloText != null)
            {
                eloText.text = hideElo ? "" : $"ELO: {elo}";
                eloText.gameObject.SetActive(!hideElo);
            }
        }

        private void UpdateTurnIndicators()
        {
            if (_gm == null || _gm.Game == null) return;

            bool p1Turn = _gm.Game.CurrentPlayer == GameConstants.Player1Piece && !_gm.Game.GameOver;
            bool p2Turn = _gm.Game.CurrentPlayer == GameConstants.Player2Piece && !_gm.Game.GameOver;

            if (Player1TurnIndicator != null) Player1TurnIndicator.SetActive(p1Turn);
            if (Player2TurnIndicator != null) Player2TurnIndicator.SetActive(p2Turn);
        }
    }
}
