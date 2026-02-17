// =============================================================================
// SceneSetup.cs - Connect Four Pro
// Sahne baslatma ve obje olusturma
// Unity Editor'de sahneyi programatik olarak kurar
// =============================================================================
// KULLANIM:
// 1. Unity'de bos bir sahne acin
// 2. Bos bir GameObject olusturun ve bu script'i ekleyin
// 3. Play'e basin - tum UI ve oyun objeleri otomatik olusturulur
// =============================================================================

using UnityEngine;
using UnityEngine.UI;
using TMPro;
using ConnectFourPro.UI;
using ConnectFourPro.Network;

namespace ConnectFourPro.Managers
{
    public class SceneSetup : MonoBehaviour
    {
        [Header("Auto-Setup on Start")]
        public bool AutoSetup = true;

        private void Awake()
        {
            if (AutoSetup)
            {
                SetupScene();
            }
        }

        public void SetupScene()
        {
            // 1. Kamera ayarlari
            SetupCamera();

            // 2. GameManager
            var gmObj = new GameObject("GameManager");
            var gm = gmObj.AddComponent<GameManager>();

            // 3. Board
            var boardObj = new GameObject("Board");
            var board = boardObj.AddComponent<BoardController>();
            gm.Board = board;

            // 4. Network
            var netObj = new GameObject("NetworkClient");
            netObj.transform.SetParent(gmObj.transform);
            var network = netObj.AddComponent<NetworkClient>();
            gm.Network = network;

            // 5. UI Canvas
            var canvas = CreateUICanvas();
            var uiManager = canvas.AddComponent<UIManager>();
            gm.UI = uiManager;

            // 6. UI Paneller
            uiManager.LoginPanel = CreateLoginPanel(canvas.transform);
            uiManager.MenuPanel = CreateMenuPanel(canvas.transform);
            uiManager.AISelectPanel = CreateAISelectPanel(canvas.transform);
            uiManager.LobbyPanel = CreateLobbyPanel(canvas.transform);
            uiManager.WaitingPanel = CreateWaitingPanel(canvas.transform);
            uiManager.LeaderboardPanel = CreateLeaderboardPanel(canvas.transform);
            uiManager.GameHUDPanel = CreateGameHUDPanel(canvas.transform);

            // 7. Global Status Text
            var statusObj = CreateTextElement(canvas.transform, "StatusText", "",
                new Vector2(0.5f, 0), new Vector2(0.5f, 0),
                new Vector2(0, 10), new Vector2(600, 40));
            uiManager.StatusText = statusObj.GetComponent<TMP_Text>();

            Debug.Log("[SceneSetup] Scene setup complete!");
        }

        private void SetupCamera()
        {
            var cam = Camera.main;
            if (cam == null)
            {
                var camObj = new GameObject("MainCamera");
                cam = camObj.AddComponent<Camera>();
                camObj.tag = "MainCamera";
            }

            cam.transform.position = new Vector3(0, 0, -10);
            cam.orthographic = true;
            cam.orthographicSize = 5;
            cam.backgroundColor = new Color(26f / 255f, 26f / 255f, 46f / 255f);
        }

        // =========================================================================
        // UI PANEL OLUSTURMA
        // =========================================================================

        private GameObject CreateUICanvas()
        {
            var canvasObj = new GameObject("UICanvas");
            var canvas = canvasObj.AddComponent<Canvas>();
            canvas.renderMode = RenderMode.ScreenSpaceOverlay;
            canvas.sortingOrder = 10;

            canvasObj.AddComponent<CanvasScaler>().uiScaleMode = CanvasScaler.ScaleMode.ScaleWithScreenSize;
            canvasObj.GetComponent<CanvasScaler>().referenceResolution = new Vector2(1280, 720);
            canvasObj.AddComponent<GraphicRaycaster>();

            // EventSystem
            if (FindAnyObjectByType<UnityEngine.EventSystems.EventSystem>() == null)
            {
                var esObj = new GameObject("EventSystem");
                esObj.AddComponent<UnityEngine.EventSystems.EventSystem>();
                esObj.AddComponent<UnityEngine.EventSystems.StandaloneInputModule>();
            }

            return canvasObj;
        }

