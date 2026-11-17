// =============================================================================
// Views.cs - Connect Four Pro Ultimate
// Ekranlar (src/gui_app.py draw_* fonksiyonlarinin karsiliklari)
// =============================================================================
//
// Her ekran bir kok nesne altinda bir kez kurulur; gorunurken her karede
// Refresh() ile AppController'daki durumu yansitir.

using System.Collections.Generic;
using ConnectFourPro.AI;
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using ConnectFourPro.Net;
using UnityEngine;
using UnityEngine.UI;

namespace ConnectFourPro.UI
{
    public abstract class View
    {
        protected readonly AppController App;
        public readonly RectTransform Root;

        protected View(AppController app, Transform parent, string name)
        {
            App = app;
            Root = UIKit.Stretch(parent, name);
        }

        public bool Visible
        {
            get => Root.gameObject.activeSelf;
            set => Root.gameObject.SetActive(value);
        }

        public virtual void OnShow()
        {
        }

        public virtual void Refresh()
        {
        }

        /// <summary>Ekran yonu degisince cagrilir (Responsive.Apply'dan sonra).</summary>
        public virtual void OnLayoutChanged(LayoutOrientation o)
        {
            // Sigdirma yalnizca dikeyde acilir; yatay gorunum degismez
            foreach (var t in _fit)
                t.resizeTextForBestFit = o == LayoutOrientation.Portrait;
        }

        private readonly List<Text> _fit = new List<Text>();

        /// <summary>Dikeyde yazi kutuya sigmazsa min ile max arasinda kuculur.</summary>
        protected void FitInPortrait(Text t, int min, int max)
        {
            t.resizeTextMinSize = min;
            t.resizeTextMaxSize = max;
            _fit.Add(t);
        }

        protected Text Title(string text, float y = 50)
        {
            var t = UIKit.Label(Root, text, 44, Theme.Red, 0, y, 1000, 60, TextAnchor.MiddleCenter, FontStyle.Bold);
            FitInPortrait(t, 30, 44);
            return t;
        }

        // Dik konum kisayolu: Portrait kaydi, ogenin son Place'inden sonra yapilir
        protected static void P(Component c, float x, float y, float w, float h) =>
            Responsive.Portrait((RectTransform)c.transform, x, y, w, h);
    }

    // -------------------------------------------------------------------------
    public sealed class LoginView : View
    {
        private readonly InputField _username;
        private readonly InputField _password;

        public LoginView(AppController app, Transform parent) : base(app, parent, "Login")
        {
            P(Title("CONNECT FOUR PRO", 80), 0, 150, 510, 60);
            P(UIKit.Label(Root, "ULTIMATE", 22, Theme.Yellow, 0, 122, 400, 30, TextAnchor.MiddleCenter, FontStyle.Bold),
              0, 200, 400, 30);
            P(UIKit.Label(Root, "Hoş geldiniz!", 26, Theme.White, 0, 170), 0, 250, 480, 40);

            P(UIKit.Label(Root, "Kullanıcı Adı", 18, Theme.Gray, 0, 220, 320, 26), 0, 310, 440, 26);
            _username = UIKit.Input(Root, "kullanıcı adı", false, 0, 255, 320, 50, AppController.UsernameMaxLength);
            P(_username, 0, 350, 440, 56);
            P(UIKit.Label(Root, "Şifre", 18, Theme.Gray, 0, 305, 320, 26), 0, 410, 440, 26);
            _password = UIKit.Input(Root, "şifre", true, 0, 340, 320, 50, 128);
            P(_password, 0, 450, 440, 56);

            P(UIKit.Button(Root, "Giriş Yap", Theme.Button, Login, -82, 420, 150, 50), -112, 530, 216, 56);
            P(UIKit.Button(Root, "Kayıt Ol", Theme.Green, () => App.Register(_username.text, _password.text), 82, 420, 150, 50),
              112, 530, 216, 56);

            var line = UIKit.Image(Root, "Divider", Theme.Gray);
            UIKit.Place(line.rectTransform, 0, 488, 240, 1);
            P(line, 0, 600, 300, 1);
            var orBg = UIKit.Image(Root, "OrBg", Theme.Background);
            UIKit.Place(orBg.rectTransform, 0, 488, 60, 22);
            P(orBg, 0, 600, 60, 24);
            P(UIKit.Label(Root, "veya", 16, Theme.Gray, 0, 488, 60, 22), 0, 600, 60, 24);
            P(UIKit.Button(Root, "Misafir Olarak Devam", Theme.Panel, App.GuestLogin, 0, 540, 280, 50), 0, 660, 440, 56);

            app.InputsCleared += () =>
            {
                _username.text = "";
                _password.text = "";
            };
        }

