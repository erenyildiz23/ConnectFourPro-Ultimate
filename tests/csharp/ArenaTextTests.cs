// Turnuva ekranlarinin yazilari (Game/ArenaModel.cs): durum, bilgi satiri, yerel saat ve
// turnuva acma formundaki baslangic secenekleri.
using System;
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    [NonParallelizable]
    public class ArenaTextTests
    {
        private static readonly DateTime Now = new DateTime(2026, 11, 19, 12, 0, 0, DateTimeKind.Utc);

        [TearDown]
        public void ResetLang() => Loc.Current = Lang.Tr;

        private static TournamentSummary T(string status, int players = 2, int duration = 30)
        {
            return new TournamentSummary
            {
                Id = 5, Creator = "Ali", DurationMinutes = duration, Status = status, Players = players,
                StartsAt = Now.AddMinutes(90), EndsAt = Now.AddMinutes(18).AddSeconds(42),
            };
        }

        [Test]
        public void LocalClockAppliesOffset()
        {
            Assert.That(ArenaModel.LocalClock(Now, 0), Is.EqualTo("12:00"));
            Assert.That(ArenaModel.LocalClock(Now, 180), Is.EqualTo("15:00"));
            Assert.That(ArenaModel.LocalClock(Now.AddMinutes(5), -300), Is.EqualTo("07:05"));
            Assert.That(ArenaModel.LocalClock(Now.AddHours(13), 0), Is.EqualTo("01:00"), "gece yarisini gecer");
        }

        [Test]
        public void StatusTextPerStatus()
        {
            Assert.That(ArenaModel.StatusText(T(ArenaModel.Running), Now, 0), Is.EqualTo("18:42 kaldı"));
            Assert.That(ArenaModel.StatusText(T(ArenaModel.Scheduled), Now, 180), Is.EqualTo("Başlıyor 16:30"));
            Assert.That(ArenaModel.StatusText(T(ArenaModel.Finished), Now, 0), Is.EqualTo("Turnuva bitti"));
            Assert.That(ArenaModel.StatusText(T(ArenaModel.Cancelled), Now, 0), Is.EqualTo("İptal edildi"));
            Assert.That(ArenaModel.StatusText(null, Now, 0), Is.EqualTo(""));
            var past = T(ArenaModel.Running);
            past.EndsAt = Now.AddMinutes(-1);
            Assert.That(ArenaModel.StatusText(past, Now, 0), Is.EqualTo("0:00 kaldı"), "eksiye inmez");
            var noStart = T(ArenaModel.Scheduled);
            noStart.StartsAt = null;
            Assert.That(ArenaModel.StatusText(noStart, Now, 0), Is.EqualTo("Başlıyor"));
        }

        [Test]
        public void InfoLineTurkishAndEnglish()
        {
            var t = T(ArenaModel.Running, players: 12);
            Assert.That(ArenaModel.InfoLine(t, Now, 0, Lang.Tr), Is.EqualTo("3+2 · 30 dk · 12 oyuncu · 18:42 kaldı"));
            Assert.That(ArenaModel.InfoLine(t, Now, 0, Lang.En), Is.EqualTo("3+2 · 30 min · 12 players · 18:42 left"));
            var s = T(ArenaModel.Scheduled, players: 1, duration: 15);
            Assert.That(ArenaModel.InfoLine(s, Now, 0, Lang.Tr), Is.EqualTo("3+2 · 15 dk · 1 oyuncu · Başlıyor 13:30"));
            Assert.That(ArenaModel.InfoLine(s, Now, 0, Lang.En), Is.EqualTo("3+2 · 15 min · 1 player · Starts 13:30"));
            var f = T(ArenaModel.Finished, players: 4, duration: 60);
            Assert.That(ArenaModel.InfoLine(f, Now, 0, Lang.En), Is.EqualTo("3+2 · 60 min · 4 players · Tournament over"));
            Assert.That(ArenaModel.InfoLine(null, Now, 0, Lang.Tr), Is.EqualTo(""));
        }

        [Test]
        public void StartOptionsCoverNowToTwentyFourHours()
        {
            var o = ArenaModel.StartOptions;
            Assert.That(o[0], Is.EqualTo(0), "ilk secenek: hemen");
            Assert.That(o[o.Length - 1], Is.EqualTo(ArenaModel.MaxStartInMinutes));
            for (int i = 1; i < o.Length; i++)
                Assert.That(o[i], Is.GreaterThan(o[i - 1]));
            foreach (int m in o)
                Assert.That(ArenaModel.IsValidStartIn(m), Is.True, m.ToString());
        }

        [Test]
        public void StepStartInMovesBetweenOptionsAndClamps()
        {
            Assert.That(ArenaModel.StepStartIn(0, -1), Is.EqualTo(0));
            Assert.That(ArenaModel.StepStartIn(0, 1), Is.EqualTo(15));
            Assert.That(ArenaModel.StepStartIn(15, -1), Is.EqualTo(0));
            Assert.That(ArenaModel.StepStartIn(ArenaModel.MaxStartInMinutes, 1), Is.EqualTo(ArenaModel.MaxStartInMinutes));
            Assert.That(ArenaModel.StepStartIn(50, 1), Is.EqualTo(60), "secenek disi deger bir sonrakine gider");
            Assert.That(ArenaModel.StepStartIn(50, -1), Is.EqualTo(45));
        }

        [TestCase("Turnuvalar", "Tournaments")]
        [TestCase("+ Turnuva Aç", "+ Create Tournament")]
        [TestCase("Katıl", "Join")]
        [TestCase("Duraklat", "Pause")]
        [TestCase("Devam", "Resume")]
        [TestCase("Hemen", "Now")]
        [TestCase("Başlıyor", "Starts")]
        [TestCase("kaldı", "left")]
        [TestCase("oyuncu", "players")]
        [TestCase("Sıradaki oyun", "Next game")]
        [TestCase("Turnuva bitti", "Tournament over")]
        [TestCase("İptal edildi", "Cancelled")]
        [TestCase("Seri", "Streak")]
        [TestCase("Başlıyor 21:00", "Starts 21:00")]
        [TestCase("18:42 kaldı", "18:42 left")]
        [TestCase("12 oyuncu", "12 players")]
        [TestCase("1 oyuncu", "1 player")]
        [TestCase("30 dk", "30 min")]
        [TestCase("Hata: Turnuva bitti", "Error: Tournament over")]
        [TestCase("TURNUVALAR", "TOURNAMENTS")]
        [TestCase("Turnuva Aç", "Create Tournament")]
        [TestCase("Süre", "Duration")]
        [TestCase("Başlangıç", "Start")]
        [TestCase("Henüz turnuva yok", "No tournaments yet")]
        [TestCase("Henüz katılan yok", "No players yet")]
        [TestCase("Turnuva yüklenemedi", "Could not load the tournament")]
        [TestCase("Oyuncu", "Player")]
        [TestCase("Puan", "Score")]
        [TestCase("Son 5", "Last 5")]
        [TestCase("Duraklatıldı", "Paused")]
        public void ArenaStringsTranslate(string tr, string en)
        {
            Loc.Current = Lang.En;
            Assert.That(Loc.T(tr), Is.EqualTo(en));
        }
    }
}