        private GameObject CreateLoginPanel(Transform parent)
        {
            var panel = CreatePanel(parent, "LoginPanel", new Color(26f / 255f, 26f / 255f, 46f / 255f, 0.95f));
            panel.AddComponent<LoginPanel>();

            // Baslik
            CreateTextElement(panel.transform, "Title", "CONNECT FOUR PRO",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -50), new Vector2(400, 50), 36);

            // Alt baslik
            CreateTextElement(panel.transform, "Subtitle", "Hosgeldiniz!",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -100), new Vector2(300, 35), 24);

            // Username input
            var usernameInput = CreateInputField(panel.transform, "UsernameInput", "Kullanici Adi",
                new Vector2(0.5f, 0.5f), new Vector2(0, 40), new Vector2(280, 45));
            panel.GetComponent<LoginPanel>().UsernameInput = usernameInput.GetComponent<TMP_InputField>();

            // Password input
            var passwordInput = CreateInputField(panel.transform, "PasswordInput", "Sifre",
                new Vector2(0.5f, 0.5f), new Vector2(0, -20), new Vector2(280, 45));
            var passField = passwordInput.GetComponent<TMP_InputField>();
            if (passField != null) passField.contentType = TMP_InputField.ContentType.Password;
            panel.GetComponent<LoginPanel>().PasswordInput = passField;

            // Buttons
            var loginBtn = CreateButton(panel.transform, "LoginButton", "Giris Yap",
                new Vector2(0.5f, 0.5f), new Vector2(-75, -80), new Vector2(130, 45),
                new Color(233f / 255f, 69f / 255f, 96f / 255f));
            panel.GetComponent<LoginPanel>().LoginButton = loginBtn.GetComponent<Button>();

            var regBtn = CreateButton(panel.transform, "RegisterButton", "Kayit Ol",
                new Vector2(0.5f, 0.5f), new Vector2(75, -80), new Vector2(130, 45),
                new Color(46f / 255f, 204f / 255f, 113f / 255f));
            panel.GetComponent<LoginPanel>().RegisterButton = regBtn.GetComponent<Button>();

            var guestBtn = CreateButton(panel.transform, "GuestButton", "Misafir Olarak Devam",
                new Vector2(0.5f, 0.5f), new Vector2(0, -150), new Vector2(240, 45),
                new Color(22f / 255f, 33f / 255f, 62f / 255f));
            panel.GetComponent<LoginPanel>().GuestButton = guestBtn.GetComponent<Button>();

            // Feedback text
            var feedbackObj = CreateTextElement(panel.transform, "FeedbackText", "",
                new Vector2(0.5f, 0), new Vector2(0.5f, 0),
                new Vector2(0, 30), new Vector2(400, 30), 16);
            panel.GetComponent<LoginPanel>().FeedbackText = feedbackObj.GetComponent<TMP_Text>();