        private void Login() => App.Login(_username.text, _password.text);

        public override void OnShow()
        {
            _lastFocused = _username;
            _username.ActivateInputField();
        }

        // Enter alanin odagini ayni karede kaldirabilir; bu yuzden son odakli alan izlenir
        private InputField _lastFocused;

        public override void Refresh()
        {
            bool enter = Keys.EnterPressed();
            bool tab = Keys.TabPressed();
            if (enter && _lastFocused == _username)
                Focus(_password);
            else if (enter && _lastFocused == _password)
                Login();
            else if (tab)
                Focus(_lastFocused == _username ? _password : _username);

            if (_username.isFocused)
                _lastFocused = _username;
            else if (_password.isFocused)
                _lastFocused = _password;
        }

        private void Focus(InputField field)
        {
            _lastFocused = field;
            field.ActivateInputField();
            field.Select();
        }
    }

    // -------------------------------------------------------------------------
    public sealed class MenuView : View
    {
        private readonly Text _name;
        private readonly Text _elo;

        public MenuView(AppController app, Transform parent) : base(app, parent, "Menu")
        {
            P(Title("CONNECT FOUR PRO", 50), 0, 150, 510, 60);
            _name = UIKit.Label(Root, "", 26, Theme.White, 0, 100);
            P(_name, 0, 215, 480, 40);
            _elo = UIKit.Label(Root, "", 20, Theme.Green, 0, 130);
            P(_elo, 0, 255, 480, 40);

            var items = new List<(string label, Color color, UnityEngine.Events.UnityAction action)>
            {
                ("Yapay Zekâya Karşı", Theme.Button, app.OpenAISelect),
                ("Online Lobi", Theme.Button, app.OpenLobby),
                ("Liderlik Tablosu", Theme.Button, app.OpenLeaderboard),
                ("Maç Geçmişi", Theme.Button, app.OpenHistory),
                ("Çıkış Yap", Theme.Panel, app.Logout),
            };
#if !UNITY_WEBGL || UNITY_EDITOR
            // Tarayicida uygulama kapatilamaz; bu buton yalnizca masaustunde
            items.Add(("Oyunu Kapat", Theme.Gray, Quit));
#endif
            for (int i = 0; i < items.Count; i++)
                P(UIKit.Button(Root, items[i].label, items[i].color, items[i].action, 0, 200 + i * 66, 300, 52, 21),
                  0, 340 + i * 78, 440, 60);
        }

        private static void Quit()
        {
#if UNITY_EDITOR
            UnityEditor.EditorApplication.isPlaying = false;
#else
            Application.Quit();
#endif
        }

        public override void Refresh()
        {
            if (App.IsGuest)
            {
                _name.text = "Misafir: " + App.Username;
                _name.fontSize = 20;
                _name.color = Theme.Gray;
                _elo.text = "";
            }
            else
            {
                _name.text = App.Username;
                _name.fontSize = 26;
                _name.color = Theme.White;
                _elo.text = "ELO: " + App.UserElo;
            }
        }
    }

    // -------------------------------------------------------------------------
    public sealed class AISelectView : View
    {
        private readonly Button _firstMove;

