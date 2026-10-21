// =============================================================================
// GameBootstrap.cs - Connect Four Pro Ultimate
// Sahnedeki tek bilesen: kamera, arayuz, ag ve uygulama durumunu kurar
// =============================================================================
//
// Sahne (Assets/Scenes/Main.unity) yalnizca bu bilesene sahip bir nesne icerir;
// "Tools > Connect Four > Build Scenes" menusu sahneyi olusturur. Sahneye
// eklenmemisse bile oyun baslarken otomatik olusturulur (bkz. AutoCreate).

using System.Collections.Generic;
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

        public AppController App => _app;

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void AutoCreate()
        {
            if (FindAnyObjectByType<GameBootstrap>() == null)
                new GameObject("ConnectFourPro").AddComponent<GameBootstrap>();
        }

        private void Awake()
        {
            // Tarayicida kare hizini tarayici belirler (requestAnimationFrame)
            Application.targetFrameRate = -1;
            QualitySettings.vSyncCount = 0;
            Application.runInBackground = true;   // sekme arka plandayken de sunucu olaylari islensin

            if (!string.IsNullOrWhiteSpace(serverUrlOverride))
                ServerConfig.Url = serverUrlOverride;

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

            UIKit.Label(root, "Sunucu: " + _app.ServerUrl, 13, new Color(1, 1, 1, 0.25f), 0, 12, 1200, 20,
                        TextAnchor.MiddleRight);
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
            _app.Tick();
            _active?.Refresh();

            bool inGame = _app.Screen == AppScreen.PlayingAI || _app.Screen == AppScreen.PlayingOnline
                          || _app.Screen == AppScreen.Spectating;
            _status.text = _app.Status;
            _status.color = _app.Tone == StatusTone.Good ? Theme.Green
                          : _app.Tone == StatusTone.Bad ? Theme.Red
                          : inGame ? Theme.White : Theme.Gray;
            _statusBar.enabled = inGame;
        }

        private void OnApplicationQuit() => _app?.Shutdown();
    }
}
