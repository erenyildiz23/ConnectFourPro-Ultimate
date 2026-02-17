// =============================================================================
// MainMenuPanel.cs - Connect Four Pro
// Ana menu ekrani
// =============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using ConnectFourPro.Managers;

namespace ConnectFourPro.UI
{
    public class MainMenuPanel : MonoBehaviour
    {
        [Header("Player Info")]
        public TMP_Text PlayerNameText;
        public TMP_Text PlayerEloText;

        [Header("Buttons")]
        public Button PlayAIButton;
        public Button OnlineLobbyButton;
        public Button LeaderboardButton;
        public Button LogoutButton;
        public Button QuitButton;

        private GameManager _gm;

        private void Start()
        {
            _gm = GameManager.Instance;

            PlayAIButton?.onClick.AddListener(() => _gm?.SetState(GameAppState.AISelect));
            OnlineLobbyButton?.onClick.AddListener(() =>
            {
                _gm?.SetState(GameAppState.Lobby);
            });
            LeaderboardButton?.onClick.AddListener(() => _gm?.SetState(GameAppState.Leaderboard));
            LogoutButton?.onClick.AddListener(() => _gm?.Logout());
            QuitButton?.onClick.AddListener(() =>
            {
#if UNITY_EDITOR
                UnityEditor.EditorApplication.isPlaying = false;
#else
                Application.Quit();
#endif
            });
        }

        private void OnEnable()
        {
            RefreshPlayerInfo();
        }

        private void RefreshPlayerInfo()
        {
            if (_gm == null) _gm = GameManager.Instance;
            if (_gm == null) return;

            if (PlayerNameText != null)
            {
                PlayerNameText.text = _gm.IsGuest ? $"Misafir: {_gm.Username}" : _gm.Username;
            }

            if (PlayerEloText != null)
            {
                PlayerEloText.text = _gm.IsGuest ? "" : $"ELO: {_gm.UserElo}";
                PlayerEloText.gameObject.SetActive(!_gm.IsGuest);
            }
        }
    }
}
