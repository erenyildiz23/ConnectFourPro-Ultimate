// =============================================================================
// ArenaModel.cs - Connect Four Pro Ultimate
// Arena turnuvasi verisi: turnuva ozeti, puan durumu satiri ve yardimcilar
// =============================================================================
//
// Sunucu (src/server.py) turnuvayi {id, creator, duration_minutes, starts_at, ends_at,
// status, players} ve puan durumunu {rank, username, score, games_played, streak,
// on_fire, paused, recent} olarak gonderir. Turnuva adi sunucudan gelmez; istemci
// creator'dan sabit kalipla kurar (DisplayName). UnityEngine kullanmaz, testlenebilir.

using System;
using System.Collections.Generic;
using System.Globalization;
using ConnectFourPro.Net;

namespace ConnectFourPro.Game
{
    /// <summary>Turnuva listesindeki / sayfasindaki bir turnuva.</summary>
    public sealed class TournamentSummary
    {
        public int Id;
        public string Creator = "";
        public int DurationMinutes;
        /// <summary>Baslangic (UTC); bozuk ya da yoksa null.</summary>
        public DateTime? StartsAt;
        /// <summary>Bitis (UTC); bozuk ya da yoksa null.</summary>
        public DateTime? EndsAt;
        /// <summary>scheduled / running / finished / cancelled.</summary>
        public string Status = "";
        public int Players;

        public bool IsScheduled => Status == ArenaModel.Scheduled;
        public bool IsRunning => Status == ArenaModel.Running;
        /// <summary>Bitti ya da iptal edildi: katilma ve eslesme yok.</summary>
        public bool IsOver => Status == ArenaModel.Finished || Status == ArenaModel.Cancelled;

        public static TournamentSummary From(JsonObject o)
        {
            return new TournamentSummary
            {
                Id = o.GetInt("id"),
                Creator = o.GetString("creator", ""),
                DurationMinutes = o.GetInt("duration_minutes"),
                StartsAt = ArenaModel.ParseUtc(o.GetString("starts_at")),
                EndsAt = ArenaModel.ParseUtc(o.GetString("ends_at")),
                Status = o.GetString("status", ""),
                Players = o.GetInt("players"),
            };
        }
    }

    /// <summary>Puan durumunun bir satiri (sunucu siralamasiyla gelir).</summary>
    public sealed class StandingRow
    {
        public int Rank;
        public string Username = "";
        public int Score;
        public int GamesPlayed;
        public int Streak;
        /// <summary>Seri ates modunda (3. art arda galibiyetten itibaren 4 puan).</summary>
        public bool OnFire;
        public bool Paused;
        /// <summary>Son 5 sonuc, eskiden yeniye: "WDL..." (W galibiyet, D beraberlik, L yenilgi).</summary>
        public string Recent = "";

        public static StandingRow From(JsonObject o)
        {
            return new StandingRow
            {
                Rank = o.GetInt("rank"),
                Username = o.GetString("username", ""),
                Score = o.GetInt("score"),
                GamesPlayed = o.GetInt("games_played"),
                Streak = o.GetInt("streak"),
                OnFire = o.GetBool("on_fire"),
                Paused = o.GetBool("paused"),
                Recent = o.GetString("recent", ""),
            };
        }
    }

    public static class ArenaModel
    {
        public const string Scheduled = "scheduled";
        public const string Running = "running";
        public const string Finished = "finished";
        public const string Cancelled = "cancelled";

        /// <summary>Sunucunun kabul ettigi sureler (dakika).</summary>
        public static readonly int[] Durations = { 15, 30, 60 };
        /// <summary>Baslangic en gec bu kadar dakika sonra (24 saat).</summary>
        public const int MaxStartInMinutes = 24 * 60;

        public static bool IsValidDuration(int minutes) => Array.IndexOf(Durations, minutes) >= 0;
        public static bool IsValidStartIn(int minutes) => minutes >= 0 && minutes <= MaxStartInMinutes;

        /// <summary>Turnuva adi: sabit kalip (Turkce ek unlu uyumu yapilmaz).</summary>
        public static string DisplayName(string creator, Lang lang) =>
            lang == Lang.En ? creator + "'s Arena" : creator + "'nın Arenası";

        /// <summary>{standings: [...]} (arena_standings ve GET /tournaments/&lt;id&gt;) satirlari.</summary>
        public static List<StandingRow> ParseStandings(JsonObject data)
        {
            var rows = new List<StandingRow>();
            if (data == null)
                return rows;
            foreach (JsonObject o in data.GetObjectList("standings"))
                rows.Add(StandingRow.From(o));
            return rows;
        }