        public AISelectView(AppController app, Transform parent) : base(app, parent, "AISelect")
        {
            P(Title("ZORLUK SEVİYESİ SEÇ", 90), 0, 150, 510, 60);
            // Ilk hamle secimi: baslik (60-120) ile ilk zorluk dugmesi (172-228) arasinda (124-160)
            _firstMove = UIKit.Button(Root, app.AIStartsLabel, Theme.Panel, app.ToggleAIStartsNext, 0, 142, 260, 36, 18);
            P(_firstMove, 0, 230, 440, 48);
            // Zorluk dugmelerinin merkezleri degismez (tests/e2e/webgl.spec.mjs Kolay'a (0, 200)'den tiklar)
            float y = 200;
            float py = 320;
            foreach (var (name, depth) in AIEngine.Difficulties)
            {
                int d = depth;
                P(UIKit.Button(Root, AppController.DifficultyLabel(name), Theme.Button, () => app.StartAIGame(d), 0, y, 420, 56, 22),
                  0, py, 440, 64);
                y += 76;
                py += 90;
            }
            P(UIKit.Button(Root, "Geri", Theme.Panel, app.RequestBack, 0, y + 30, 260, 50), 0, py + 20, 300, 56);
        }

        public override void Refresh() => UIKit.SetLabel(_firstMove, App.AIStartsLabel);
    }

    // -------------------------------------------------------------------------
    public sealed class LobbyView : View
    {
        private const int MaxRows = 8;
        // Dikeyde sigan satir sayisi (satir yuksekligi 60, adim 64)
        private const int PortraitMaxRows = 8;
        private readonly RectTransform _rows;
        private readonly Text _empty;
        private readonly List<Text> _landscapeHeader = new List<Text>();
        private readonly List<Text> _portraitHeader = new List<Text>();
        private int _shownVersion = -1;

        public LobbyView(AppController app, Transform parent) : base(app, parent, "Lobby")
        {
            P(Title("ONLİNE LOBİ", 45), 0, 150, 510, 60);
            P(UIKit.Button(Root, "+ Yeni Oyun", Theme.Button, app.CreateOnlineGame, -470, 110, 180, 48), -160, 220, 170, 52);
            P(UIKit.Button(Root, "Yenile", Theme.Button, () =>
            {
                app.RefreshActiveGames();
                app.SetStatus("Yenilendi");
            }, -320, 110, 100, 48), 10, 220, 130, 52);
            P(UIKit.Button(Root, "Geri", Theme.Panel, app.RequestBack, 500, 110, 120, 48), 180, 220, 120, 52);

            var header = UIKit.Panel(Root, "Header", Theme.Panel);
            UIKit.Place(header.rectTransform, 0, 170, 1180, 40);
            P(header, 0, 275, 510, 40);
            float[] cols = { -480, -260, -20, 220, 470 };
            string[] titles = { "ODA", "OYUNCU 1", "OYUNCU 2", "DURUM", "İŞLEM" };
            for (int i = 0; i < cols.Length; i++)
                _landscapeHeader.Add(UIKit.Label(Root, titles[i], 18, Theme.White, cols[i], 170, 220, 40, TextAnchor.MiddleCenter, FontStyle.Bold));

            // Dikte 3 sutun: ODA / OYUNCULAR / ISLEM; yatayda gizli
            float[] pcols = { -185, -15, 185 };
            string[] ptitles = { "ODA", "OYUNCULAR", "İŞLEM" };
            for (int i = 0; i < pcols.Length; i++)
            {
                var t = UIKit.Label(Root, ptitles[i], 18, Theme.White, pcols[i], 170, 220, 40, TextAnchor.MiddleCenter, FontStyle.Bold);
                P(t, pcols[i], 275, i == 1 ? 190 : 120, 40);
                _portraitHeader.Add(t);
            }

            _rows = UIKit.Stretch(Root, "Rows");
            _empty = UIKit.Label(Root, "Aktif oyun yok. Yeni bir oyun oluşturun!", 24, Theme.Gray, 0, 320);
            P(_empty, 0, 400, 460, 80);
            SetHeaders(Responsive.Current);
        }

        private void SetHeaders(LayoutOrientation o)
        {
            bool portrait = o == LayoutOrientation.Portrait;
            foreach (var t in _landscapeHeader)
                t.gameObject.SetActive(!portrait);
            foreach (var t in _portraitHeader)
                t.gameObject.SetActive(portrait);
        }

        public override void OnShow() => _shownVersion = -1;

        public override void OnLayoutChanged(LayoutOrientation o)
        {
            base.OnLayoutChanged(o);
            SetHeaders(o);
            // Satirlar yone gore farkli kuruldugu icin yeniden kurulur
            _shownVersion = -1;
            if (Visible)
                Refresh();
        }

