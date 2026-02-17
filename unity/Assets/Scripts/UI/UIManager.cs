// =============================================================================
// UIManager.cs - Connect Four Pro
// Ana UI yoneticisi - tum ekranlari kontrol eder
// Python gui_app.py'deki ekran cizim fonksiyonlarinin Unity karsiligi
// =============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using ConnectFourPro.Core;
using ConnectFourPro.Managers;

namespace ConnectFourPro.UI
{
    public class UIManager : MonoBehaviour
    {
        [Header("Screen Panels")]
        public GameObject LoginPanel;
        public GameObject MenuPanel;
        public GameObject AISelectPanel;
        public GameObject LobbyPanel;
        public GameObject WaitingPanel;
        public GameObject LeaderboardPanel;
        public GameObject GameHUDPanel;

        [Header("Status")]
        public TMP_Text StatusText;

        private GameManager _gm;

        private void Start()
        {
            _gm = GameManager.Instance;

            if (_gm != null)
            {
                _gm.OnStateChanged += OnStateChanged;
                _gm.OnStatusChanged += OnStatusChanged;
            }

            // Baslangic durumu
            ShowPanel(GameAppState.Login);
        }

        private void OnStateChanged(GameAppState newState)
        {
            ShowPanel(newState);
        }

        private void OnStatusChanged(string text)
        {
            if (StatusText != null)
                StatusText.text = text;
        }

        private void ShowPanel(GameAppState state)
        {
            // Tum panelleri gizle
            SetPanelActive(LoginPanel, false);
            SetPanelActive(MenuPanel, false);
            SetPanelActive(AISelectPanel, false);
            SetPanelActive(LobbyPanel, false);
            SetPanelActive(WaitingPanel, false);
            SetPanelActive(LeaderboardPanel, false);
            SetPanelActive(GameHUDPanel, false);

            // Ilgili paneli goster
            switch (state)
            {
                case GameAppState.Login:
                    SetPanelActive(LoginPanel, true);
                    break;
                case GameAppState.Menu:
                    SetPanelActive(MenuPanel, true);
                    break;
                case GameAppState.AISelect:
                    SetPanelActive(AISelectPanel, true);
                    break;
                case GameAppState.Lobby:
                    SetPanelActive(LobbyPanel, true);
                    break;
                case GameAppState.Waiting:
                    SetPanelActive(WaitingPanel, true);
                    break;
                case GameAppState.Leaderboard:
                    SetPanelActive(LeaderboardPanel, true);
                    break;
                case GameAppState.PlayingAI:
                case GameAppState.PlayingOnline:
                case GameAppState.Spectating:
                    SetPanelActive(GameHUDPanel, true);
                    break;
            }
        }

        private void SetPanelActive(GameObject panel, bool active)
        {
            if (panel != null)
                panel.SetActive(active);
        }
    }
}
