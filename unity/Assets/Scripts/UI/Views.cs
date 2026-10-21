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

        protected Text Title(string text, float y = 50) =>
            UIKit.Label(Root, text, 44, Theme.Red, 0, y, 1000, 60, TextAnchor.MiddleCenter, FontStyle.Bold);
    }

    // -------------------------------------------------------------------------
    public sealed class LoginView : View
    {
        private readonly InputField _username;
        private readonly InputField _password;

        public LoginView(AppController app, Transform parent) : base(app, parent, "Login")
        {
            Title("CONNECT FOUR PRO", 80);
            UIKit.Label(Root, "ULTIMATE", 22, Theme.Yellow, 0, 122, 400, 30, TextAnchor.MiddleCenter, FontStyle.Bold);
            UIKit.Label(Root, "Hoş geldiniz!", 26, Theme.White, 0, 170);

            UIKit.Label(Root, "Kullanıcı Adı", 18, Theme.Gray, 0, 220, 320, 26);
            _username = UIKit.Input(Root, "kullanıcı adı", false, 0, 255, 320, 50, AppController.UsernameMaxLength);
            UIKit.Label(Root, "Şifre", 18, Theme.Gray, 0, 305, 320, 26);
            _password = UIKit.Input(Root, "şifre", true, 0, 340, 320, 50, 128);

            UIKit.Button(Root, "Giriş Yap", Theme.Button, Login, -82, 420, 150, 50);
            UIKit.Button(Root, "Kayıt Ol", Theme.Green, () => App.Register(_username.text, _password.text), 82, 420, 150, 50);

            var line = UIKit.Image(Root, "Divider", Theme.Gray);
            UIKit.Place(line.rectTransform, 0, 488, 240, 1);
            var orBg = UIKit.Image(Root, "OrBg", Theme.Background);
            UIKit.Place(orBg.rectTransform, 0, 488, 60, 22);
            UIKit.Label(Root, "veya", 16, Theme.Gray, 0, 488, 60, 22);
            UIKit.Button(Root, "Misafir Olarak Devam", Theme.Panel, App.GuestLogin, 0, 540, 280, 50);

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
            Title("CONNECT FOUR PRO", 50);
            _name = UIKit.Label(Root, "", 26, Theme.White, 0, 100);
            _elo = UIKit.Label(Root, "", 20, Theme.Green, 0, 130);

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
                UIKit.Button(Root, items[i].label, items[i].color, items[i].action, 0, 200 + i * 66, 300, 52, 21);
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
        public AISelectView(AppController app, Transform parent) : base(app, parent, "AISelect")
        {
            Title("ZORLUK SEVİYESİ SEÇ", 90);
            float y = 200;
            foreach (var (name, depth) in AIEngine.Difficulties)
            {
                int d = depth;
                UIKit.Button(Root, $"{name} (D{depth})", Theme.Button, () => app.StartAIGame(d), 0, y, 260, 56, 22);
                y += 76;
            }
            UIKit.Button(Root, "Geri", Theme.Panel, app.RequestBack, 0, y + 30, 260, 50);
        }
    }

    // -------------------------------------------------------------------------
    public sealed class LobbyView : View
    {
        private const int MaxRows = 8;
        private readonly RectTransform _rows;
        private readonly Text _empty;
        private int _shownVersion = -1;

        public LobbyView(AppController app, Transform parent) : base(app, parent, "Lobby")
        {
            Title("ONLİNE LOBİ", 45);
            UIKit.Button(Root, "+ Yeni Oyun", Theme.Button, app.CreateOnlineGame, -470, 110, 180, 48);
            UIKit.Button(Root, "Yenile", Theme.Button, () =>
            {
                app.RefreshActiveGames();
                app.SetStatus("Yenilendi");
            }, -320, 110, 100, 48);
            UIKit.Button(Root, "Geri", Theme.Panel, app.RequestBack, 500, 110, 120, 48);

            var header = UIKit.Panel(Root, "Header", Theme.Panel);
            UIKit.Place(header.rectTransform, 0, 170, 1180, 40);
            float[] cols = { -480, -260, -20, 220, 470 };
            string[] titles = { "ODA", "OYUNCU 1", "OYUNCU 2", "DURUM", "İŞLEM" };
            for (int i = 0; i < cols.Length; i++)
                UIKit.Label(Root, titles[i], 18, Theme.White, cols[i], 170, 220, 40, TextAnchor.MiddleCenter, FontStyle.Bold);

            _rows = UIKit.Stretch(Root, "Rows");
            _empty = UIKit.Label(Root, "Aktif oyun yok. Yeni bir oyun oluşturun!", 24, Theme.Gray, 0, 320);
        }

        public override void OnShow() => _shownVersion = -1;

        public override void Refresh()
        {
            if (_shownVersion == App.ActiveGamesVersion)
                return;
            _shownVersion = App.ActiveGamesVersion;
            for (int i = _rows.childCount - 1; i >= 0; i--)
                Object.Destroy(_rows.GetChild(i).gameObject);

            var games = App.ActiveGames;
            _empty.enabled = games.Count == 0;
            for (int i = 0; i < games.Count && i < MaxRows; i++)
                BuildRow(games[i], i);
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
        private readonly Text _room;
        private readonly Text _hint;
        private readonly Text _dots;

        public WaitingView(AppController app, Transform parent) : base(app, parent, "Waiting")
        {
            Title("RAKİP BEKLENİYOR", 170);
            _room = UIKit.Label(Root, "", 44, Theme.Green, 0, 270, 900, 60, TextAnchor.MiddleCenter, FontStyle.Bold);
            _hint = UIKit.Label(Root, "", 24, Theme.White, 0, 330);
            _dots = UIKit.Label(Root, "", 24, Theme.Gray, 0, 400);
            UIKit.Button(Root, "İptal", Theme.Panel, app.RequestBack, 0, 480, 180, 50);
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
            _dots.text = "Bekleniyor" + new string('.', (int)(Time.unscaledTime * 2) % 4);
        }
    }

    // -------------------------------------------------------------------------
    public sealed class LeaderboardView : View
    {
        private readonly Text _message;
        private readonly Text[] _lines = new Text[10];

        public LeaderboardView(AppController app, Transform parent) : base(app, parent, "Leaderboard")
        {
            Title("LİDERLİK TABLOSU", 55);
            _message = UIKit.Label(Root, "", 24, Theme.Gray, 0, 250);
            for (int i = 0; i < _lines.Length; i++)
                _lines[i] = UIKit.Label(Root, "", 21, Theme.White, 0, 125 + i * 42, 900, 40);
            UIKit.Button(Root, "Geri", Theme.Panel, app.RequestBack, 0, 655, 180, 50);
        }

        public override void Refresh()
        {
            var data = App.LeaderboardData;
            _message.text = App.LeaderboardError ? "Sunucuya bağlanılamadı"
                          : data == null ? "Yükleniyor..."
                          : data.Count == 0 ? "Henüz kayıtlı oyuncu yok" : "";
            for (int i = 0; i < _lines.Length; i++)
            {
                if (data != null && i < data.Count)
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
        private readonly Text _message;
        private readonly Text[,] _cells = new Text[10, 4];

        public HistoryView(AppController app, Transform parent) : base(app, parent, "History")
        {
            Title("MAÇ GEÇMİŞİ", 55);
            _message = UIKit.Label(Root, "", 24, Theme.Gray, 0, 250, 1000);
            float[] xs = { -390, -150, 110, 380 };
            for (int i = 0; i < 10; i++)
                for (int c = 0; c < 4; c++)
                    _cells[i, c] = UIKit.Label(Root, "", 20, Theme.White, xs[c], 120 + i * 48, 250, 40, TextAnchor.MiddleLeft);
            UIKit.Button(Root, "Geri", Theme.Panel, app.RequestBack, 0, 655, 180, 50);
        }

        public override void Refresh()
        {
            var data = App.HistoryData;
            _message.text = App.IsGuest ? "Maç geçmişi sadece kayıtlı oyuncular için tutulur."
                          : App.HistoryError ? "Sunucuya bağlanılamadı"
                          : data == null ? "Yükleniyor..."
                          : data.Count == 0 ? "Henüz online maç oynamadınız." : "";
            for (int i = 0; i < 10; i++)
            {
                bool has = !App.IsGuest && data != null && i < data.Count;
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
        private readonly Text _room;
        private readonly Text _moves;
        private readonly Text _accuracyTitle;
        private readonly Text _accuracy;
        private readonly Button _menu;

        public BoardView Board { get; }

        public GameView(AppController app, Transform parent) : base(app, parent, "Game")
        {
            _title = UIKit.Label(Root, "", 38, Theme.Red, 0, 42, 1000, 56, TextAnchor.MiddleCenter, FontStyle.Bold);

            Board = BoardView.Create(Root, -250, 375, () => App.Game, app.CanHumanMove, () => App.HumanPiece);
            Board.ColumnClicked += app.HandleColumnClick;

            const float px = 400;   // bilgi paneli merkezi
            var panel = UIKit.Panel(Root, "InfoPanel", Theme.Panel);
            UIKit.Place(panel.rectTransform, px, 375, 320, 480);
            _panelTitle = UIKit.Label(Root, "", 24, Theme.White, px, 165, 300, 34, TextAnchor.MiddleCenter, FontStyle.Bold);

            for (int i = 0; i < 2; i++)
            {
                float y = 225 + i * 70;
                var disc = UIKit.Image(Root, "Disc " + i, Theme.PieceColor(i + 1), UIKit.Circle);
                UIKit.Place(disc.rectTransform, px - 125, y, 34, 34);
                _names[i] = UIKit.Label(Root, "", 21, Theme.White, px - 10, y - 10, 180, 28, TextAnchor.MiddleLeft);
                _elos[i] = UIKit.Label(Root, "", 16, Theme.Gray, px - 10, y + 14, 180, 22, TextAnchor.MiddleLeft);
                _turns[i] = UIKit.Label(Root, "< SIRA", 18, Theme.Green, px + 110, y, 90, 30, TextAnchor.MiddleCenter, FontStyle.Bold);
            }

            _room = UIKit.Label(Root, "", 24, Theme.Hover, px, 385, 300, 34, TextAnchor.MiddleCenter, FontStyle.Bold);
            _moves = UIKit.Label(Root, "", 19, Theme.Gray, px, 422, 300, 28);
            _accuracyTitle = UIKit.Label(Root, "Hamle analizi (isabet)", 15, Theme.Gray, px, 458, 300, 24);
            _accuracy = UIKit.Label(Root, "", 20, Theme.White, px, 484, 300, 28);
            _menu = UIKit.Button(Root, "Menü", Theme.Button, app.RequestBack, px, 560, 180, 48);
        }

        public override void Refresh()
        {
            var app = App;
            _title.text = app.IsSpectator ? "CANLI YAYIN" : app.Screen == AppScreen.PlayingAI ? "Yapay Zekâya Karşı" : "Online Maç";
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

            UIKit.SetLabel(_menu, app.LeaveConfirmPending ? "Çıkışı Onayla" : "Menü");
        }

        private void SetPlayer(int i, string name, int? elo, int piece)
        {
            _names[i].text = name != null && name.Length > 14 ? name.Substring(0, 14) : name;
            _elos[i].text = elo.HasValue ? "ELO: " + elo.Value : "";
            _turns[i].enabled = App.Game.CurrentPlayer == piece && !App.Game.GameOver;
        }
    }
}