        public override void Refresh()
        {
            if (_shownVersion == App.ActiveGamesVersion)
                return;
            _shownVersion = App.ActiveGamesVersion;
            for (int i = _rows.childCount - 1; i >= 0; i--)
                Object.Destroy(_rows.GetChild(i).gameObject);

            bool portrait = Responsive.Current == LayoutOrientation.Portrait;
            var games = App.ActiveGames;
            _empty.enabled = games.Count == 0;
            int max = portrait ? PortraitMaxRows : MaxRows;
            for (int i = 0; i < games.Count && i < max; i++)
            {
                if (portrait)
                    BuildPortraitRow(games[i], i);
                else
                    BuildRow(games[i], i);
            }
        }

        // Dik satir: yukseklik 60; oyuncular iki satir, islem dugmesi >= 48 yuksek
        private void BuildPortraitRow(ActiveGame g, int index)
        {
            float y = 335 + index * 64;
            var bg = UIKit.Image(_rows, "Row " + g.RoomId, index % 2 == 0 ? Theme.Panel : Theme.Background);
            UIKit.Place(bg.rectTransform, 0, y, 510, 60);
            UIKit.Label(_rows, g.RoomId, 20, Theme.Hover, -185, y, 130, 56, TextAnchor.MiddleCenter, FontStyle.Bold);
            UIKit.Label(_rows, $"{Short(g.P1)} ({g.P1Elo})", 18, Theme.Red, -15, y - 15, 190, 28);
            string room = g.RoomId;
            if (g.Waiting)
            {
                UIKit.Label(_rows, "Bekleniyor...", 18, Theme.Waiting, -15, y + 15, 190, 28);
                UIKit.Button(_rows, "Katıl", Theme.Green, () => App.JoinOnlineGame(room), 185, y, 110, 48, 18);
            }
            else
            {
                UIKit.Label(_rows, $"{Short(g.P2)} ({g.P2Elo})", 18, Theme.Yellow, -15, y + 15, 190, 28);
                UIKit.Button(_rows, "İzle", Theme.Hover, () => App.SpectateGame(room), 185, y, 110, 48, 18);
            }
        }

        private void BuildRow(ActiveGame g, int index)
        {
            float y = 225 + index * 54;
            var bg = UIKit.Image(_rows, "Row " + g.RoomId, index % 2 == 0 ? Theme.Panel : Theme.Background);
            UIKit.Place(bg.rectTransform, 0, y, 1180, 50);
            UIKit.Label(_rows, g.RoomId, 20, Theme.Hover, -480, y, 220, 50, TextAnchor.MiddleCenter, FontStyle.Bold);
            UIKit.Label(_rows, $"{Short(g.P1)} ({g.P1Elo})", 19, Theme.Red, -260, y, 230, 50);
            string room = g.RoomId;
            if (g.Waiting)
            {
                UIKit.Label(_rows, "Bekleniyor...", 19, Theme.Waiting, -20, y, 230, 50);
                UIKit.Label(_rows, "Bekliyor", 19, Theme.Waiting, 220, y, 230, 50);
                UIKit.Button(_rows, "Katıl", Theme.Green, () => App.JoinOnlineGame(room), 470, y, 100, 38, 18);
            }
            else
            {
                UIKit.Label(_rows, $"{Short(g.P2)} ({g.P2Elo})", 19, Theme.Yellow, -20, y, 230, 50);
                UIKit.Label(_rows, $"Oyunda ({g.MoveCount} hamle)", 19, Theme.Playing, 220, y, 230, 50);
                UIKit.Button(_rows, "İzle", Theme.Hover, () => App.SpectateGame(room), 470, y, 100, 38, 18);
            }
        }

        private static string Short(string s) => s != null && s.Length > 12 ? s.Substring(0, 12) : s;
    }

    // -------------------------------------------------------------------------
    public sealed class WaitingView : View
    {
        private static readonly string[] Dots = { "Bekleniyor", "Bekleniyor.", "Bekleniyor..", "Bekleniyor..." };
        private readonly Text _room;
        private readonly Text _hint;
        private readonly Text _dots;

