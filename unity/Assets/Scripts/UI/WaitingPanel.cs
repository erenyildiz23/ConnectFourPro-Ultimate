// =============================================================================
// WaitingPanel.cs - Connect Four Pro
// Rakip bekleme ekrani
// =============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using ConnectFourPro.Managers;

namespace ConnectFourPro.UI
{
    public class WaitingPanel : MonoBehaviour
    {
        [Header("UI Elements")]
        public TMP_Text TitleText;
        public TMP_Text RoomCodeText;
        public TMP_Text WaitingDotsText;
        public Button CancelButton;

        private GameManager _gm;
        private float _dotTimer;
        private int _dotCount;

        private void Start()
        {
            _gm = GameManager.Instance;
            CancelButton?.onClick.AddListener(() => _gm?.ResetToMenu());
        }

        private void OnEnable()
        {
            RefreshRoomCode();
        }

        private void Update()
        {
            // Animasyonlu bekleme noktasi
            _dotTimer += Time.deltaTime;
            if (_dotTimer > 0.5f)
            {
                _dotTimer = 0;
                _dotCount = (_dotCount + 1) % 4;
                if (WaitingDotsText != null)
                    WaitingDotsText.text = "Bekleniyor" + new string('.', _dotCount);
            }
        }

        private void RefreshRoomCode()
        {
            if (_gm == null) _gm = GameManager.Instance;

            if (RoomCodeText != null && _gm != null)
                RoomCodeText.text = $"Oda Kodu: {_gm.RoomId ?? "..."}";
        }
    }
}
