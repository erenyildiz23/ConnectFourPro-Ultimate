// =============================================================================
// LobbyPanel.cs - Connect Four Pro
// Online lobi ekrani
// =============================================================================

using System.Collections;
using UnityEngine;
using UnityEngine.UI;
using TMPro;
using ConnectFourPro.Managers;
using ConnectFourPro.Network;

namespace ConnectFourPro.UI
{
    public class LobbyPanel : MonoBehaviour
    {
        [Header("Buttons")]
        public Button CreateGameButton;
        public Button RefreshButton;
        public Button BackButton;

        [Header("Game List")]
        public Transform GameListContent;
        public GameObject GameListItemPrefab;

        [Header("Info")]
        public TMP_Text InfoText;

        private GameManager _gm;
        private float _lastRefreshTime;

        private void Start()
        {
            _gm = GameManager.Instance;

            CreateGameButton?.onClick.AddListener(() => _gm?.CreateOnlineGame());
            RefreshButton?.onClick.AddListener(RefreshGames);
            BackButton?.onClick.AddListener(() => _gm?.ResetToMenu());
        }

        private void OnEnable()
        {
            RefreshGames();
        }

        private void Update()
        {
            // Her 3 saniyede bir otomatik yenile
            if (Time.time - _lastRefreshTime > 3f)
            {
                RefreshGames();
            }
        }

        private void RefreshGames()
        {
            _lastRefreshTime = Time.time;

            _gm?.Network?.FetchActiveGames(games =>
            {
                // Eski listeyi temizle
                if (GameListContent != null)
                {
                    foreach (Transform child in GameListContent)
                    {
                        Destroy(child.gameObject);
                    }
                }

                if (games == null || games.Length == 0)
                {
                    if (InfoText != null)
                        InfoText.text = "Aktif oyun yok. Yeni bir oyun olusturun!";
                    return;
                }

                if (InfoText != null)
                    InfoText.text = $"{games.Length} aktif oyun";

                foreach (var game in games)
                {
                    CreateGameListItem(game);
                }
            });
        }

        private void CreateGameListItem(ActiveGameData game)
        {
            if (GameListItemPrefab == null || GameListContent == null) return;

            var item = Instantiate(GameListItemPrefab, GameListContent);

            // Oda ID
            var roomText = item.transform.Find("RoomText")?.GetComponent<TMP_Text>();
            if (roomText != null) roomText.text = game.room_id;

            // Oyuncu 1
            var p1Text = item.transform.Find("Player1Text")?.GetComponent<TMP_Text>();
            if (p1Text != null) p1Text.text = $"{game.p1} ({game.p1_elo})";

            // Oyuncu 2
            var p2Text = item.transform.Find("Player2Text")?.GetComponent<TMP_Text>();
            if (p2Text != null)
            {
                p2Text.text = game.p2 == "Bekleniyor..." ? game.p2 : $"{game.p2} ({game.p2_elo})";
            }

            // Durum ve buton
            var statusText = item.transform.Find("StatusText")?.GetComponent<TMP_Text>();
            var actionButton = item.transform.Find("ActionButton")?.GetComponent<Button>();
            var actionButtonText = actionButton?.GetComponentInChildren<TMP_Text>();

            if (game.status == "WAITING")
            {
                if (statusText != null) statusText.text = "Bekliyor";
                if (actionButtonText != null) actionButtonText.text = "Katil";
                actionButton?.onClick.AddListener(() => _gm?.JoinOnlineGame(game.room_id));
            }
            else
            {
                if (statusText != null) statusText.text = "Oyunda";
                if (actionButtonText != null) actionButtonText.text = "Izle";
                actionButton?.onClick.AddListener(() => _gm?.SpectateGame(game.room_id));
            }
        }
    }
}
