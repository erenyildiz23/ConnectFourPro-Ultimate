// Turnuva ekranlarinda gosterilecek satirlarin secimi (Game/ArenaModel.cs): liste sirasi,
// puan durumunda kendi satirinin her zaman gorunmesi ve uzun adlarin kisaltilmasi.
using System;
using System.Collections.Generic;
using System.Linq;
using ConnectFourPro.Game;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class ArenaListTests
    {
        private static readonly DateTime Now = new DateTime(2026, 11, 19, 12, 0, 0, DateTimeKind.Utc);

        private static TournamentSummary T(int id, string status, int startMin, int endMin) => new TournamentSummary
        {
            Id = id, Creator = "u" + id, DurationMinutes = 15, Status = status,
            StartsAt = Now.AddMinutes(startMin), EndsAt = Now.AddMinutes(endMin),
        };

        [Test]
        public void ListOrderRunningThenScheduledThenNewestFinished()
        {
            // Sunucu sirasi: starts_at artan (eski bitenler once)
            var server = new List<TournamentSummary>
            {
                T(1, ArenaModel.Finished, -6000, -5985),
                T(2, ArenaModel.Finished, -100, -85),
                T(3, ArenaModel.Running, -10, 5),
                T(4, ArenaModel.Running, -5, 25),
                T(5, ArenaModel.Scheduled, 30, 45),
                T(6, ArenaModel.Scheduled, 10, 25),
                T(7, ArenaModel.Cancelled, -50, -35),
            };
            var sorted = ArenaModel.SortForList(server);
            Assert.That(sorted.Select(t => t.Id), Is.EqualTo(new[] { 3, 4, 6, 5, 2, 1, 7 }));
            Assert.That(server[0].Id, Is.EqualTo(1), "girdi listesi degismez");
        }

        [Test]
        public void ListOrderKeepsJoinableInFirstRows()
        {
            var server = new List<TournamentSummary>();
            for (int i = 0; i < 10; i++)
                server.Add(T(i + 1, ArenaModel.Finished, -9000 + i * 100, -8985 + i * 100));
            server.Add(T(50, ArenaModel.Scheduled, 60, 75));
            var visible = ArenaModel.SortForList(server).Take(8).ToList();
            Assert.That(visible[0].Id, Is.EqualTo(50));
            Assert.That(visible[1].Id, Is.EqualTo(10), "en yeni biten once");
        }

        [Test]
        public void ListOrderToleratesNullAndMissingTimes()
        {
            Assert.That(ArenaModel.SortForList(null), Is.Empty);
            var a = T(1, ArenaModel.Scheduled, 0, 15);
            a.StartsAt = null;
            var b = T(2, ArenaModel.Scheduled, 5, 20);
            Assert.That(ArenaModel.SortForList(new List<TournamentSummary> { b, a }).Select(t => t.Id),
                        Is.EqualTo(new[] { 2, 1 }), "zamani bilinmeyen sona");
        }

        private static List<StandingRow> Rows(int n) =>
            Enumerable.Range(1, n).Select(i => new StandingRow { Rank = i, Username = "p" + i }).ToList();

        [Test]
        public void StandingsShowOwnRowInLastSlotWhenBelowTheFold()
        {
            var rows = ArenaModel.VisibleStandings(Rows(15), "p12", 9);
            Assert.That(rows.Count, Is.EqualTo(9));
            Assert.That(rows.Take(8).Select(r => r.Rank), Is.EqualTo(Enumerable.Range(1, 8)));
            Assert.That(rows[8].Username, Is.EqualTo("p12"));
            Assert.That(rows[8].Rank, Is.EqualTo(12), "gercek sira korunur");
        }

        [TestCase("p3")]
        [TestCase("p9")]
        [TestCase("yok")]
        [TestCase(null)]
        public void StandingsUnchangedWhenOwnRowVisibleOrAbsent(string me)
        {
            var rows = ArenaModel.VisibleStandings(Rows(15), me, 9);
            Assert.That(rows.Select(r => r.Rank), Is.EqualTo(Enumerable.Range(1, 9)));
        }

        [Test]
        public void StandingsShorterThanSlots()
        {
            Assert.That(ArenaModel.VisibleStandings(Rows(3), "p3", 9).Count, Is.EqualTo(3));
            Assert.That(ArenaModel.VisibleStandings(null, "p3", 9), Is.Empty);
        }

        [Test]
        public void ClipShortensLongNames()
        {
            Assert.That(ArenaModel.Clip("kisa", 16), Is.EqualTo("kisa"));
            Assert.That(ArenaModel.Clip("abcdefghijklmnop", 16), Is.EqualTo("abcdefghijklmnop"));
            Assert.That(ArenaModel.Clip("abcdefghijklmnopqrst", 16), Is.EqualTo("abcdefghijklm..."));
            Assert.That(ArenaModel.Clip("abcdefghijklmnopqrst", 16).Length, Is.EqualTo(16));
            Assert.That(ArenaModel.Clip(null, 16), Is.EqualTo(""));
        }
    }
}
