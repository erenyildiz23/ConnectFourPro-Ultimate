// =============================================================================
// LoginPanel.cs - Connect Four Pro
// Giris/Kayit ekrani
// =============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using ConnectFourPro.Managers;

namespace ConnectFourPro.UI
{
    public class LoginPanel : MonoBehaviour
    {
        [Header("Input Fields")]
        public TMP_InputField UsernameInput;
        public TMP_InputField PasswordInput;

        [Header("Buttons")]
        public Button LoginButton;
        public Button RegisterButton;
        public Button GuestButton;

        [Header("Feedback")]
        public TMP_Text FeedbackText;

        private GameManager _gm;

        private void Start()
        {
            _gm = GameManager.Instance;

            LoginButton?.onClick.AddListener(OnLoginClicked);
            RegisterButton?.onClick.AddListener(OnRegisterClicked);
            GuestButton?.onClick.AddListener(OnGuestClicked);

            // Enter ile giris
            if (PasswordInput != null)
            {
                PasswordInput.onSubmit.AddListener((_) => OnLoginClicked());
            }
        }

        private void OnLoginClicked()
        {
            string username = UsernameInput?.text?.Trim() ?? "";
            string password = PasswordInput?.text ?? "";

            if (string.IsNullOrEmpty(username) || string.IsNullOrEmpty(password))
            {
                ShowFeedback("Kullanici adi ve sifre gerekli!", Color.red);
                return;
            }

            SetButtonsInteractable(false);

            _gm.Network?.Login(username, password, (success, userData, error) =>
            {
                SetButtonsInteractable(true);

                if (success && userData != null)
                {
                    _gm.Username = userData.username;
                    _gm.UserId = userData.user_id;
                    _gm.UserElo = userData.rating;
                    _gm.IsGuest = false;
                    _gm.SetState(GameAppState.Menu);
                    _gm.SetStatus($"Hosgeldin {_gm.Username}!");
                    ClearInputs();
                }
                else
                {
                    ShowFeedback(error ?? "Giris basarisiz!", Color.red);
                }
            });
        }

        private void OnRegisterClicked()
        {
            string username = UsernameInput?.text?.Trim() ?? "";
            string password = PasswordInput?.text ?? "";

            if (string.IsNullOrEmpty(username) || string.IsNullOrEmpty(password))
            {
                ShowFeedback("Kullanici adi ve sifre gerekli!", Color.red);
                return;
            }

            if (username.Length < 3 || password.Length < 3)
            {
                ShowFeedback("En az 3 karakter gerekli!", Color.red);
                return;
            }

            SetButtonsInteractable(false);

            _gm.Network?.Register(username, password, (success, userId, error) =>
            {
                SetButtonsInteractable(true);

                if (success)
                {
                    _gm.Username = username;
                    _gm.UserId = userId;
                    _gm.UserElo = 1200;
                    _gm.IsGuest = false;
                    _gm.SetState(GameAppState.Menu);
                    _gm.SetStatus($"Kayit basarili! Hosgeldin {username}!");
                    ClearInputs();
                }
                else
                {
                    ShowFeedback(error ?? "Kayit basarisiz!", Color.red);
                }
            });
        }

        private void OnGuestClicked()
        {
            _gm.GuestLogin();
            ClearInputs();
        }

        private void ShowFeedback(string msg, Color color)
        {
            if (FeedbackText != null)
            {
                FeedbackText.text = msg;
                FeedbackText.color = color;
            }
        }

        private void ClearInputs()
        {
            if (UsernameInput != null) UsernameInput.text = "";
            if (PasswordInput != null) PasswordInput.text = "";
            if (FeedbackText != null) FeedbackText.text = "";
        }

        private void SetButtonsInteractable(bool interactable)
        {
            if (LoginButton != null) LoginButton.interactable = interactable;
            if (RegisterButton != null) RegisterButton.interactable = interactable;
            if (GuestButton != null) GuestButton.interactable = interactable;
        }
    }
}
