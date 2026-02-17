// =============================================================================
// AISelectPanel.cs - Connect Four Pro
// AI zorluk secim ekrani
// =============================================================================

using UnityEngine;
using UnityEngine.UI;
using ConnectFourPro.Managers;

namespace ConnectFourPro.UI
{
    public class AISelectPanel : MonoBehaviour
    {
        [Header("Difficulty Buttons")]
        public Button EasyButton;   // Depth 2
        public Button MediumButton; // Depth 4
        public Button HardButton;   // Depth 6

        [Header("Navigation")]
        public Button BackButton;

        private GameManager _gm;

        private void Start()
        {
            _gm = GameManager.Instance;

            EasyButton?.onClick.AddListener(() => StartAI(2));
            MediumButton?.onClick.AddListener(() => StartAI(4));
            HardButton?.onClick.AddListener(() => StartAI(6));
            BackButton?.onClick.AddListener(() => _gm?.SetState(GameAppState.Menu));
        }

        private void StartAI(int depth)
        {
            _gm?.StartAIGame(depth);
        }
    }
}
