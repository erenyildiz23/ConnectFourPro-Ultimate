// =============================================================================
// GameBootstrap.cs - Connect Four Pro Ultimate
// Sahnedeki tek bilesen: kamera, arayuz, ag ve uygulama durumunu kurar
// =============================================================================
//
// Sahne (Assets/Scenes/Main.unity) yalnizca bu bilesene sahip bir nesne icerir;
// "Tools > Connect Four > Build Scenes" menusu sahneyi olusturur. Sahneye
// eklenmemisse bile oyun baslarken otomatik olusturulur (bkz. AutoCreate).

using System.Collections.Generic;
using System.Linq;
using ConnectFourPro.Net;
using ConnectFourPro.UI;
using UnityEngine;
using UnityEngine.UI;

namespace ConnectFourPro.Game
{
    [DisallowMultipleComponent]
    public sealed class GameBootstrap : MonoBehaviour
    {
        [Tooltip("Bos birakilirsa: WebGL'de sayfanin adresi, Editor'de CONNECT4_SERVER veya http://localhost:5000")]
        [SerializeField] private string serverUrlOverride = "";

        private AppController _app;
        private readonly Dictionary<AppScreen, View> _views = new Dictionary<AppScreen, View>();
        private View _active;
        private Text _status;
        private Image _statusBar;
        private CanvasScaler _scaler;
        private Button _langButton;
        private const string LangPrefKey = "lang";
        private LayoutOrientation _orientation = LayoutOrientation.Landscape;

        public AppController App => _app;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void AutoCreate()
        {
            if (FindAnyObjectByType<GameBootstrap>() == null)
                new GameObject("ConnectFourPro").AddComponent<GameBootstrap>();
        }

        private void Awake()
        {
#if UNITY_WEBGL && !UNITY_EDITOR
            // Tarayicida kare hizini tarayici belirler (requestAnimationFrame)
            Application.targetFrameRate = -1;
            QualitySettings.vSyncCount = 0;
#else
            // Editor / masaustu: ekran yenilemesine kilitle (sinirsiz kare cizme)
            QualitySettings.vSyncCount = 1;
#endif
            Application.runInBackground = true;   // sekme arka plandayken de sunucu olaylari islensin

            if (!string.IsNullOrWhiteSpace(serverUrlOverride))
                ServerConfig.Url = serverUrlOverride;

            // Dil: kayitli tercih, yoksa sistem/tarayici dili (Turkce degilse Ingilizce)
            Loc.Current = Loc.Initial(PlayerPrefs.GetString(LangPrefKey, ""),
                                      Application.systemLanguage == SystemLanguage.Turkish);
            Debug.Log("[App] Dil: " + Loc.Code(Loc.Current));

            EnsureCamera();
            var transport = SocketTransports.Create(gameObject);
            _app = new AppController(this, ServerConfig.Url, transport);
            BuildUI();
            _app.ScreenChanged += ShowScreen;
            ShowScreen(_app.Screen);
        }

        private static void EnsureCamera()
        {
            var cam = Camera.main;
            if (cam == null)
            {
                cam = new GameObject("Main Camera").AddComponent<Camera>();
                cam.tag = "MainCamera";
            }
            cam.clearFlags = CameraClearFlags.SolidColor;
            cam.backgroundColor = Theme.Background;
            cam.orthographic = true;
            cam.cullingMask = 0;    // her sey UI'da; sahne cizilmez
        }

