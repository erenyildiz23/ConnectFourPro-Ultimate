// Arayuz dili (Turkce / Ingilizce). Saf C#: UnityEngine kullanmaz, testlenebilir.
//
// Oyun mantigi (AppController, gorunumler) metinleri Turkce uretir; bu metinler
// yalnizca ekrana yazilirken T() ile secili dile cevrilir. Boylece dil degisince
// ekrandaki her sey (durum cubugu dahil) bir sonraki karede yeni dile gecer ve
// mantik/testler dilden bagimsiz kalir.
//
// Tablo anahtari Turkce metnin kendisidir. {0}, {1} ... iceren anahtarlar sablondur:
// "Hoş geldin {0}!" anahtari "Hoş geldin Ali!" metnini de cevirir. Sablona giren
// parcalar da (ornegin "Hata: Oda bulunamadi" icindeki sunucu mesaji) cevrilir.
using System;
using System.Collections.Generic;
using System.Text.RegularExpressions;

namespace ConnectFourPro.Game
{
    public enum Lang { Tr, En }

    public static class Loc
    {
        private static Lang _current = Lang.Tr;

        /// <summary>Dil degisince (yeni dil ile) cagrilir.</summary>
        public static event Action<Lang> Changed;

        public static Lang Current
        {
            get => _current;
            set
            {
                if (_current == value)
                    return;
                _current = value;
                _cache.Clear();
                Changed?.Invoke(value);
            }
        }

        /// <summary>PlayerPrefs'te saklanan kisa ad ("tr" / "en").</summary>
        public static string Code(Lang lang) => lang == Lang.En ? "en" : "tr";

        /// <summary>Kayitli tercih varsa o; yoksa sistem dili Turkce ise TR, degilse EN.</summary>
        public static Lang Initial(string savedCode, bool systemIsTurkish)
        {
            if (savedCode == "tr")
                return Lang.Tr;
            if (savedCode == "en")
                return Lang.En;
            return systemIsTurkish ? Lang.Tr : Lang.En;
        }

        /// <summary>Dil degistirme dugmesinin yazisi: gecilecek dilin adi (cevrilmez).</summary>
        public static string ToggleLabel => _current == Lang.Tr ? "English" : "Türkçe";

        public static void Toggle() => Current = _current == Lang.Tr ? Lang.En : Lang.Tr;

        /// <summary>Turkce metni secili dile cevirir; tabloda yoksa oldugu gibi dondurur.</summary>
        public static string T(string tr) => T(tr, _current);

        public static string T(string tr, Lang lang)
        {
            if (string.IsNullOrEmpty(tr) || lang == Lang.Tr)
                return tr ?? "";
            if (_cache.TryGetValue(tr, out var hit))
                return hit;
            string result = Translate(tr, 0);
            if (_cache.Count > 512)
                _cache.Clear();
            _cache[tr] = result;
            return result;
        }

        /// <summary>Sunucu hata olayinin gosterilecek (Turkce) metni: bilinen code onceliklidir,
        /// code yoksa ya da bilinmiyorsa sunucunun msg alani (eski sunucu).</summary>
        public static string ServerError(string code, string msg)
        {
            if (!string.IsNullOrEmpty(code) && ServerCodes.TryGetValue(code, out var tr))
                return tr;
            return msg ?? "";
        }

        private static string Translate(string tr, int depth)
        {
            if (En.TryGetValue(tr, out var exact))
                return exact;
            if (depth > 3)
                return tr;
            foreach (var t in Templates)
            {
                var m = t.Pattern.Match(tr);
                if (!m.Success)
                    continue;
                var args = new object[m.Groups.Count - 1];
                for (int i = 1; i < m.Groups.Count; i++)
                    args[i - 1] = Translate(m.Groups[i].Value, depth + 1);
                return string.Format(t.En, args);
            }
            return tr;
        }

        // =====================================================================
        // Tablo
        // =====================================================================