        public WaitingView(AppController app, Transform parent) : base(app, parent, "Waiting")
        {
            P(Title("RAKİP BEKLENİYOR", 170), 0, 250, 510, 60);
            _room = UIKit.Label(Root, "", 44, Theme.Green, 0, 270, 900, 60, TextAnchor.MiddleCenter, FontStyle.Bold);
            P(_room, 0, 340, 480, 70);
            FitInPortrait(_room, 28, 44);
            _hint = UIKit.Label(Root, "", 24, Theme.White, 0, 330);
            P(_hint, 0, 420, 480, 40);
            _dots = UIKit.Label(Root, "", 24, Theme.Gray, 0, 400);
            P(_dots, 0, 480, 480, 40);
            P(UIKit.Button(Root, "İptal", Theme.Panel, app.RequestBack, 0, 480, 180, 50), 0, 580, 240, 56);
        }

        public override void Refresh()
        {
            if (App.RoomId != null)
            {
                _room.text = "Oda Kodu: " + App.RoomId;
                _hint.text = "Rakip lobiden katılabilir!";
            }
            else
            {
                _room.text = "";
                _hint.text = "Oda oluşturuluyor...";
            }
            _dots.text = Dots[(int)(Time.unscaledTime * 2) % 4];
        }
    }

    // -------------------------------------------------------------------------
    public sealed class LeaderboardView : View
    {
        // Dikeyde gosterilen satir sayisi (adim 52: 10 satir 230..698 araligina sigar)
        private const int PortraitRows = 10;
        private readonly Text _message;
        private readonly Text[] _lines = new Text[10];

        public LeaderboardView(AppController app, Transform parent) : base(app, parent, "Leaderboard")
        {
            P(Title("LİDERLİK TABLOSU", 55), 0, 150, 510, 60);
            _message = UIKit.Label(Root, "", 24, Theme.Gray, 0, 250);
            P(_message, 0, 400, 480, 80);
            for (int i = 0; i < _lines.Length; i++)
            {
                _lines[i] = UIKit.Label(Root, "", 21, Theme.White, 0, 125 + i * 42, 900, 40);
                P(_lines[i], 0, 230 + i * 52, 510, 48);
                FitInPortrait(_lines[i], 18, 21);
            }
            P(UIKit.Button(Root, "Geri", Theme.Panel, app.RequestBack, 0, 655, 180, 50), 0, 800, 240, 56);
        }

        public override void OnLayoutChanged(LayoutOrientation o)
        {
            base.OnLayoutChanged(o);
            Refresh();
        }

        public override void Refresh()
        {
            var data = App.LeaderboardData;
            _message.text = App.LeaderboardError ? "Sunucuya bağlanılamadı"
                          : data == null ? "Yükleniyor..."
                          : data.Count == 0 ? "Henüz kayıtlı oyuncu yok" : "";
            int limit = Responsive.Current == LayoutOrientation.Portrait ? PortraitRows : _lines.Length;
            for (int i = 0; i < _lines.Length; i++)
            {
                if (data != null && i < data.Count && i < limit)
                {
                    var p = data[i];
                    _lines[i].text = $"{i + 1}. {p.Username}  -  ELO: {p.Rating}  (G:{p.Wins} M:{p.Losses})";
                    _lines[i].color = i < 3 ? Theme.Yellow : Theme.White;
                }
                else
                    _lines[i].text = "";
            }
        }
    }

    // -------------------------------------------------------------------------
    public sealed class HistoryView : View
    {
        // Dikeyde her kayit iki satir (adim 78); sigan kayit sayisi
        private const int PortraitRows = 8;
        private readonly Text _message;
        private readonly Text[,] _cells = new Text[10, 4];

