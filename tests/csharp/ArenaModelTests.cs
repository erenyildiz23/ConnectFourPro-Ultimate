// Arena turnuvasi veri modeli (Game/ArenaModel.cs): REST/soket yuklerinin ayristirilmasi,
// turnuva adi ve ISO zamanlari.
using System;
using ConnectFourPro.Game;
using ConnectFourPro.Net;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class ArenaModelTests
    {
        internal const string Standings =
            "{\"tournament_id\":5,\"standings\":[" +
            "{\"rank\":1,\"username\":\"veli\",\"score\":8,\"games_played\":3,\"streak\":3,\"on_fire\":true,\"paused\":false,\"recent\":\"WWW\"}," +
            "{\"rank\":2,\"username\":\"Ali\",\"score\":2,\"games_played\":4,\"streak\":0,\"on_fire\":false,\"paused\":true,\"recent\":\"LWLDL\"}]}";

        internal const string Tournament5 =
            "{\"id\":5,\"creator\":\"Ali\",\"duration_minutes\":30,\"starts_at\":\"2026-11-19T12:00:00+00:00\"," +
            "\"ends_at\":\"2026-11-19T12:30:00+00:00\",\"status\":\"running\",\"players\":2}";

        [Test]
        public void ParseStandingsReadsEveryField()
        {
            var rows = ArenaModel.ParseStandings(JsonObject.ParseObject(Standings));
            Assert.That(rows.Count, Is.EqualTo(2));
            var top = rows[0];
            Assert.That(top.Rank, Is.EqualTo(1));
            Assert.That(top.Username, Is.EqualTo("veli"));
            Assert.That(top.Score, Is.EqualTo(8));
            Assert.That(top.GamesPlayed, Is.EqualTo(3));
            Assert.That(top.Streak, Is.EqualTo(3));
            Assert.That(top.OnFire, Is.True);
            Assert.That(top.Paused, Is.False);
            Assert.That(top.Recent, Is.EqualTo("WWW"));
            Assert.That(rows[1].Username, Is.EqualTo("Ali"));
            Assert.That(rows[1].Paused, Is.True);
            Assert.That(rows[1].Recent, Is.EqualTo("LWLDL"));
        }

        [Test]
        public void ParseStandingsToleratesMissingOrBrokenData()
        {
            Assert.That(ArenaModel.ParseStandings(JsonObject.ParseObject("{}")), Is.Empty);
            Assert.That(ArenaModel.ParseStandings(JsonObject.ParseObject("{\"standings\":5}")), Is.Empty);
            Assert.That(ArenaModel.ParseStandings(null), Is.Empty);
            var rows = ArenaModel.ParseStandings(JsonObject.ParseObject("{\"standings\":[{\"username\":\"x\"}]}"));
            Assert.That(rows.Count, Is.EqualTo(1));
            Assert.That(rows[0].Recent, Is.EqualTo(""));
            Assert.That(rows[0].Score, Is.EqualTo(0));
        }

        [Test]
        public void DisplayNameUsesFixedPatternPerLanguage()
        {
            Assert.That(ArenaModel.DisplayName("Ali", Lang.Tr), Is.EqualTo("Ali'nın Arenası"));
            Assert.That(ArenaModel.DisplayName("Ali", Lang.En), Is.EqualTo("Ali's Arena"));
            Assert.That(ArenaModel.DisplayName("veli", Lang.Tr), Is.EqualTo("veli'nın Arenası"), "ek unlu uyumu yapilmaz");
        }

        [Test]
        public void TournamentSummaryParsesFieldsAndUtcTimes()
        {
            var t = TournamentSummary.From(JsonObject.ParseObject(Tournament5));
            Assert.That(t.Id, Is.EqualTo(5));
            Assert.That(t.Creator, Is.EqualTo("Ali"));
            Assert.That(t.DurationMinutes, Is.EqualTo(30));
            Assert.That(t.Status, Is.EqualTo("running"));
            Assert.That(t.Players, Is.EqualTo(2));
            Assert.That(t.StartsAt, Is.EqualTo(new DateTime(2026, 11, 19, 12, 0, 0, DateTimeKind.Utc)));
            Assert.That(t.EndsAt, Is.EqualTo(new DateTime(2026, 11, 19, 12, 30, 0, DateTimeKind.Utc)));
            Assert.That(t.EndsAt.Value.Kind, Is.EqualTo(DateTimeKind.Utc));
        }

        [TestCase("2026-11-19T15:30:00+03:00", 12)]
        [TestCase("2026-11-19T12:30:00Z", 12)]
        [TestCase("2026-11-19T12:30:00.123456+00:00", 12)]
        [TestCase("2026-11-19T12:30:00", 12)]
        public void IsoTimesAreConvertedToUtc(string iso, int hour)
        {
            DateTime? t = ArenaModel.ParseUtc(iso);
            Assert.That(t, Is.Not.Null);
            Assert.That(t.Value.Kind, Is.EqualTo(DateTimeKind.Utc));
            Assert.That(t.Value.Hour, Is.EqualTo(hour));
            Assert.That(t.Value.Minute, Is.EqualTo(30));
        }

        [TestCase(null)]
        [TestCase("")]
        [TestCase("dun")]
        public void BadIsoTimeIsNull(string iso) => Assert.That(ArenaModel.ParseUtc(iso), Is.Null);

        [Test]
        public void ListParsesTournamentsAndToleratesOldServer()
        {
            var list = ArenaModel.ParseTournaments(JsonObject.ParseObject("{\"tournaments\":[" + Tournament5 + "]}"));
            Assert.That(list.Count, Is.EqualTo(1));
            Assert.That(list[0].Id, Is.EqualTo(5));
            Assert.That(ArenaModel.ParseTournaments(JsonObject.ParseObject("{}")), Is.Empty);
            Assert.That(ArenaModel.ParseTournaments(null), Is.Empty);
        }

        [Test]
        public void SecondsUntilIsNeverNegative()
        {
            var end = new DateTime(2026, 11, 19, 12, 30, 0, DateTimeKind.Utc);
            Assert.That(ArenaModel.SecondsUntil(end, end.AddSeconds(-90.5)), Is.EqualTo(91));
            Assert.That(ArenaModel.SecondsUntil(end, end.AddSeconds(5)), Is.EqualTo(0));
            Assert.That(ArenaModel.SecondsUntil(null, end), Is.EqualTo(0));
        }
    }
}