        private sealed class Template
        {
            public Regex Pattern;
            public string En;
        }

        private static readonly Dictionary<string, string> _cache = new Dictionary<string, string>();

        /// <summary>Sunucu socket hata kodlari (src/server.py ERROR_CODES) -> sunucunun Turkce mesaji.</summary>
        public static readonly IReadOnlyDictionary<string, string> ServerCodes = new Dictionary<string, string>
        {
            ["session_invalid"] = "Oturum gecersiz, tekrar giris yapin",
            ["invalid_user"] = "Gecersiz kullanici",
            ["name_registered"] = "Bu kullanici adi kayitli, giris yapin",
            ["guest_name_taken"] = "Bu misafir adi kullanimda",
            ["invalid_request"] = "Gecersiz istek",
            ["room_not_found"] = "Oda bulunamadi",
            ["own_game"] = "Kendi oyununuza katilamazsiniz",
            ["already_connected"] = "Bu oyuna zaten bagli durumdasiniz",
            ["bad_resume_token"] = "Yeniden baglanma anahtari gecersiz",
            ["replaced_by_other_connection"] = "Baska bir baglantidan oyuna girildi",
            ["waiting_opponent"] = "Rakip bekleniyor!",
            ["not_a_player"] = "Bu oyunda hamle yapma yetkiniz yok!",
            ["invalid_move"] = "Gecersiz hamle!",
            ["game_over"] = "Oyun bitti",
            ["not_your_turn"] = "Sira sizde degil!",
            ["rematch_players_only"] = "Sadece oyuncular rovans isteyebilir",
            ["game_in_progress"] = "Oyun devam ediyor",
            ["already_in_game"] = "Zaten bir oyundasiniz",
        };