        public HistoryView(AppController app, Transform parent) : base(app, parent, "History")
        {
            P(Title("MAÇ GEÇMİŞİ", 55), 0, 150, 510, 60);
            _message = UIKit.Label(Root, "", 24, Theme.Gray, 0, 250, 1000);
            P(_message, 0, 400, 480, 80);
            float[] xs = { -390, -150, 110, 380 };
            // Dik: ust satir tarih + rakip, alt satir sonuc + hamle sayisi
            float[] pxs = { -130, 135, -130, 135 };
            float[] pdy = { -20, -20, 18, 18 };
            for (int i = 0; i < 10; i++)
                for (int c = 0; c < 4; c++)
                {
                    _cells[i, c] = UIKit.Label(Root, "", 20, Theme.White, xs[c], 120 + i * 48, 250, 40, TextAnchor.MiddleLeft);
                    P(_cells[i, c], pxs[c], 235 + i * 78 + pdy[c], 240, 34);
                    FitInPortrait(_cells[i, c], 18, 20);
                }
            P(UIKit.Button(Root, "Geri", Theme.Panel, app.RequestBack, 0, 655, 180, 50), 0, 850, 240, 56);
        }

        public override void OnLayoutChanged(LayoutOrientation o)
        {
            base.OnLayoutChanged(o);
            Refresh();
        }

        public override void Refresh()
        {
            var data = App.HistoryData;
            _message.text = App.IsGuest ? "Maç geçmişi sadece kayıtlı oyuncular için tutulur."
                          : App.HistoryError ? "Sunucuya bağlanılamadı"
                          : data == null ? "Yükleniyor..."
                          : data.Count == 0 ? "Henüz online maç oynamadınız." : "";
            int limit = Responsive.Current == LayoutOrientation.Portrait ? PortraitRows : 10;
            for (int i = 0; i < 10; i++)
            {
                bool has = !App.IsGuest && data != null && i < data.Count && i < limit;
                if (!has)
                {
                    for (int c = 0; c < 4; c++)
                        _cells[i, c].text = "";
                    continue;
                }
                var g = data[i];
                string text;
                Color color;
                switch (g.Result)
                {
                    case "win": text = "KAZANDIN"; color = Theme.Green; break;
                    case "loss": text = "KAYBETTİN"; color = Theme.Red; break;
                    case "draw": text = "BERABERE"; color = Theme.Yellow; break;
                    default: text = "?"; color = Theme.Gray; break;
                }
                if (g.EndReason == "forfeit")
                    text += " (hükmen)";
                _cells[i, 0].text = g.ShortDate;
                _cells[i, 0].color = Theme.Gray;
                _cells[i, 1].text = "vs " + g.OpponentOf(App.Username);
                _cells[i, 2].text = text;
                _cells[i, 2].color = color;
                _cells[i, 3].text = g.MoveCount + " hamle";
                _cells[i, 3].color = Theme.Gray;
            }
        }
    }

    // -------------------------------------------------------------------------
    public sealed class GameView : View
    {
        private readonly Text _title;
        private readonly Text _panelTitle;
        private readonly Text[] _names = new Text[2];
        private readonly Text[] _elos = new Text[2];
        private readonly Text[] _turns = new Text[2];
        private readonly Text[] _clocks = new Text[2];
        private readonly Text _room;
        private readonly Text _moves;
        private readonly Text _accuracyTitle;
        private readonly Text _accuracy;
        private readonly Button _menu;
        private readonly Text _menuLabel;
        private readonly Button _again;
        private readonly Button _undo;
        private readonly Button _rematch;

        public BoardView Board { get; }