            return panel;
        }

        private GameObject CreateMenuPanel(Transform parent)
        {
            var panel = CreatePanel(parent, "MenuPanel", new Color(26f / 255f, 26f / 255f, 46f / 255f, 0.95f));
            var menu = panel.AddComponent<MainMenuPanel>();

            CreateTextElement(panel.transform, "Title", "CONNECT FOUR PRO",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -40), new Vector2(400, 50), 36);

            var nameText = CreateTextElement(panel.transform, "PlayerName", "",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -90), new Vector2(300, 30), 22);
            menu.PlayerNameText = nameText.GetComponent<TMP_Text>();

            var eloText = CreateTextElement(panel.transform, "PlayerElo", "",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -115), new Vector2(200, 25), 18);
            menu.PlayerEloText = eloText.GetComponent<TMP_Text>();
            eloText.GetComponent<TMP_Text>().color = new Color(46f / 255f, 204f / 255f, 113f / 255f);

            float btnY = -160;
            float btnSpacing = 65;
            Color btnColor = new Color(233f / 255f, 69f / 255f, 96f / 255f);

            var aiBtn = CreateButton(panel.transform, "PlayAIButton", "Yapay Zekaya Karsi",
                new Vector2(0.5f, 1), new Vector2(0, btnY), new Vector2(250, 50), btnColor);
            menu.PlayAIButton = aiBtn.GetComponent<Button>();

            var lobbyBtn = CreateButton(panel.transform, "LobbyButton", "Online Lobi",
                new Vector2(0.5f, 1), new Vector2(0, btnY - btnSpacing), new Vector2(250, 50), btnColor);
            menu.OnlineLobbyButton = lobbyBtn.GetComponent<Button>();

            var lbBtn = CreateButton(panel.transform, "LeaderboardButton", "Liderlik Tablosu",
                new Vector2(0.5f, 1), new Vector2(0, btnY - btnSpacing * 2), new Vector2(250, 50), btnColor);
            menu.LeaderboardButton = lbBtn.GetComponent<Button>();

            var logoutBtn = CreateButton(panel.transform, "LogoutButton", "Cikis Yap",
                new Vector2(0.5f, 1), new Vector2(0, btnY - btnSpacing * 3), new Vector2(250, 50),
                new Color(22f / 255f, 33f / 255f, 62f / 255f));
            menu.LogoutButton = logoutBtn.GetComponent<Button>();

            var quitBtn = CreateButton(panel.transform, "QuitButton", "Oyunu Kapat",
                new Vector2(0.5f, 1), new Vector2(0, btnY - btnSpacing * 4), new Vector2(250, 50),
                new Color(127f / 255f, 140f / 255f, 141f / 255f));
            menu.QuitButton = quitBtn.GetComponent<Button>();

            return panel;
        }

        private GameObject CreateAISelectPanel(Transform parent)
        {
            var panel = CreatePanel(parent, "AISelectPanel", new Color(26f / 255f, 26f / 255f, 46f / 255f, 0.95f));
            var aiSelect = panel.AddComponent<AISelectPanel>();

            CreateTextElement(panel.transform, "Title", "ZORLUK SEVIYESI SEC",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -60), new Vector2(400, 50), 32);

            var easyBtn = CreateButton(panel.transform, "EasyButton", "Kolay (D2)",
                new Vector2(0.5f, 0.5f), new Vector2(0, 60), new Vector2(200, 50),
                new Color(46f / 255f, 204f / 255f, 113f / 255f));
            aiSelect.EasyButton = easyBtn.GetComponent<Button>();

            var medBtn = CreateButton(panel.transform, "MediumButton", "Orta (D4)",
                new Vector2(0.5f, 0.5f), new Vector2(0, 0), new Vector2(200, 50),
                new Color(241f / 255f, 196f / 255f, 15f / 255f));
            aiSelect.MediumButton = medBtn.GetComponent<Button>();

            var hardBtn = CreateButton(panel.transform, "HardButton", "Zor (D6)",
                new Vector2(0.5f, 0.5f), new Vector2(0, -60), new Vector2(200, 50),
                new Color(233f / 255f, 69f / 255f, 96f / 255f));
            aiSelect.HardButton = hardBtn.GetComponent<Button>();

            var backBtn = CreateButton(panel.transform, "BackButton", "Geri",
                new Vector2(0.5f, 0.5f), new Vector2(0, -140), new Vector2(200, 50),
                new Color(127f / 255f, 140f / 255f, 141f / 255f));
            aiSelect.BackButton = backBtn.GetComponent<Button>();

            return panel;
        }

        private GameObject CreateLobbyPanel(Transform parent)
        {
            var panel = CreatePanel(parent, "LobbyPanel", new Color(26f / 255f, 26f / 255f, 46f / 255f, 0.95f));
            var lobby = panel.AddComponent<LobbyPanel>();

            CreateTextElement(panel.transform, "Title", "ONLINE LOBI",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -30), new Vector2(300, 40), 32);

            var createBtn = CreateButton(panel.transform, "CreateButton", "+ Yeni Oyun",
                new Vector2(0, 1), new Vector2(50, -80), new Vector2(160, 45),
                new Color(233f / 255f, 69f / 255f, 96f / 255f));
            lobby.CreateGameButton = createBtn.GetComponent<Button>();

            var refreshBtn = CreateButton(panel.transform, "RefreshButton", "Yenile",
                new Vector2(0, 1), new Vector2(230, -80), new Vector2(100, 45),
                new Color(52f / 255f, 152f / 255f, 219f / 255f));
            lobby.RefreshButton = refreshBtn.GetComponent<Button>();

            var backBtn = CreateButton(panel.transform, "BackButton", "Geri",
                new Vector2(1, 1), new Vector2(-100, -80), new Vector2(100, 45),
                new Color(127f / 255f, 140f / 255f, 141f / 255f));
            lobby.BackButton = backBtn.GetComponent<Button>();

            // Info text
            var infoText = CreateTextElement(panel.transform, "InfoText", "Yukleniyor...",
                new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                new Vector2(0, 0), new Vector2(500, 40), 20);
            lobby.InfoText = infoText.GetComponent<TMP_Text>();

            return panel;
        }

        private GameObject CreateWaitingPanel(Transform parent)
        {
            var panel = CreatePanel(parent, "WaitingPanel", new Color(26f / 255f, 26f / 255f, 46f / 255f, 0.95f));
            var waiting = panel.AddComponent<WaitingPanel>();

            CreateTextElement(panel.transform, "Title", "RAKIP BEKLENIYOR",
                new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                new Vector2(0, 80), new Vector2(400, 50), 32);

            var roomText = CreateTextElement(panel.transform, "RoomCode", "Oda Kodu: ...",
                new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                new Vector2(0, 20), new Vector2(300, 40), 28);
            roomText.GetComponent<TMP_Text>().color = new Color(46f / 255f, 204f / 255f, 113f / 255f);
            waiting.RoomCodeText = roomText.GetComponent<TMP_Text>();

            var dotsText = CreateTextElement(panel.transform, "WaitingDots", "Bekleniyor...",
                new Vector2(0.5f, 0.5f), new Vector2(0.5f, 0.5f),
                new Vector2(0, -30), new Vector2(300, 30), 20);
            waiting.WaitingDotsText = dotsText.GetComponent<TMP_Text>();

            var cancelBtn = CreateButton(panel.transform, "CancelButton", "Iptal",
                new Vector2(0.5f, 0.5f), new Vector2(0, -100), new Vector2(150, 45),
                new Color(233f / 255f, 69f / 255f, 96f / 255f));
            waiting.CancelButton = cancelBtn.GetComponent<Button>();

            return panel;
        }

        private GameObject CreateLeaderboardPanel(Transform parent)
        {
            var panel = CreatePanel(parent, "LeaderboardPanel", new Color(26f / 255f, 26f / 255f, 46f / 255f, 0.95f));
            panel.AddComponent<LeaderboardPanel>();

            CreateTextElement(panel.transform, "Title", "LIDERLIK TABLOSU",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -40), new Vector2(400, 50), 32);

            var backBtn = CreateButton(panel.transform, "BackButton", "Geri",
                new Vector2(0.5f, 0), new Vector2(0, 40), new Vector2(150, 45),
                new Color(127f / 255f, 140f / 255f, 141f / 255f));
            panel.GetComponent<LeaderboardPanel>().BackButton = backBtn.GetComponent<Button>();

            return panel;
        }

        private GameObject CreateGameHUDPanel(Transform parent)
        {
            var panel = CreatePanel(parent, "GameHUDPanel", Color.clear);
            var hud = panel.AddComponent<GameHUDPanel>();

            // Sag bilgi paneli
            var infoPanel = new GameObject("InfoPanel");
            infoPanel.transform.SetParent(panel.transform, false);
            var infoPanelRect = infoPanel.AddComponent<RectTransform>();
            infoPanelRect.anchorMin = new Vector2(1, 0.5f);
            infoPanelRect.anchorMax = new Vector2(1, 0.5f);
            infoPanelRect.anchoredPosition = new Vector2(-140, 0);
            infoPanelRect.sizeDelta = new Vector2(250, 350);

            var bgImage = infoPanel.AddComponent<Image>();
            bgImage.color = new Color(22f / 255f, 33f / 255f, 62f / 255f, 0.9f);

            // Oyun modu basligi
            var modeText = CreateTextElement(infoPanel.transform, "GameModeText", "AI'ya Karsi",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -20), new Vector2(220, 30), 20);
            hud.GameModeText = modeText.GetComponent<TMP_Text>();

            // P1 bilgisi
            var p1Name = CreateTextElement(infoPanel.transform, "P1Name", "Player1",
                new Vector2(0, 1), new Vector2(0, 1),
                new Vector2(50, -60), new Vector2(180, 25), 16);
            hud.Player1NameText = p1Name.GetComponent<TMP_Text>();

            var p1Elo = CreateTextElement(infoPanel.transform, "P1Elo", "ELO: 1200",
                new Vector2(0, 1), new Vector2(0, 1),
                new Vector2(50, -80), new Vector2(150, 20), 12);
            hud.Player1EloText = p1Elo.GetComponent<TMP_Text>();
            p1Elo.GetComponent<TMP_Text>().color = new Color(127f / 255f, 140f / 255f, 141f / 255f);

            // P2 bilgisi
            var p2Name = CreateTextElement(infoPanel.transform, "P2Name", "Player2",
                new Vector2(0, 1), new Vector2(0, 1),
                new Vector2(50, -120), new Vector2(180, 25), 16);
            hud.Player2NameText = p2Name.GetComponent<TMP_Text>();

            var p2Elo = CreateTextElement(infoPanel.transform, "P2Elo", "ELO: 1200",
                new Vector2(0, 1), new Vector2(0, 1),
                new Vector2(50, -140), new Vector2(150, 20), 12);
            hud.Player2EloText = p2Elo.GetComponent<TMP_Text>();
            p2Elo.GetComponent<TMP_Text>().color = new Color(127f / 255f, 140f / 255f, 141f / 255f);

            // Oda ve hamle bilgisi
            var roomText = CreateTextElement(infoPanel.transform, "RoomIdText", "",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -190), new Vector2(200, 30), 18);
            hud.RoomIdText = roomText.GetComponent<TMP_Text>();
            roomText.GetComponent<TMP_Text>().color = new Color(52f / 255f, 152f / 255f, 219f / 255f);

            var moveText = CreateTextElement(infoPanel.transform, "MoveCountText", "Hamle: 0",
                new Vector2(0.5f, 1), new Vector2(0.5f, 1),
                new Vector2(0, -220), new Vector2(200, 25), 16);
            hud.MoveCountText = moveText.GetComponent<TMP_Text>();
            moveText.GetComponent<TMP_Text>().color = new Color(127f / 255f, 140f / 255f, 141f / 255f);

            // Menu butonu
            var menuBtn = CreateButton(infoPanel.transform, "MenuButton", "Menu",
                new Vector2(0.5f, 0), new Vector2(0, 30), new Vector2(150, 40),
                new Color(233f / 255f, 69f / 255f, 96f / 255f));
            hud.MenuButton = menuBtn.GetComponent<Button>();

            // Status text (alt kisim)
            var statusText = CreateTextElement(panel.transform, "StatusText", "",
                new Vector2(0.5f, 0), new Vector2(0.5f, 0),
                new Vector2(0, 25), new Vector2(600, 40), 18);
            hud.StatusText = statusText.GetComponent<TMP_Text>();

            return panel;
        }

        // =========================================================================
        // UI YARDIMCI FONKSIYONLARI
        // =========================================================================

        private GameObject CreatePanel(Transform parent, string name, Color bgColor)
        {
            var panelObj = new GameObject(name);
            panelObj.transform.SetParent(parent, false);

            var rect = panelObj.AddComponent<RectTransform>();
            rect.anchorMin = Vector2.zero;
            rect.anchorMax = Vector2.one;
            rect.sizeDelta = Vector2.zero;

            if (bgColor.a > 0)
            {
                var img = panelObj.AddComponent<Image>();
                img.color = bgColor;
            }

            return panelObj;
        }

        private GameObject CreateTextElement(Transform parent, string name, string text,
            Vector2 anchor, Vector2 pivot, Vector2 anchoredPos, Vector2 sizeDelta, float fontSize = 18)
        {
            var obj = new GameObject(name);
            obj.transform.SetParent(parent, false);

            var rect = obj.AddComponent<RectTransform>();
            rect.anchorMin = anchor;
            rect.anchorMax = anchor;
            rect.pivot = pivot;
            rect.anchoredPosition = anchoredPos;
            rect.sizeDelta = sizeDelta;

            var tmp = obj.AddComponent<TextMeshProUGUI>();
            tmp.text = text;
            tmp.fontSize = fontSize;
            tmp.alignment = TextAlignmentOptions.Center;
            tmp.color = Color.white;

            return obj;
        }

        private GameObject CreateButton(Transform parent, string name, string text,
            Vector2 anchor, Vector2 anchoredPos, Vector2 sizeDelta, Color bgColor)
        {
            var btnObj = new GameObject(name);
            btnObj.transform.SetParent(parent, false);

            var rect = btnObj.AddComponent<RectTransform>();
            rect.anchorMin = anchor;
            rect.anchorMax = anchor;
            rect.anchoredPosition = anchoredPos;
            rect.sizeDelta = sizeDelta;

            var img = btnObj.AddComponent<Image>();
            img.color = bgColor;

            var btn = btnObj.AddComponent<Button>();
            btn.targetGraphic = img;

            // Button text
            var textObj = new GameObject("Text");
            textObj.transform.SetParent(btnObj.transform, false);

            var textRect = textObj.AddComponent<RectTransform>();
            textRect.anchorMin = Vector2.zero;
            textRect.anchorMax = Vector2.one;
            textRect.sizeDelta = Vector2.zero;

            var tmp = textObj.AddComponent<TextMeshProUGUI>();
            tmp.text = text;
            tmp.fontSize = 16;
            tmp.alignment = TextAlignmentOptions.Center;
            tmp.color = Color.white;

            return btnObj;
        }

        private GameObject CreateInputField(Transform parent, string name, string placeholder,
            Vector2 anchor, Vector2 anchoredPos, Vector2 sizeDelta)
        {
            var inputObj = new GameObject(name);
            inputObj.transform.SetParent(parent, false);

            var rect = inputObj.AddComponent<RectTransform>();
            rect.anchorMin = anchor;
            rect.anchorMax = anchor;
            rect.anchoredPosition = anchoredPos;
            rect.sizeDelta = sizeDelta;

            var img = inputObj.AddComponent<Image>();
            img.color = new Color(44f / 255f, 62f / 255f, 80f / 255f);

            // Text area
            var textArea = new GameObject("Text Area");
            textArea.transform.SetParent(inputObj.transform, false);
            var taRect = textArea.AddComponent<RectTransform>();
            taRect.anchorMin = Vector2.zero;
            taRect.anchorMax = Vector2.one;
            taRect.offsetMin = new Vector2(10, 5);
            taRect.offsetMax = new Vector2(-10, -5);

            // Input text
            var textObj = new GameObject("Text");
            textObj.transform.SetParent(textArea.transform, false);
            var tRect = textObj.AddComponent<RectTransform>();
            tRect.anchorMin = Vector2.zero;
            tRect.anchorMax = Vector2.one;
            tRect.sizeDelta = Vector2.zero;

            var inputText = textObj.AddComponent<TextMeshProUGUI>();
            inputText.fontSize = 18;
            inputText.color = Color.white;

            // Placeholder
            var phObj = new GameObject("Placeholder");
            phObj.transform.SetParent(textArea.transform, false);
            var phRect = phObj.AddComponent<RectTransform>();
            phRect.anchorMin = Vector2.zero;
            phRect.anchorMax = Vector2.one;
            phRect.sizeDelta = Vector2.zero;

            var phText = phObj.AddComponent<TextMeshProUGUI>();
            phText.text = placeholder;
            phText.fontSize = 18;
            phText.fontStyle = FontStyles.Italic;
            phText.color = new Color(127f / 255f, 140f / 255f, 141f / 255f);

            // TMP_InputField
            var inputField = inputObj.AddComponent<TMP_InputField>();
            inputField.textViewport = taRect;
            inputField.textComponent = inputText;
            inputField.placeholder = phText;

            return inputObj;
        }
    }
}