        /// <summary>GET /tournaments yaniti {tournaments: [...]}.</summary>
        public static List<TournamentSummary> ParseTournaments(JsonObject data)
        {
            var list = new List<TournamentSummary>();
            if (data == null)
                return list;
            foreach (JsonObject o in data.GetObjectList("tournaments"))
                list.Add(TournamentSummary.From(o));
            return list;
        }

        /// <summary>
        /// Sunucunun ISO 8601 zamani (Python isoformat) -> UTC. Saat dilimi yoksa UTC kabul
        /// edilir (sunucu UTC tutar). Bozuk ya da bos metin: null.
        /// </summary>
        public static DateTime? ParseUtc(string iso)
        {
            if (string.IsNullOrEmpty(iso))
                return null;
            if (DateTime.TryParse(iso, CultureInfo.InvariantCulture,
                                  DateTimeStyles.AdjustToUniversal | DateTimeStyles.AssumeUniversal,
                                  out DateTime t))
                return DateTime.SpecifyKind(t, DateTimeKind.Utc);
            return null;
        }

        /// <summary>
        /// Turnuva acma formunun baslangic secenekleri (dakika sonra): hemen, 15 dk adimla
        /// 1 saate kadar, 1.5 ve 2 saat, sonra saat basi 24 saate kadar.
        /// </summary>
        public static readonly int[] StartOptions = BuildStartOptions();

        private static int[] BuildStartOptions()
        {
            var list = new List<int> { 0, 15, 30, 45, 60, 90, 120 };
            for (int m = 180; m <= MaxStartInMinutes; m += 60)
                list.Add(m);
            return list.ToArray();
        }

        /// <summary>Baslangic seciminde bir sonraki (dir &gt; 0) / onceki secenek; uclarda durur.</summary>
        public static int StepStartIn(int current, int dir)
        {
            if (dir > 0)
            {
                foreach (int m in StartOptions)
                    if (m > current)
                        return m;
                return StartOptions[StartOptions.Length - 1];
            }
            for (int i = StartOptions.Length - 1; i >= 0; i--)
                if (StartOptions[i] < current)
                    return StartOptions[i];
            return StartOptions[0];
        }

        /// <summary>UTC zamanin yerel saati "SS:dd" (offsetMinutes: tarayicinin UTC farki, dogu +).</summary>
        public static string LocalClock(DateTime utc, int offsetMinutes) =>
            utc.AddMinutes(offsetMinutes).ToString("HH:mm", CultureInfo.InvariantCulture);

        /// <summary>
        /// Turnuvanin durum yazisi (Turkce; ekranda Loc.T ile cevrilir): surerken "18:42 kaldı",
        /// planliyken "Başlıyor 21:00" (yerel saat), bitince "Turnuva bitti" / "İptal edildi".
        /// </summary>
        public static string StatusText(TournamentSummary t, DateTime nowUtc, int offsetMinutes)
        {
            if (t == null)
                return "";
            switch (t.Status)
            {
                case Running:
                    return ClockFormat.Format(SecondsUntil(t.EndsAt, nowUtc)) + " kaldı";
                case Scheduled:
                    return t.StartsAt is DateTime s ? "Başlıyor " + LocalClock(s, offsetMinutes) : "Başlıyor";
                case Finished:
                    return "Turnuva bitti";
                case Cancelled:
                    return "İptal edildi";
                default:
                    return "";
            }
        }

        /// <summary>Liste satiri / sayfa basligi: "3+2 · 30 dk · 12 oyuncu · 18:42 kaldı" (secili dilde).</summary>
        public static string InfoLine(TournamentSummary t, DateTime nowUtc, int offsetMinutes, Lang lang)
        {
            if (t == null)
                return "";
            return string.Join(" · ",
                "3+2",
                Loc.T(t.DurationMinutes + " dk", lang),
                Loc.T(t.Players + " oyuncu", lang),
                Loc.T(StatusText(t, nowUtc, offsetMinutes), lang));
        }

        /// <summary>Hedefe kalan tam saniye (yukari yuvarlanir, 0'in altina inmez; hedef yoksa 0).</summary>
        public static int SecondsUntil(DateTime? target, DateTime nowUtc)
        {
            if (target == null)
                return 0;
            double left = (target.Value - nowUtc).TotalSeconds;
            return left <= 0 ? 0 : (int)Math.Ceiling(left);
        }
    }
}