        public GameView(AppController app, Transform parent) : base(app, parent, "Game")
        {
            _title = UIKit.Label(Root, "", 38, Theme.Red, 0, 42, 1000, 56, TextAnchor.MiddleCenter, FontStyle.Bold);
            // Dikey: baslik 510'a sigar (uzun sonuc basliklari kuculur), "Sunucu" etiketinin altinda
            P(_title, 0, 38, 510, 44);
            FitInPortrait(_title, 28, 38);

            Board = BoardView.Create(Root, -250, 375, () => App.Game, app.CanHumanMove, () => App.HumanPiece);
            Board.ColumnClicked += app.HandleColumnClick;
            // Dikey: tahta 0.9 olcekle ortada. Merkez y=345: hover diski (merkez 0.6 hucre ustte) basligin
            // altinda kalir; tahta cercevesi y 573'te biter, bilgi paneli 582'de baslar
            P(Board, 0, 345, 560, 480);
            Responsive.PortraitScale((RectTransform)Board.transform, 0.9f);

            const float px = 400;   // bilgi paneli merkezi
            var panel = UIKit.Panel(Root, "InfoPanel", Theme.Panel);
            UIKit.Place(panel.rectTransform, px, 375, 320, 480);
            // Dikey: panel tahtanin altindan durum cubugunun ustune (y 582..880), 510 genis
            P(panel, 0, 731, 510, 298);
            _panelTitle = UIKit.Label(Root, "", 24, Theme.White, px, 165, 300, 34, TextAnchor.MiddleCenter, FontStyle.Bold);
            P(_panelTitle, 0, 600, 400, 28);

            for (int i = 0; i < 2; i++)
            {
                float y = 225 + i * 70;
                var disc = UIKit.Image(Root, "Disc " + i, Theme.PieceColor(i + 1), UIKit.Circle);
                UIKit.Place(disc.rectTransform, px - 125, y, 34, 34);
                _names[i] = UIKit.Label(Root, "", 21, Theme.White, px - 10, y - 10, 180, 28, TextAnchor.MiddleLeft);
                _elos[i] = UIKit.Label(Root, "", 16, Theme.Gray, px - 10, y + 14, 180, 22, TextAnchor.MiddleLeft);
                _turns[i] = UIKit.Label(Root, "< SIRA", 18, Theme.Green, px + 110, y, 90, 30, TextAnchor.MiddleCenter, FontStyle.Bold);
                // Hamle suresi: "< SIRA"nin hemen altinda (y+13..y+35; sonraki satir y+46'da baslar)
                _clocks[i] = UIKit.Label(Root, "", 16, Theme.Gray, px + 110, y + 24, 80, 22, TextAnchor.MiddleCenter, FontStyle.Bold);

                // Dikey: oyuncu satiri 52 aralikli; SIRA ve sure sagda ust uste
                float ry = 645 + i * 52;
                P(disc, -225, ry, 34, 34);
                P(_names[i], -65, ry - 10, 260, 28);
                P(_elos[i], -65, ry + 14, 260, 24);
                P(_turns[i], 200, ry - 10, 100, 30);
                P(_clocks[i], 200, ry + 14, 90, 24);
            }

            _room = UIKit.Label(Root, "", 24, Theme.Hover, px, 385, 300, 34, TextAnchor.MiddleCenter, FontStyle.Bold);
            _moves = UIKit.Label(Root, "", 19, Theme.Gray, px, 422, 300, 28);
            _accuracyTitle = UIKit.Label(Root, "Hamle analizi (isabet)", 15, Theme.Gray, px, 458, 300, 24);
            _accuracy = UIKit.Label(Root, "", 20, Theme.White, px, 484, 300, 28);
            // Dikey: oda ve hamle tek satirda, isabet iki satir
            P(_room, -130, 747, 240, 32);
            P(_moves, 130, 747, 240, 32);
            P(_accuracyTitle, 0, 772, 400, 24);
            P(_accuracy, 0, 798, 500, 28);
            // AI oyununda "Yeni Oyun" / bitince "Tekrar Oyna" (panel y 135-615 icinde)
            _again = UIKit.Button(Root, "Tekrar Oyna", Theme.Green, app.PlayAgain, px, 530, 180, 48);
            _again.gameObject.SetActive(false);
            P(_again, 0, 842, 160, 52);
            // AI oyununda "Geri Al" (452-492): "Tekrar Oyna"nin (506-554) ustunde; isabet
            // satirlari yalnizca online oyunda dolu, burada bos. Dolgu panelden (Theme.Panel)
            // farkli olmali: ayni renkte buton panelin icinde kaybolur, yalnizca yazi gorunur
            _undo = UIKit.Button(Root, "Geri Al", Theme.InputBackground, app.UndoAIMove, px, 472, 180, 40, 18);
            _undo.gameObject.SetActive(false);
            P(_undo, -170, 842, 160, 52);
            // Biten online oyunda "Rovans": ayni yerde, "Tekrar Oyna" yalnizca AI oyununda gorunur
            _rematch = UIKit.Button(Root, "Rövanş", Theme.Green, app.RequestRematch, px, 530, 180, 48, 18);
            _rematch.gameObject.SetActive(false);
            P(_rematch, 0, 842, 160, 52);
            _menu = UIKit.Button(Root, "Menü", Theme.Button, app.RequestBack, px, 590, 180, 48);
            _menuLabel = _menu.GetComponentInChildren<Text>();
            // Dikey: Geri Al | Yeni Oyun / Rovans | Menu tek satirda, en alt kenar y=868 (< 888)
            P(_menu, 170, 842, 160, 52);
        }

