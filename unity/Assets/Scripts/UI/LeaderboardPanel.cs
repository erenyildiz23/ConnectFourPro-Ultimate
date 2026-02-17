// =============================================================================
// LeaderboardPanel.cs - Connect Four Pro
// Liderlik tablosu ekrani
// =============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using ConnectFourPro.Managers;
using ConnectFourPro.Network;

namespace ConnectFourPro.UI
{
    public class LeaderboardPanel : MonoBehaviour
    {
        [Header("UI Elements")]
        public Transform EntryListContent;
        public GameObject EntryPrefab;
        public TMP_Text InfoText;

        [Header("Navigation")]
        public Button BackButton;

        [Header("Colors")]
        public Color GoldColor = new Color(241f/255f, 196f/255f, 15f/255f);
        public Color SilverColor = new Color(189f/255f, 195f/255f, 199f/255f);
        public Color BronzeColor = new Color(205f/255f, 127f/255f, 50f/255f);
        public Color NormalColor = Color.white;

        private GameManager _gm;

        private void Start()
        {
            _gm = GameManager.Instance;
            BackButton?.onClick.AddListener(() => _gm?.SetState(GameAppState.Menu));
        }

        private void OnEnable()
        {
            FetchLeaderboard();
        }

        private void FetchLeaderboard()
        {
            if (InfoText != null)
                InfoText.text = "Yukleniyor...";

            _gm?.Network?.FetchLeaderboard(entries =>
            {
                // Eski listeyi temizle
                if (EntryListContent != null)
                {
                    foreach (Transform child in EntryListContent)
                    {
                        Destroy(child.gameObject);
                    }
                }

                if (entries == null || entries.Length == 0)
                {
                    if (InfoText != null)
                        InfoText.text = "Sunucuya baglanilamadi veya veri yok";
                    return;
                }

                if (InfoText != null)
                    InfoText.text = "";

                for (int i = 0; i < entries.Length && i < 10; i++)
                {
                    CreateLeaderboardEntry(i, entries[i]);
                }
            });
        }

        private void CreateLeaderboardEntry(int rank, LeaderboardEntry entry)
        {
            if (EntryPrefab == null || EntryListContent == null) return;

            var item = Instantiate(EntryPrefab, EntryListContent);

            var rankText = item.transform.Find("RankText")?.GetComponent<TMP_Text>();
            var nameText = item.transform.Find("NameText")?.GetComponent<TMP_Text>();
            var eloText = item.transform.Find("EloText")?.GetComponent<TMP_Text>();
            var statsText = item.transform.Find("StatsText")?.GetComponent<TMP_Text>();

            Color textColor;
            string prefix;
            switch (rank)
            {
                case 0: textColor = GoldColor; prefix = "1."; break;
                case 1: textColor = SilverColor; prefix = "2."; break;
                case 2: textColor = BronzeColor; prefix = "3."; break;
                default: textColor = NormalColor; prefix = $"{rank + 1}."; break;
            }

            if (rankText != null) { rankText.text = prefix; rankText.color = textColor; }
            if (nameText != null) { nameText.text = entry.username; nameText.color = textColor; }
            if (eloText != null) { eloText.text = $"ELO: {entry.rating}"; eloText.color = textColor; }
            if (statsText != null) { statsText.text = $"W:{entry.wins} L:{entry.losses}"; }
        }
    }
}