        private void BuildUI()
        {
            UIKit.EnsureEventSystem(transform);
            var canvas = UIKit.CreateCanvas(transform);
            var root = canvas.transform;

            var bg = UIKit.Image(root, "Background", Theme.Background);
            bg.rectTransform.anchorMin = Vector2.zero;
            bg.rectTransform.anchorMax = Vector2.one;
            bg.rectTransform.offsetMin = bg.rectTransform.offsetMax = Vector2.zero;

            var game = new GameView(_app, root);
            _views[AppScreen.Login] = new LoginView(_app, root);
            _views[AppScreen.Menu] = new MenuView(_app, root);
            _views[AppScreen.AISelect] = new AISelectView(_app, root);
            _views[AppScreen.Lobby] = new LobbyView(_app, root);
            _views[AppScreen.Waiting] = new WaitingView(_app, root);
            _views[AppScreen.Leaderboard] = new LeaderboardView(_app, root);
            _views[AppScreen.History] = new HistoryView(_app, root);
            _views[AppScreen.Replay] = new ReplayView(_app, root);
            _views[AppScreen.PlayingAI] = game;
            _views[AppScreen.PlayingOnline] = game;
            _views[AppScreen.Spectating] = game;
            foreach (var v in _views.Values)
                v.Visible = false;

            var board = game.Board;
            _app.IsAnimating = () => board.IsAnimating;
            _app.AnimateDrop = board.AnimateDrop;
            _app.FinishAnimation = board.FinishAnimation;
            _app.CancelAnimation = board.CancelAnimation;

            // Durum satiri (tum ekranlarda en altta)
            _statusBar = UIKit.Image(root, "StatusBar", Theme.Panel);
            var sb = _statusBar.rectTransform;
            sb.anchorMin = new Vector2(0, 0);
            sb.anchorMax = new Vector2(1, 0);
            sb.pivot = new Vector2(0.5f, 0);
            sb.sizeDelta = new Vector2(0, 52);
            sb.anchoredPosition = Vector2.zero;
            _status = UIKit.Text(_statusBar.transform, "", 20, Theme.White);
            var st = _status.rectTransform;
            st.anchorMin = Vector2.zero;
            st.anchorMax = Vector2.one;
            st.offsetMin = new Vector2(20, 0);
            st.offsetMax = new Vector2(-20, 0);

            var server = UIKit.Label(root, "Sunucu: " + _app.ServerUrl, 13, new Color(1, 1, 1, 0.25f), 0, 12, 1200, 20,
                                     TextAnchor.MiddleRight);
            // Dikey: durum cubugu biraz yuksek (uzun metin sarar), sunucu etiketi 540 genislige sigar
            // Genislik 0 dogru: cubuk yatayda anchor ile gerilir (sizeDelta.x = kenar payi)
            Responsive.Portrait(sb, 0, 0, 0, 72);
            Responsive.Portrait(server.rectTransform, 0, 12, 520, 24);

            // Dil dugmesi (yalnizca giris ve menu ekraninda): yatayda sag ust, dikeyde sol ust.
            // e2e testinin tikladigi noktalardan uzak.
            _langButton = UIKit.Button(root, Loc.ToggleLabel, Theme.Panel, ToggleLanguage, 560, 50, 130, 40, 18);
            Responsive.Portrait(_langButton.GetComponent<RectTransform>(), -195, 50, 130, 44);

            _scaler = canvas.GetComponent<CanvasScaler>();
            ApplyOrientation(ScreenLayout.For(Screen.width, Screen.height));
        }

        private void ToggleLanguage()
        {
            Loc.Toggle();
            PlayerPrefs.SetString(LangPrefKey, Loc.Code(Loc.Current));
            PlayerPrefs.Save();
            Debug.Log("[App] Dil: " + Loc.Code(Loc.Current));
        }

        private void ApplyOrientation(LayoutOrientation o)
        {
            _orientation = o;
            Responsive.Apply(o, _scaler);
            // GameView 3 durumda kayitli; her gorunum yalnizca bir kez
            foreach (var v in _views.Values.Distinct())
                v.OnLayoutChanged(o);
        }

        private void ShowScreen(AppScreen screen)
        {
            var next = _views[screen];
            if (_active == next)
                return;
            if (_active != null)
                _active.Visible = false;
            _active = next;
            _active.Visible = true;
            _active.OnShow();
        }

        private void Update()
        {
            var orientation = ScreenLayout.For(Screen.width, Screen.height);
            if (orientation != _orientation)
                ApplyOrientation(orientation);

            _app.Tick();
            // Tekrar: sol / sag ok bir hamle geri / ileri, Bosluk oynat / durdur
            var replay = _app.Screen == AppScreen.Replay ? _app.Replay : null;
            if (replay != null)
            {
                if (Keys.LeftPressed())
                    replay.Prev();
                if (Keys.RightPressed())
                    replay.Next();
                if (Keys.SpacePressed())
                    replay.TogglePlay();
            }
            _active?.Refresh();

            // Esc: ekrandaki Geri/Iptal/Menu butonu gibi (canli online oyunda ilk basis onay ister)
            if (Keys.BackPressed() && _app.Screen != AppScreen.Login && _app.Screen != AppScreen.Menu)
                _app.RequestBack();

            // Biten online oyunun tekrarinda rovans mesajlari durum cubugunda gorunur
            bool inGame = _app.Screen == AppScreen.PlayingAI || _app.Screen == AppScreen.PlayingOnline
                          || _app.Screen == AppScreen.Spectating
                          || (_app.Screen == AppScreen.Replay && _app.ReplayReturnScreen == AppScreen.PlayingOnline);
            _status.text = Loc.T(_app.Status);
            bool showLang = _app.Screen == AppScreen.Login || _app.Screen == AppScreen.Menu;
            if (_langButton.gameObject.activeSelf != showLang)
                _langButton.gameObject.SetActive(showLang);
            if (showLang)
                UIKit.SetLabel(_langButton, Loc.ToggleLabel);
            _status.color = _app.Tone == StatusTone.Good ? Theme.Green
                          : _app.Tone == StatusTone.Bad ? Theme.Error
                          : inGame ? Theme.White : Theme.Gray;
            _statusBar.enabled = inGame;
        }

        private void OnApplicationQuit() => _app?.Shutdown();
    }
}