        public override void OnShow() => UIKit.ClearSelection();

        public override void Refresh()
        {
            var app = App;

            // Klavye: 1-7 tasi o sutuna birakir (siranin kimde oldugunu HandleColumnClick denetler)
            int key = Keys.ColumnPressed();
            if (key >= 0)
                app.HandleColumnClick(key);

            // Oyun bitince baslik sonucu gosterir (son tas dusmeden once degil)
            var headline = app.ResultHeadline;
            if (headline.HasValue && !Board.IsAnimating)
            {
                _title.text = headline.Value.text;
                _title.color = HeadlineColor(headline.Value.tone);
            }
            else
            {
                _title.text = app.IsSpectator ? "CANLI YAYIN" : app.Screen == AppScreen.PlayingAI ? "Yapay Zekâya Karşı" : "Online Maç";
                _title.color = Theme.Red;
            }
            _panelTitle.text = app.IsSpectator ? "İZLİYORSUNUZ" : "OYUN BİLGİSİ";
            _panelTitle.color = app.IsSpectator ? Theme.Waiting : Theme.White;

            var (p1, p1Elo, p2, p2Elo) = app.PlayerLabels();
            SetPlayer(0, p1, p1Elo, Core.Board.Player1);
            SetPlayer(1, p2, p2Elo, Core.Board.Player2);

            _room.text = app.RoomId != null ? "Oda: " + app.RoomId : "";
            _moves.text = "Hamle: " + app.Game.MoveCount;

            var s = app.Summary;
            _accuracyTitle.enabled = s != null;
            _accuracy.text = s != null ? $"Sen: %{s.MyAccuracy:0}   Rakip: %{s.OpponentAccuracy:0}" : "";

            _menuLabel.text = app.BackLabel;
            bool again = app.Screen == AppScreen.PlayingAI;
            if (again)
                UIKit.SetLabel(_again, app.NewGameLabel);
            if (_again.gameObject.activeSelf != again)
                _again.gameObject.SetActive(again);
            bool undo = app.CanUndo;
            if (_undo.gameObject.activeSelf != undo)
                _undo.gameObject.SetActive(undo);
            bool rematch = app.CanRequestRematch;
            if (rematch)
                UIKit.SetLabel(_rematch, app.RematchLabel);
            if (_rematch.gameObject.activeSelf != rematch)
                _rematch.gameObject.SetActive(rematch);
        }

        private Color HeadlineColor(StatusTone tone)
        {
            int w = App.Game.Winner;
            if (App.IsSpectator && w != 0)
                return Theme.PieceColor(w);
            return tone == StatusTone.Good ? Theme.Green : tone == StatusTone.Bad ? Theme.Red : Theme.Yellow;
        }

        private void SetPlayer(int i, string name, int? elo, int piece)
        {
            // Isim iki tarafta da ayni (en fazla 14 karakter, misafir adi tam sigar);
            // "(Sen)" etiketi isim satirina sigmadigi icin alttaki ELO satirinda durur.
            _names[i].text = name != null && name.Length > 14 ? name.Substring(0, 14) : name;
            string eloText = elo.HasValue ? "ELO: " + elo.Value : "";
            if (App.IsLocalPiece(piece))
                eloText = eloText.Length > 0 ? "(Sen)  " + eloText : "(Sen)";
            _elos[i].text = eloText;
            _turns[i].enabled = App.Game.CurrentPlayer == piece && !App.Game.GameOver;
            int? secs = App.TurnSecondsLeft;
            if (_turns[i].enabled && secs.HasValue)
            {
                _clocks[i].text = secs.Value + " sn";
                _clocks[i].color = App.TurnClockWarning ? Theme.Error : Theme.Gray;
            }
            else
                _clocks[i].text = "";
        }
    }
}
