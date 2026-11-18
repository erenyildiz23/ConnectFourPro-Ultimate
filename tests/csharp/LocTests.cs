// Arayuz dili tablosu ve ceviri (Game/Loc.cs).
using System.Linq;
using System.Text.RegularExpressions;
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    [NonParallelizable]
    public class LocTests
    {
        [TearDown]
        public void ResetLang() => Loc.Current = Lang.Tr;

        [Test]
        public void EveryEntryHasNonEmptyEnglish()
        {
            foreach (var kv in Loc.Table)
                Assert.That(kv.Value, Is.Not.Null.And.Not.Empty, kv.Key);
        }

        [Test]
        public void TemplatesUseSamePlaceholdersInBothLanguages()
        {
            var ph = new Regex(@"\{\d+\}");
            foreach (var kv in Loc.Table)
            {
                var tr = ph.Matches(kv.Key).Select(m => m.Value).OrderBy(x => x);
                var en = ph.Matches(kv.Value).Select(m => m.Value).OrderBy(x => x);
                Assert.That(en, Is.EqualTo(tr), kv.Key);
            }
        }

        [Test]
        public void EveryServerCodeMessageIsTranslated()
        {
            foreach (var kv in Loc.ServerCodes)
                Assert.That(Loc.Table.ContainsKey(kv.Value), kv.Key);
        }

        [Test]
        public void TurkishIsIdentity()
        {
            Loc.Current = Lang.Tr;
            Assert.That(Loc.T("Senin sıran!"), Is.EqualTo("Senin sıran!"));
            Assert.That(Loc.T("Hoş geldin Ali!"), Is.EqualTo("Hoş geldin Ali!"));
        }

        [TestCase("Senin sıran!", "Your turn!")]
        [TestCase("Hoş geldin Ali!", "Welcome Ali!")]
        [TestCase("Kayıt başarılı! Hoş geldin Ali!", "Signed up! Welcome Ali!")]
        [TestCase("Hata: Oda bulunamadi", "Error: Room not found")]
        [TestCase("Oyuna geri dönüldü. Rakibin sırası...", "Back in the game. Opponent's turn...")]
        [TestCase("Kazandın!  ELO +12 (1212)", "You won!  ELO +12 (1212)")]
        [TestCase("Kırmızı kazandı! (süre doldu)", "Red wins! (time ran out)")]
        [TestCase("AI - Kolay", "AI - Easy")]
        [TestCase("Ali kazandı!", "Ali wins!")]
        [TestCase("3. Ali  -  ELO: 1250  (G:4 M:2)", "3. Ali  -  ELO: 1250  (W:4 L:2)")]
        [TestCase("Sen: %87   Rakip: %64", "You: 87%   Opponent: 64%")]
        [TestCase("(Sen)  ELO: 1200", "(You)  ELO: 1200")]
        [TestCase("12 sn", "12s")]
        [TestCase("KAYBETTİN (hükmen)", "YOU LOST (forfeit)")]
        [TestCase("Rakibin bağlantısı koptu! 30 sn içinde dönmezse kazanırsın.",
                  "Your opponent disconnected! You win if they don't return within 30s.")]
        [TestCase("İzle", "Watch")]
        [TestCase("Tekrarı izle", "Watch replay")]
        [TestCase("Hamle 3 / 7", "Move 3 / 7")]
        [TestCase("MAÇ TEKRARI", "MATCH REPLAY")]
        [TestCase("veli kazandı! (hükmen)", "veli wins! (forfeit)")]
        [TestCase("Misafir_123456", "Misafir_123456")]
        [TestCase("", "")]
        public void TranslatesToEnglish(string tr, string en)
        {
            Loc.Current = Lang.En;
            Assert.That(Loc.T(tr), Is.EqualTo(en));
        }

        [Test]
        public void ChangedFiresOnlyOnRealChange()
        {
            int calls = 0;
            void Handler(Lang l) => calls++;
            Loc.Changed += Handler;
            try
            {
                Loc.Current = Lang.Tr;
                Loc.Toggle();
                Loc.Toggle();
                Assert.That(calls, Is.EqualTo(2));
                Assert.That(Loc.Current, Is.EqualTo(Lang.Tr));
            }
            finally { Loc.Changed -= Handler; }
        }

        [TestCase("tr", false, Lang.Tr)]
        [TestCase("en", true, Lang.En)]
        [TestCase("", true, Lang.Tr)]
        [TestCase("", false, Lang.En)]
        [TestCase("xx", false, Lang.En)]
        public void InitialLanguage(string saved, bool systemTurkish, Lang expected) =>
            Assert.That(Loc.Initial(saved, systemTurkish), Is.EqualTo(expected));

        [Test]
        public void ServerErrorPrefersKnownCode()
        {
            Assert.That(Loc.ServerError("room_not_found", "whatever"), Is.EqualTo("Oda bulunamadi"));
            Assert.That(Loc.ServerError("", "Oda bulunamadi"), Is.EqualTo("Oda bulunamadi"));
            Assert.That(Loc.ServerError("unknown_code", "Yeni mesaj"), Is.EqualTo("Yeni mesaj"));
        }

        [Test]
        public void ToggleLabelNamesTheOtherLanguage()
        {
            Loc.Current = Lang.Tr;
            Assert.That(Loc.ToggleLabel, Is.EqualTo("English"));
            Loc.Current = Lang.En;
            Assert.That(Loc.ToggleLabel, Is.EqualTo("Türkçe"));
        }
    }
}