        /// <summary>Turkce -> Ingilizce. {n} iceren anahtarlar sablondur.</summary>
        public static readonly IReadOnlyDictionary<string, string> Table = new Dictionary<string, string>
        {
            // --- Giris
            ["Hoş geldiniz!"] = "Welcome!",
            ["Kullanıcı Adı"] = "Username",
            ["kullanıcı adı"] = "username",
            ["Şifre"] = "Password",
            ["şifre"] = "password",
            ["Giriş Yap"] = "Log In",
            ["Kayıt Ol"] = "Sign Up",
            ["veya"] = "or",
            ["Misafir Olarak Devam"] = "Continue as Guest",
            ["Sunucu: {0}"] = "Server: {0}",

            // --- Menu
            ["Yapay Zekâya Karşı"] = "Versus AI",
            ["Hızlı Maç"] = "Quick Match",
            ["Online Lobi"] = "Online Lobby",
            ["Liderlik Tablosu"] = "Leaderboard",
            ["Maç Geçmişi"] = "Match History",
            ["Çıkış Yap"] = "Log Out",
            ["Oyunu Kapat"] = "Quit Game",
            ["Misafir: {0}"] = "Guest: {0}",

            // --- Yapay zeka secimi
            ["ZORLUK SEVİYESİ SEÇ"] = "SELECT DIFFICULTY",
            ["Geri"] = "Back",
            ["Kolay"] = "Easy",
            ["Orta"] = "Medium",
            ["Zor"] = "Hard",
            ["Kolay - yeni başlayanlar için"] = "Easy - for beginners",
            ["Orta - dengeli rakip"] = "Medium - a balanced opponent",
            ["Zor - en güçlü rakip"] = "Hard - the strongest opponent",
            ["İlk hamle: AI"] = "First move: AI",
            ["İlk hamle: Sen"] = "First move: You",
            ["AI - {0}"] = "AI - {0}",

            // --- Lobi / bekleme
            ["ONLİNE LOBİ"] = "ONLINE LOBBY",
            ["+ Yeni Oyun"] = "+ New Game",
            ["Yenile"] = "Refresh",
            ["Yenilendi"] = "Refreshed",
            ["Süresiz"] = "Untimed",   // sure secimi; "3+2" ve saat ("3:00") cevrilmez
            ["ODA"] = "ROOM",
            ["OYUNCU 1"] = "PLAYER 1",
            ["OYUNCU 2"] = "PLAYER 2",
            ["DURUM"] = "STATUS",
            ["İŞLEM"] = "ACTION",
            ["OYUNCULAR"] = "PLAYERS",
            ["Aktif oyun yok. Yeni bir oyun oluşturun!"] = "No active games. Create a new one!",
            ["Bekleniyor"] = "Waiting",
            ["Bekleniyor."] = "Waiting.",
            ["Bekleniyor.."] = "Waiting..",
            ["Bekleniyor..."] = "Waiting...",
            ["Bekliyor"] = "Waiting",
            ["Katıl"] = "Join",
            ["İzle"] = "Watch",
            ["Oyunda ({0} hamle)"] = "Playing ({0} moves)",
            ["RAKİP BEKLENİYOR"] = "WAITING FOR OPPONENT",
            ["İptal"] = "Cancel",
            ["Oda Kodu: {0}"] = "Room Code: {0}",
            ["Rakip lobiden katılabilir!"] = "Your opponent can join from the lobby!",
            ["Oda oluşturuluyor..."] = "Creating room...",
            ["RAKİP ARANIYOR"] = "FINDING OPPONENT",
            ["Rakip aranıyor..."] = "Searching for an opponent...",
            ["Eşleşince oyun başlar."] = "The game starts once matched.",

            // --- Liderlik / gecmis
            ["LİDERLİK TABLOSU"] = "LEADERBOARD",
            ["Sunucuya bağlanılamadı"] = "Could not connect to the server",
            ["Yükleniyor..."] = "Loading...",
            ["Henüz kayıtlı oyuncu yok"] = "No registered players yet",
            ["{0}. {1}  -  ELO: {2}  (G:{3} M:{4})"] = "{0}. {1}  -  ELO: {2}  (W:{3} L:{4})",
            ["MAÇ GEÇMİŞİ"] = "MATCH HISTORY",
            ["Maç geçmişi sadece kayıtlı oyuncular için tutulur."] = "Match history is kept only for registered players.",
            ["Henüz online maç oynamadınız."] = "You haven't played an online match yet.",
            ["KAZANDIN"] = "YOU WON",
            ["KAYBETTİN"] = "YOU LOST",
            ["BERABERE"] = "DRAW",
            ["İPTAL EDİLDİ"] = "ABORTED",
            ["{0} hamle"] = "{0} moves",

            // --- Mac tekrari
            ["MAÇ TEKRARI"] = "MATCH REPLAY",
            ["Tekrarı izle"] = "Watch replay",
            ["Hamle {0} / {1}"] = "Move {0} / {1}",

            // --- Oyun ekrani
            ["Hamle analizi (isabet)"] = "Move analysis (accuracy)",
            ["Tekrar Oyna"] = "Play Again",
            ["Yeni Oyun"] = "New Game",
            ["Geri Al"] = "Undo",
            ["Rövanş"] = "Rematch",
            ["Rövanşı Kabul Et"] = "Accept Rematch",
            ["Menü"] = "Menu",
            ["Lobiye Dön"] = "Back to Lobby",
            ["Çıkışı Onayla"] = "Confirm Leave",
            ["< SIRA"] = "< TURN",
            ["CANLI YAYIN"] = "LIVE",
            ["Online Maç"] = "Online Match",
            ["İZLİYORSUNUZ"] = "SPECTATING",
            ["OYUN BİLGİSİ"] = "GAME INFO",
            ["Oda: {0}"] = "Room: {0}",
            ["Hamle: {0}"] = "Moves: {0}",
            ["Sen: %{0}   Rakip: %{1}"] = "You: {0}%   Opponent: {1}%",
            ["(Sen)"] = "(You)",
            ["(Sen)  {0}"] = "(You)  {0}",
            ["{0} sn"] = "{0}s",
            ["Rakip"] = "Opponent",
            ["Oyuncu 1"] = "Player 1",
            ["Oyuncu 2"] = "Player 2",
            ["KAZANDIN!"] = "YOU WON!",
            ["AI KAZANDI"] = "AI WINS",
            ["KIRMIZI KAZANDI"] = "RED WINS",
            ["SARI KAZANDI"] = "YELLOW WINS",

            // --- Durum cubugu: giris / kayit
            ["Kullanıcı adı ve şifre gerekli!"] = "Username and password required!",
            ["Giriş yapılıyor..."] = "Logging in...",
            ["Sunucuya bağlanılamadı!"] = "Could not connect to the server!",
            ["Hoş geldin {0}!"] = "Welcome {0}!",
            ["Yanlış kullanıcı adı veya şifre!"] = "Wrong username or password!",
            ["Çok fazla deneme! Biraz sonra tekrar deneyin."] = "Too many attempts! Please try again later.",
            ["Sunucu veritabanına ulaşamıyor. Misafir olarak devam edebilirsiniz."] =
                "The server can't reach its database. You can continue as a guest.",
            ["Sunucu veritabanına ulaşamıyor."] = "The server can't reach its database.",
            ["Giriş başarısız!"] = "Login failed!",
            ["Kullanıcı adı en az {0}, şifre en az {1} karakter olmalı!"] =
                "Username must be at least {0} and password at least {1} characters!",
            ["Hesap oluşturuluyor..."] = "Creating account...",
            ["Kayıt başarılı! Hoş geldin {0}!"] = "Signed up! Welcome {0}!",
            ["Bu kullanıcı adı zaten alınmış!"] = "This username is already taken!",
            ["Geçersiz kullanıcı adı veya şifre (harf, rakam, _ . - kullanın)"] =
                "Invalid username or password (use letters, digits, _ . -)",
            ["Kayıt başarısız!"] = "Sign up failed!",

            // --- Durum cubugu: oyun
            ["Dört taşı yatay, dikey ya da çapraz diz. Kırmızı sensin - bir sütuna tıkla."] =
                "Line up four discs horizontally, vertically or diagonally. You are red - click a column.",
            ["Hamle geri alındı. Senin sıran!"] = "Move undone. Your turn!",
            ["AI düşünüyor..."] = "AI is thinking...",
            ["Senin sıran!"] = "Your turn!",
            ["Rakibin sırası..."] = "Opponent's turn...",
            ["Bu sütun dolu!"] = "This column is full!",
            ["Kazandın!"] = "You won!",
            ["Kaybettin."] = "You lost.",
            ["Berabere!"] = "Draw!",
            ["Oyun iptal edildi (puansız)"] = "Game aborted (unrated)",
            ["AI kazandı!"] = "AI wins!",
            ["Kırmızı kazandı!"] = "Red wins!",
            ["Sarı kazandı!"] = "Yellow wins!",
            ["{0} kazandı!"] = "{0} wins!",
            ["{0}  ELO {1} ({2})"] = "{0}  ELO {1} ({2})",
            ["{0} (süre doldu)"] = "{0} (time ran out)",
            ["{0} (bağlantı koptu)"] = "{0} (disconnected)",
            ["{0} (oyun terk edildi)"] = "{0} (game abandoned)",
            ["{0} (hükmen)"] = "{0} (forfeit)",
            ["Rakibin süresi doldu, kazandın!"] = "Your opponent ran out of time, you won!",
            ["Rakibin bağlantısı koptu, hükmen kazandın!"] = "Your opponent disconnected, you won by forfeit!",
            ["Rakip oyunu terk etti - Kazandın!"] = "Your opponent left the game - You won!",
            ["Süre doldu, hükmen kaybettin."] = "Time ran out, you lost by forfeit.",
            ["Bağlantın koptuğu için hükmen kaybettin."] = "You lost by forfeit because you disconnected.",
            ["Oyunu terk ettin, hükmen kaybettin."] = "You left the game, you lost by forfeit.",
            ["Hükmen kaybettin."] = "You lost by forfeit.",
            ["Oyundan çıkmak hükmen yenilgi sayılır. Onaylamak için tekrar basın."] =
                "Leaving counts as a forfeit loss. Press again to confirm.",

            // --- Durum cubugu: online
            ["Odaya katılınıyor..."] = "Joining room...",
            ["Yayına bağlanılıyor..."] = "Connecting to the stream...",
            ["Oyun başladı! Senin sıran."] = "Game started! Your turn.",
            ["Oyun başladı! Rakibin sırası."] = "Game started! Opponent's turn.",
            ["Rövanş başladı! Senin sıran."] = "Rematch started! Your turn.",
            ["Rövanş başladı! Rakibin sırası."] = "Rematch started! Opponent's turn.",
            ["Rövanş başladı! Canlı izleniyor"] = "Rematch started! Watching live",
            ["Canlı izleniyor"] = "Watching live",
            ["Yayına geri dönüldü. Canlı izleniyor"] = "Back to the stream. Watching live",
            ["Oyuna geri dönüldü. {0}"] = "Back in the game. {0}",
            ["Rakip geri döndü. "] = "Your opponent is back. ",
            ["Rakip geri döndü. {0}"] = "Your opponent is back. {0}",
            ["Bağlantı koptu! Yeniden bağlanılıyor..."] = "Connection lost! Reconnecting...",
            ["Bağlantı koptu! Yeniden bağlanılıyor... ({0} sn)"] = "Connection lost! Reconnecting... ({0}s)",
            ["Bağlantı koptu! Oda kapanmış olabilir, yeniden bağlanılıyor..."] =
                "Connection lost! The room may be closed, reconnecting...",
            ["Bağlantı koptu, rövanş yapılamaz."] = "Connection lost, no rematch possible.",
            ["Bağlantı yok, hamle gönderilemedi."] = "No connection, move not sent.",
            ["Rakibin bağlantısı koptu! {0} sn içinde dönmezse kazanırsın."] =
                "Your opponent disconnected! You win if they don't return within {0}s.",
            ["Bir oyuncunun bağlantısı koptu..."] = "A player disconnected...",
            ["Rakibin bağlantısı koptu. Hamleni yapabilirsin; yapmazsan oyun iptal edilir (puansız)."] =
                "Opponent disconnected. You can still move; if you don't, the game is aborted (unrated).",
            ["Rakibin bağlantısı koptu. Dönüp ilk hamleyi yapmazsa oyun iptal edilir (puansız)."] =
                "Opponent disconnected. If they don't return and make the first move, the game is aborted (unrated).",
            ["Yayın bağlantısı geri gelmedi. Lobiye dönüp tekrar izleyebilirsin."] =
                "The stream connection did not come back. Return to the lobby to watch again.",
            ["Sunucuya yeniden bağlanılamadı. Oyun hükmen kaybedilmiş olabilir; lobiye dönebilirsin."] =
                "Could not reconnect to the server. The game may be lost by forfeit; you can return to the lobby.",
            ["Rövanş kabul edildi, oyun başlıyor..."] = "Rematch accepted, starting...",
            ["Rövanş istendi, rakip bekleniyor..."] = "Rematch requested, waiting for your opponent...",
            ["Rakip rövanş istiyor!"] = "Your opponent wants a rematch!",
            ["Rakip ayrıldı, rövanş yapılamaz."] = "Your opponent left, no rematch possible.",
            ["Rövanş yapılamaz."] = "No rematch possible.",
            ["Oda zaman aşımına uğradı."] = "The room timed out.",
            ["Oda zaman aşımı nedeniyle kapatıldı. Lobiye dönebilirsin."] =
                "The room was closed after a timeout. You can return to the lobby.",
            ["Oda kapandı, rövanş yapılamaz."] = "The room closed, no rematch possible.",
            ["Oyun sunucuda sona ermiş. Lobiye dönebilirsin."] = "The game has ended on the server. You can return to the lobby.",
            ["Yayın sunucuda sona ermiş. Lobiye dönebilirsin."] = "The stream has ended on the server. You can return to the lobby.",
            ["Hata: {0}"] = "Error: {0}",
            ["Rakip arama sona erdi."] = "The search has ended.",
            ["Bağlantı koptu, arama iptal edildi."] = "Connection lost, search cancelled.",

            // --- Hazir sohbet (Game/QuickChat.cs; numara sirasiyla)
            ["Sohbet"] = "Chat",
            ["İyi oyun!"] = "Good game!",
            ["Bol şans!"] = "Good luck!",
            ["Güzel hamle!"] = "Nice move!",
            ["Hay aksi!"] = "Oops!",
            ["Düşünüyorum..."] = "Thinking...",
            ["Teşekkürler!"] = "Thanks!",
            ["Rövanş?"] = "Rematch?",
            ["Selam!"] = "Hi!",

            // --- Sunucu hata mesajlari (src/server.py; ASCII Turkce)
            ["Oturum gecersiz, tekrar giris yapin"] = "Session expired, please log in again",
            ["Gecersiz kullanici"] = "Invalid user",
            ["Bu kullanici adi kayitli, giris yapin"] = "This username is registered, please log in",
            ["Bu misafir adi kullanimda"] = "This guest name is in use",
            ["Gecersiz istek"] = "Invalid request",
            ["Oda bulunamadi"] = "Room not found",
            ["Kendi oyununuza katilamazsiniz"] = "You can't join your own game",
            ["Bu oyuna zaten bagli durumdasiniz"] = "You are already connected to this game",
            ["Yeniden baglanma anahtari gecersiz"] = "Reconnect key is invalid",
            ["Baska bir baglantidan oyuna girildi"] = "The game was opened from another connection",
            ["Rakip bekleniyor!"] = "Waiting for an opponent!",
            ["Bu oyunda hamle yapma yetkiniz yok!"] = "You can't make moves in this game!",
            ["Gecersiz hamle!"] = "Invalid move!",
            ["Oyun bitti"] = "Game over",
            ["Sira sizde degil!"] = "It's not your turn!",
            ["Sadece oyuncular rovans isteyebilir"] = "Only players can request a rematch",
            ["Oyun devam ediyor"] = "Game in progress",
            ["Zaten bir oyundasiniz"] = "You are already in a game",
        };

        private static readonly Dictionary<string, string> En = new Dictionary<string, string>();
        private static readonly List<Template> Templates = new List<Template>();
        private static readonly Regex Placeholder = new Regex(@"\{(\d+)\}");

        static Loc()
        {
            foreach (var kv in Table)
            {
                if (!Placeholder.IsMatch(kv.Key))
                {
                    En[kv.Key] = kv.Value;
                    continue;
                }
                // "{0} kazandı!" -> ^(.+?) kazandı!$ ; parcalar sirayla {0},{1}... olmalidir
                string pattern = "^" + Placeholder.Replace(Regex.Escape(kv.Key).Replace(@"\{", "{"), "(.+?)") + "$";
                Templates.Add(new Template { Pattern = new Regex(pattern, RegexOptions.CultureInvariant), En = kv.Value });
            }
            // Uzun (daha belirgin) sablon once denenir: "Kayıt başarılı! Hoş geldin {0}!" > "Hoş geldin {0}!"
            Templates.Sort((a, b) => b.Pattern.ToString().Length.CompareTo(a.Pattern.ToString().Length));
        }
    }
}
