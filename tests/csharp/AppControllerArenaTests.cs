// Arena turnuvasi istemcisi: protokol (game_over.arena), GameSocket arena_* olaylari ve
// AppController turnuva durumu (liste, sayfa, acma, katilma, duraklatma, turnuva oyunu,
// siradaki oyun, yeniden baglanma, eski sunucu).
using System;
using System.Collections.Generic;
using ConnectFourPro.Core;
using ConnectFourPro.Game;
using ConnectFourPro.Net;
using NUnit.Framework;

namespace ConnectFourPro.Tests
{
    public class ArenaProtocolTests
    {
        [Test]
        public void GameOverArenaPointsAreKeyedByUsername()
        {
            var json = ServerMessages.WithFields(ServerMessages.GameOver(1, eloP1: 8, eloP2: -8),
                new Dictionary<string, object>
                {
                    ["arena"] = new Dictionary<string, object>
                    {
                        ["tournament_id"] = 5,
                        ["points"] = new Dictionary<string, object> { ["Ali"] = 2, ["veli"] = 0 },
                    },
                });
            var info = GameOverInfo.From(JsonObject.ParseObject(json));
            Assert.That(info.ArenaTournamentId, Is.EqualTo(5));
            Assert.That(info.ArenaPointsFor("Ali"), Is.EqualTo(2));
            Assert.That(info.ArenaPointsFor("veli"), Is.EqualTo(0));
            Assert.That(info.ArenaPointsFor("baska"), Is.Null);
        }

        [Test]
        public void NormalGameOverHasNoArenaPoints()
        {
            var info = GameOverInfo.From(JsonObject.ParseObject(ServerMessages.GameOver(1)));
            Assert.That(info.ArenaTournamentId, Is.Null);
            Assert.That(info.ArenaPointsFor("Ali"), Is.Null);
        }

        [Test]
        public void ArenaEventsAreKnownServerEvents() =>
            Assert.That(SocketEvents.ServerEvents,
                        Is.SupersetOf(new[] { "arena_created", "arena_joined", "arena_standings", "arena_state" }));
    }

    public class GameSocketArenaTests
    {
        private const string Url = "http://test";
        private FakeTransport _transport;
        private GameSocket _socket;

        [SetUp]
        public void SetUp()
        {
            UnityEngine.UnityStubs.Reset();
            _transport = new FakeTransport();
            _socket = new GameSocket(_transport, Url);
        }

        [Test]
        public void CreateArenaCarriesIdentityAndValues()
        {
            _socket.SetIdentity("Ali", "tok-1");
            _socket.CreateArena(30, 120);
            Assert.That(_transport.ConnectUrls, Is.EqualTo(new[] { Url }), "bagli degilken once baglanir");
            _transport.RaiseConnected();
            var data = _transport.EmittedOf("arena_create")[0];
            Assert.That(data.GetString("user_id"), Is.EqualTo("Ali"));
            Assert.That(data.GetString("token"), Is.EqualTo("tok-1"));
            Assert.That(data.GetInt("duration"), Is.EqualTo(30));
            Assert.That(data.GetInt("start_in_minutes"), Is.EqualTo(120));
        }

        [Test]
        public void JoinWatchPauseResumeCarryTournamentId()
        {
            _socket.SetIdentity("Ali", "tok-1");
            _transport.RaiseConnected();
            _socket.WatchArena(5);
            _socket.JoinArena(5);
            _socket.PauseArena(5);
            _socket.ResumeArena(5);
            foreach (string evt in new[] { "arena_watch", "arena_join", "arena_pause", "arena_resume" })
            {
                var sent = _transport.EmittedOf(evt);
                Assert.That(sent.Count, Is.EqualTo(1), evt);
                Assert.That(sent[0].GetInt("tournament_id"), Is.EqualTo(5), evt);
            }
            Assert.That(_transport.EmittedOf("arena_join")[0].GetString("token"), Is.EqualTo("tok-1"));
            Assert.That(_transport.EmittedOf("arena_pause")[0].GetString("user_id"), Is.EqualTo("Ali"));
        }

        [Test]
        public void ReconnectRejoinsArenaWhenNotPaused()
        {
            _socket.SetIdentity("Ali", "tok-1");
            _socket.JoinArena(5);
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1), "ilk baglantida tek istek");

            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1), "once taze siralama beklenir");
            var watch = _transport.EmittedOf("arena_watch");
            Assert.That(watch.Count, Is.EqualTo(1), "yeniden baglaninca once izlenir");
            Assert.That(watch[0].GetInt("tournament_id"), Is.EqualTo(5));

            // Baska turnuvanin siralamasi karar vermez
            _transport.Receive("arena_standings", "{\"tournament_id\":9,\"standings\":[]}");
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1));

            _transport.Receive("arena_standings",
                "{\"tournament_id\":5,\"standings\":[{\"username\":\"Ali\",\"paused\":false}]}");
            var joins = _transport.EmittedOf("arena_join");
            Assert.That(joins.Count, Is.EqualTo(2));
            Assert.That(joins[1].GetInt("tournament_id"), Is.EqualTo(5));
            Assert.That(joins[1].GetString("token"), Is.EqualTo("tok-1"));

            // Sonraki siralamalar yeniden istek gondermez
            _transport.Receive("arena_standings",
                "{\"tournament_id\":5,\"standings\":[{\"username\":\"Ali\",\"paused\":false}]}");
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(2));
        }

        [Test]
        public void ReconnectKeepsServerSidePauseAppliedWhileOffline()
        {
            _socket.SetIdentity("Ali", "tok-1");
            _socket.JoinArena(5);
            _transport.RaiseConnected();
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            // Kopukken sunucu duraklatti (ilk hamle iptali): arena_join duraklatmayi kaldirmamali
            _transport.Receive("arena_standings",
                "{\"tournament_id\":5,\"standings\":[{\"username\":\"Ali\",\"paused\":true}]}");
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1));
            Assert.That(_socket.ArenaPaused, Is.True);
        }

        [Test]
        public void ReconnectDoesNotRejoinPausedOrForgottenArena()
        {
            _socket.SetIdentity("Ali", "tok-1");
            _socket.JoinArena(5);
            _transport.RaiseConnected();
            _socket.PauseArena(5);
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1), "duraklatan oyuncu kuyruga sokulmaz");

            _socket.ResumeArena(5);
            _socket.ForgetArena();
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1), "biten turnuvaya geri katilinmaz");
        }

        [Test]
        public void ReconnectRewatchesWatchedArena()
        {
            _socket.WatchArena(7);
            _transport.RaiseConnected();
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            var watches = _transport.EmittedOf("arena_watch");
            Assert.That(watches.Count, Is.EqualTo(2), "misafir izleyici de canli siralamaya doner");
            Assert.That(watches[1].GetInt("tournament_id"), Is.EqualTo(7));
            Assert.That(_transport.EmittedOf("arena_join"), Is.Empty);
        }
    }

    public partial class AppControllerTests
    {
        private static readonly DateTime ArenaNow = new DateTime(2026, 11, 19, 12, 10, 0, DateTimeKind.Utc);
        private const string TournamentList = "{\"tournaments\":[" + ArenaModelTests.Tournament5 + "]}";
        private const string TournamentDetail =
            "{\"tournament\":" + ArenaModelTests.Tournament5 + ",\"standings\":[" +
            "{\"rank\":1,\"username\":\"veli\",\"score\":2,\"games_played\":1,\"streak\":1,\"on_fire\":false,\"paused\":false,\"recent\":\"W\"}]}";
        private const string StandingsAliActive =
            "{\"tournament_id\":5,\"standings\":[" +
            "{\"rank\":1,\"username\":\"veli\",\"score\":2,\"games_played\":1,\"streak\":1,\"on_fire\":false,\"paused\":false,\"recent\":\"W\"}," +
            "{\"rank\":2,\"username\":\"Ali\",\"score\":0,\"games_played\":0,\"streak\":0,\"on_fire\":false,\"paused\":false,\"recent\":\"\"}]}";
        private const string StandingsAliPaused =
            "{\"tournament_id\":5,\"standings\":[" +
            "{\"rank\":1,\"username\":\"Ali\",\"score\":2,\"games_played\":1,\"streak\":1,\"on_fire\":false,\"paused\":true,\"recent\":\"W\"}]}";
        private const string ArenaJoinedP1 =
            "{\"room_id\":\"AR001\",\"player_piece\":1,\"role\":\"player\",\"opponent_info\":{\"username\":\"veli\",\"rating\":1250}," +
            "\"rejoin_token\":\"seat-a\",\"quick\":true,\"tournament_id\":5,\"time_control\":\"3+2\",\"clock_p1\":180,\"clock_p2\":180,\"clock_running\":1}";
        private const string ArenaStart =
            "{\"msg\":\"Oyun Basladi!\",\"opponent_name\":\"veli\",\"opponent_elo\":1250,\"tournament_id\":5," +
            "\"time_control\":\"3+2\",\"clock_p1\":180,\"clock_p2\":180,\"clock_running\":1}";

        // Sure bitimiyle hukmen sonuc: bos tahtada da oyun biter (hukmen galibiyet = galibiyet)
        private static string ArenaGameOver(int? winner, int myPoints, int theirPoints) =>
            ServerMessages.WithFields(ServerMessages.GameOver(winner, "forfeit", "timeout", eloP1: 8, eloP2: -8, ratingP1: 1345, ratingP2: 1242),
                new Dictionary<string, object>
                {
                    ["arena"] = new Dictionary<string, object>
                    {
                        ["tournament_id"] = 5,
                        ["points"] = new Dictionary<string, object> { ["veli"] = theirPoints, ["Ali"] = myPoints },
                    },
                });

        private ApiClient.Call CallOf(string method)
        {
            for (int i = _api.Calls.Count - 1; i >= 0; i--)
                if (_api.Calls[i].Method == method)
                    return _api.Calls[i];
            return null;
        }

        /// <summary>Kayitli Ali turnuva 5'in sayfasini acar (liste ve ayrinti yanitlanmis).</summary>
        private void OpenTournament5AsAli()
        {
            LoginAsAli();
            _app.UtcNow = () => ArenaNow;
            _app.OpenTournaments();
            CallOf("Tournaments").Respond(200, TournamentList);
            _app.OpenTournament(5);
            CallOf("Tournament").Respond(200, TournamentDetail);
            _transport.RaiseConnected();
        }

        private void JoinTournament5AndStartGame()
        {
            OpenTournament5AsAli();
            _app.JoinTournament();
            _transport.Receive("arena_joined", "{\"tournament_id\":5}");
            _transport.Receive("arena_standings", StandingsAliActive);
            _transport.Receive("game_joined", ArenaJoinedP1);
            _transport.Receive("game_start", ArenaStart);
        }

        // ---------------------------------------------------------------------
        // Liste ve sayfa
        // ---------------------------------------------------------------------

        [Test]
        public void OpenTournamentsFetchesList()
        {
            LoginAsAli();
            _app.OpenTournaments();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournaments));
            Assert.That(_app.TournamentsLoading, Is.True);
            CallOf("Tournaments").Respond(200, TournamentList);
            Assert.That(_app.TournamentsLoading, Is.False);
            Assert.That(_app.TournamentsError, Is.False);
            Assert.That(_app.Tournaments.Count, Is.EqualTo(1));
            Assert.That(_app.Tournaments[0].Creator, Is.EqualTo("Ali"));
            Assert.That(_transport.ConnectUrls, Is.Empty, "liste icin soket acilmaz");
        }

        [TestCase(404)]
        [TestCase(0)]
        public void OldServerListFailureShowsErrorWithoutCrash(int status)
        {
            _app.GuestLogin();
            _app.OpenTournaments();
            Assert.DoesNotThrow(() => CallOf("Tournaments").Respond(status, status == 404 ? "<html>Not Found</html>" : null));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournaments));
            Assert.That(_app.TournamentsError, Is.True);
            Assert.That(_app.Tournaments, Is.Empty);
        }

        [Test]
        public void OpenTournamentLoadsDetailAndWatchesStandings()
        {
            OpenTournament5AsAli();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
            Assert.That(CallOf("Tournament").Username, Is.EqualTo("5"));
            Assert.That(_app.CurrentTournament.Id, Is.EqualTo(5));
            Assert.That(_app.CurrentTournament.Status, Is.EqualTo("running"));
            Assert.That(_app.Standings.Count, Is.EqualTo(1));
            var watch = _transport.EmittedOf("arena_watch");
            Assert.That(watch.Count, Is.EqualTo(1));
            Assert.That(watch[0].GetInt("tournament_id"), Is.EqualTo(5));

            int version = _app.StandingsVersion;
            _transport.Receive("arena_standings", StandingsAliActive);
            Assert.That(_app.Standings.Count, Is.EqualTo(2));
            Assert.That(_app.Standings[1].Username, Is.EqualTo("Ali"));
            Assert.That(_app.StandingsVersion, Is.GreaterThan(version));
            Assert.That(_app.IsArenaMember, Is.True);

            // Baska turnuvanin siralamasi bu sayfayi degistirmez
            _transport.Receive("arena_standings", "{\"tournament_id\":9,\"standings\":[]}");
            Assert.That(_app.Standings.Count, Is.EqualTo(2));
        }

        [Test]
        public void UnknownTournamentShowsErrorWithoutCrash()
        {
            LoginAsAli();
            _app.OpenTournament(77);
            Assert.DoesNotThrow(() => CallOf("Tournament").Respond(404, "{\"error\":\"not found\"}"));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
            Assert.That(_app.TournamentError, Is.True);
            Assert.That(_app.CurrentTournament, Is.Null);
            Assert.That(_app.CanJoinTournament, Is.False);
        }

        [Test]
        public void StaleDetailResponseIsIgnored()
        {
            LoginAsAli();
            _app.OpenTournament(5);
            var stale = CallOf("Tournament");
            _app.OpenTournament(6);
            stale.Respond(200, TournamentDetail);
            Assert.That(_app.CurrentTournament, Is.Null, "eski sayfanin yaniti yeni sayfaya yazilmaz");
        }

        [Test]
        public void BackFromTournamentGoesToListThenMenu()
        {
            OpenTournament5AsAli();
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournaments));
            Assert.That(_transport.DisconnectCalls, Is.EqualTo(0), "listeye donmek turnuva baglantisini kesmez");
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
        }

        [Test]
        public void ArenaSecondsLeftComesFromEndsAtAndNeverNegative()
        {
            OpenTournament5AsAli();
            Assert.That(_app.ArenaSecondsLeft, Is.EqualTo(20 * 60));
            _app.UtcNow = () => ArenaNow.AddMinutes(25);
            Assert.That(_app.ArenaSecondsLeft, Is.EqualTo(0));
        }

        // ---------------------------------------------------------------------
        // Misafir
        // ---------------------------------------------------------------------

        [Test]
        public void GuestWatchesButCannotCreateOrJoin()
        {
            _app.GuestLogin();
            _app.OpenTournaments();
            CallOf("Tournaments").Respond(200, TournamentList);
            Assert.That(_app.CanCreateTournament, Is.False);
            _app.CreateTournament(30, 0);
            Assert.That(_transport.ConnectUrls, Is.Empty);

            _app.OpenTournament(5);
            CallOf("Tournament").Respond(200, TournamentDetail);
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("arena_watch").Count, Is.EqualTo(1), "misafir siralamayi izler");
            Assert.That(_app.CanJoinTournament, Is.False);
            _app.JoinTournament();
            Assert.That(_transport.EmittedOf("arena_create"), Is.Empty);
            Assert.That(_transport.EmittedOf("arena_join"), Is.Empty);
        }

        // ---------------------------------------------------------------------
        // Turnuva acma
        // ---------------------------------------------------------------------

        [Test]
        public void CreateEmitsArenaCreateAndOpensCreatedTournament()
        {
            LoginAsAli();
            _app.OpenTournaments();
            CallOf("Tournaments").Respond(200, "{\"tournaments\":[]}");
            Assert.That(_app.CanCreateTournament, Is.True);
            _app.CreateTournament(60, 90);
            Assert.That(_app.TournamentCreatePending, Is.True);
            _transport.RaiseConnected();
            var sent = _transport.EmittedOf("arena_create");
            Assert.That(sent.Count, Is.EqualTo(1));
            Assert.That(sent[0].GetInt("duration"), Is.EqualTo(60));
            Assert.That(sent[0].GetInt("start_in_minutes"), Is.EqualTo(90));
            Assert.That(sent[0].GetString("user_id"), Is.EqualTo("Ali"));
            Assert.That(sent[0].GetString("token"), Is.EqualTo("tok-1"));

            _app.CreateTournament(60, 90);
            Assert.That(_transport.EmittedOf("arena_create").Count, Is.EqualTo(1), "cift tiklama ikinci istegi gondermez");

            _transport.Receive("arena_created", "{\"tournament\":" + ArenaModelTests.Tournament5 + "}");
            Assert.That(_app.TournamentCreatePending, Is.False);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
            Assert.That(_app.CurrentTournament.Id, Is.EqualTo(5));
            Assert.That(_app.Tournaments.Count, Is.EqualTo(1));
            Assert.That(_transport.EmittedOf("arena_watch").Count, Is.EqualTo(1));
        }

        [TestCase(20, 0)]
        [TestCase(30, -1)]
        [TestCase(30, 1441)]
        public void CreateRejectsInvalidValuesLocally(int duration, int startIn)
        {
            LoginAsAli();
            _app.OpenTournaments();
            _app.CreateTournament(duration, startIn);
            Assert.That(_transport.ConnectUrls, Is.Empty);
            Assert.That(_app.TournamentCreatePending, Is.False);
        }

        [Test]
        public void CreateErrorClearsPendingAndShowsStatus()
        {
            LoginAsAli();
            _app.OpenTournaments();
            _app.CreateTournament(15, 0);
            _transport.RaiseConnected();
            _transport.Receive("error", "{\"msg\":\"Zaten acik bir turnuvaniz var\",\"code\":\"arena_limit\"}");
            Assert.That(_app.TournamentCreatePending, Is.False);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournaments));
            Assert.That(_app.Status, Is.EqualTo("Hata: Zaten acik bir turnuvaniz var"));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
        }

        // ---------------------------------------------------------------------
        // Katilma, duraklatma
        // ---------------------------------------------------------------------

        [Test]
        public void JoinEmitsArenaJoinAndStandingsUpdate()
        {
            OpenTournament5AsAli();
            Assert.That(_app.CanJoinTournament, Is.True);
            _app.JoinTournament();
            var join = _transport.EmittedOf("arena_join");
            Assert.That(join.Count, Is.EqualTo(1));
            Assert.That(join[0].GetInt("tournament_id"), Is.EqualTo(5));
            Assert.That(join[0].GetString("user_id"), Is.EqualTo("Ali"));
            Assert.That(join[0].GetString("token"), Is.EqualTo("tok-1"));

            _transport.Receive("arena_joined", "{\"tournament_id\":5}");
            Assert.That(_app.ArenaJoinedId, Is.EqualTo(5));
            Assert.That(_app.CanJoinTournament, Is.False);
            _transport.Receive("arena_standings", StandingsAliActive);
            Assert.That(_app.Standings.Count, Is.EqualTo(2));
            Assert.That(_app.ArenaPaused, Is.False);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
        }

        [Test]
        public void TogglePauseEmitsPauseThenResume()
        {
            OpenTournament5AsAli();
            _app.ToggleArenaPause();
            Assert.That(_transport.EmittedOf("arena_pause"), Is.Empty, "katilmadan duraklatilamaz");
            _app.JoinTournament();
            _transport.Receive("arena_joined", "{\"tournament_id\":5}");

            _app.ToggleArenaPause();
            Assert.That(_transport.EmittedOf("arena_pause").Count, Is.EqualTo(1));
            Assert.That(_app.ArenaPaused, Is.True);
            _app.ToggleArenaPause();
            Assert.That(_transport.EmittedOf("arena_resume").Count, Is.EqualTo(1));
            Assert.That(_transport.EmittedOf("arena_resume")[0].GetInt("tournament_id"), Is.EqualTo(5));
            Assert.That(_app.ArenaPaused, Is.False);
        }

        // ---------------------------------------------------------------------
        // Turnuva oyunu
        // ---------------------------------------------------------------------

        [Test]
        public void ArenaGameStartsAsTimedOnlineGame()
        {
            JoinTournament5AndStartGame();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.InArenaGame, Is.True);
            Assert.That(_app.ArenaGameTournamentId, Is.EqualTo(5));
            Assert.That(_app.MyPiece, Is.EqualTo(Board.Player1));
            Assert.That(_app.RoomId, Is.EqualTo("AR001"));
            Assert.That(_app.TimeControl, Is.EqualTo("3+2"));
            Assert.That(_app.ArenaNextGamePending, Is.False);
            Assert.That(_app.ArenaSecondsLeft, Is.EqualTo(20 * 60), "oyun ekraninda da turnuva suresi");
        }

        [Test]
        public void NormalOnlineGameIsNotArenaGame()
        {
            _app.GuestLogin();
            StartOnlineGameAsP1();
            Assert.That(_app.InArenaGame, Is.False);
            Assert.That(_app.ArenaGameTournamentId, Is.Null);
        }

        [Test]
        public void ArenaGameOverOffersNoRematchAndWaitsForNextGame()
        {
            JoinTournament5AndStartGame();
            _transport.Receive("game_over", ArenaGameOver(1, 2, 0));
            Assert.That(_app.Game.GameOver, Is.True);
            Assert.That(_app.LastArenaPoints, Is.EqualTo(2), "puan kullanici adiyla eslesir");
            Assert.That(_app.CanRequestRematch, Is.False, "turnuva oyununda rovans yok");
            Assert.That(_app.ArenaNextGamePending, Is.True);
            _app.RequestRematch();
            Assert.That(_transport.EmittedOf("rematch_request"), Is.Empty);

            // Sunucu rovans olaylari gonderse de durum degismez
            _transport.Receive("rematch_offered", "{\"room_id\":\"AR001\",\"from_piece\":2}");
            Assert.That(_app.Rematch, Is.EqualTo(RematchState.None));

            // Siradaki eslesme normal game_joined/game_start ile gelir
            _transport.Receive("game_joined", ArenaJoinedP1.Replace("AR001", "AR002").Replace("\"player_piece\":1", "\"player_piece\":2"));
            _transport.Receive("game_start", ArenaStart);
            Assert.That(_app.ArenaNextGamePending, Is.False);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.RoomId, Is.EqualTo("AR002"));
            Assert.That(_app.MyPiece, Is.EqualTo(Board.Player2));
            Assert.That(_app.Game.GameOver, Is.False);
            Assert.That(_app.LastArenaPoints, Is.Null, "yeni oyunda onceki puan gosterilmez");
        }

        [Test]
        public void BackFromFinishedArenaGameReturnsToTournamentKeepingConnection()
        {
            JoinTournament5AndStartGame();
            _transport.Receive("game_over", ArenaGameOver(2, 0, 2));
            Assert.That(_app.LastArenaPoints, Is.EqualTo(0));
            Assert.That(_app.BackLabel, Is.EqualTo("Turnuvaya Dön"));
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
            Assert.That(_app.CurrentTournament.Id, Is.EqualTo(5));
            Assert.That(_transport.DisconnectCalls, Is.EqualTo(0), "kuyruk soket kopunca duser: baglanti korunur");
            Assert.That(_app.ArenaNextGamePending, Is.True, "turnuva sayfasinda da siradaki oyun beklenir");
            Assert.That(_app.InArenaGame, Is.False);

            _transport.Receive("game_joined", ArenaJoinedP1.Replace("AR001", "AR003"));
            _transport.Receive("game_start", ArenaStart);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline));
            Assert.That(_app.InArenaGame, Is.True);
            Assert.That(_app.ArenaNextGamePending, Is.False);
        }

        [Test]
        public void LeavingActiveArenaGameForfeitsPausesAndReturnsToTournament()
        {
            JoinTournament5AndStartGame();
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.PlayingOnline), "once onay istenir");
            _app.RequestBack();
            Assert.That(_transport.EmittedOf("leave_game").Count, Is.EqualTo(1));
            Assert.That(_transport.EmittedOf("arena_pause").Count, Is.EqualTo(1), "terk eden kuyruga donmez: duraklatilir");
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
            Assert.That(_app.ArenaPaused, Is.True);
            Assert.That(_app.ArenaNextGamePending, Is.False);
            Assert.That(_transport.DisconnectCalls, Is.EqualTo(0));
        }

        [Test]
        public void PausedAfterFirstMoveAbortIsNotPending()
        {
            JoinTournament5AndStartGame();
            _transport.Receive("game_over", ServerMessages.GameOver(null, "aborted", "first_move"));
            Assert.That(_app.IsAborted, Is.True);
            Assert.That(_app.LastArenaPoints, Is.Null);
            Assert.That(_app.CanRequestRematch, Is.False);
            // Sunucu ilk hamleyi yapmayan oyuncuyu duraklatir ve siralamayi yayar
            _transport.Receive("arena_standings", StandingsAliPaused);
            Assert.That(_app.ArenaPaused, Is.True);
            Assert.That(_app.ArenaNextGamePending, Is.False);
        }

        [Test]
        public void ArenaStateFinishedClearsPendingAndRefreshes()
        {
            JoinTournament5AndStartGame();
            _transport.Receive("game_over", ArenaGameOver(1, 2, 0));
            Assert.That(_app.ArenaNextGamePending, Is.True);
            int calls = _api.Calls.Count;

            _transport.Receive("arena_state", "{\"tournament_id\":5,\"status\":\"finished\",\"ends_at\":\"2026-11-19T12:30:00+00:00\"}");
            Assert.That(_app.ArenaNextGamePending, Is.False);
            Assert.That(_app.CurrentTournament.Status, Is.EqualTo("finished"));
            Assert.That(_app.ArenaJoinedId, Is.Null);
            Assert.That(_api.Calls.Count, Is.GreaterThan(calls), "bitince sonuc sunucudan yenilenir");
            Assert.That(CallOf("Tournament").Username, Is.EqualTo("5"));

            // Biten turnuvaya yeniden baglaninca katilinmaz
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1));
        }

        [Test]
        public void ArenaStateRunningUpdatesEndsAt()
        {
            OpenTournament5AsAli();
            _transport.Receive("arena_state", "{\"tournament_id\":5,\"status\":\"running\",\"ends_at\":\"2026-11-19T12:40:00+00:00\"}");
            Assert.That(_app.ArenaSecondsLeft, Is.EqualTo(30 * 60));
        }

        // ---------------------------------------------------------------------
        // Yeniden baglanma ve eski sunucu
        // ---------------------------------------------------------------------

        [Test]
        public void ReconnectRejoinsArenaWhenNotPaused()
        {
            OpenTournament5AsAli();
            _app.JoinTournament();
            _transport.Receive("arena_joined", "{\"tournament_id\":5}");
            _transport.Receive("arena_standings", StandingsAliActive);

            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1), "once taze siralama");
            _transport.Receive("arena_standings", StandingsAliActive);
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(2));
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
        }

        [Test]
        public void ReconnectAfterOfflinePauseDoesNotUnpause()
        {
            OpenTournament5AsAli();
            _app.JoinTournament();
            _transport.Receive("arena_joined", "{\"tournament_id\":5}");
            _transport.Receive("arena_standings", StandingsAliActive);
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            _transport.Receive("arena_standings", StandingsAliPaused);
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1));
            Assert.That(_app.ArenaPaused, Is.True);
        }

        // ---------------------------------------------------------------------
        // Turnuva hatalari ve bekleme durumu
        // ---------------------------------------------------------------------

        [Test]
        public void MissedFinishReconnectArenaOverClearsStaleStateQuietly()
        {
            JoinTournament5AndStartGame();
            _transport.Receive("game_over", ArenaGameOver(1, 2, 0));
            Assert.That(_app.ArenaNextGamePending, Is.True);
            string result = _app.Status;
            // Uygulama arka plandaydi: arena_state finished kacirildi
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            _transport.Receive("arena_standings", StandingsAliActive);
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(2));
            int calls = _api.Calls.Count;

            _transport.Receive("error", "{\"msg\":\"Turnuva bitti\",\"code\":\"arena_over\"}");
            Assert.That(_app.Status, Is.EqualTo(result), "sonuc ekraninda durum satiri ezilmez");
            Assert.That(_app.ArenaNextGamePending, Is.False);
            Assert.That(_app.ArenaPendingTournamentId, Is.Null);
            Assert.That(_app.ArenaJoinedId, Is.Null);
            Assert.That(_api.Calls.Count, Is.GreaterThan(calls), "turnuva yeniden yuklenir");
            Assert.That(CallOf("Tournament").Username, Is.EqualTo("5"));

            // Soket de unuttu: sonraki yeniden baglanmalar arena_join gondermez
            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            _transport.Receive("arena_standings", StandingsAliActive);
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(2));
        }

        [TestCase("arena_over", "Turnuva bitti")]
        [TestCase("arena_not_found", "Turnuva bulunamadi")]
        [TestCase(null, "Turnuva bitti")]
        public void FailedFirstJoinForgetsArenaAndShowsErrorOnTournamentPage(string code, string msg)
        {
            OpenTournament5AsAli();
            _app.JoinTournament();
            int calls = _api.Calls.Count;
            string err = code == null
                ? "{\"msg\":\"" + msg + "\"}"
                : "{\"msg\":\"" + msg + "\",\"code\":\"" + code + "\"}";
            _transport.Receive("error", err);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
            Assert.That(_app.Status, Is.EqualTo("Hata: " + msg));
            Assert.That(_app.Tone, Is.EqualTo(StatusTone.Bad));
            Assert.That(_app.ArenaJoinedId, Is.Null);
            Assert.That(_api.Calls.Count, Is.GreaterThan(calls), "turnuva yeniden yuklenir");

            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            _transport.Receive("arena_standings", StandingsAliActive);
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1), "reddedilen turnuvaya yeniden katilinmaz");
        }

        [Test]
        public void NextGameNotPendingAfterTournamentEndsAt()
        {
            JoinTournament5AndStartGame();
            _transport.Receive("game_over", ArenaGameOver(1, 2, 0));
            Assert.That(_app.ArenaNextGamePending, Is.True);
            Assert.That(_app.ArenaPendingTournamentId, Is.EqualTo(5));
            _app.UtcNow = () => ArenaNow.AddMinutes(20);   // ends_at 12:30
            Assert.That(_app.ArenaSecondsLeft, Is.EqualTo(0));
            Assert.That(_app.ArenaNextGamePending, Is.False, "ends_at'ten sonra eslesme yok");
            Assert.That(_app.ArenaPendingTournamentId, Is.Null);
        }

        [Test]
        public void PendingTournamentIdIsNullWithoutPendingGame()
        {
            OpenTournament5AsAli();
            Assert.That(_app.ArenaPendingTournamentId, Is.Null);
        }

        [Test]
        public void ConnectionLostClearsCreatePending()
        {
            LoginAsAli();
            _app.OpenTournaments();
            _app.CreateTournament(30, 0);
            _transport.RaiseConnected();
            Assert.That(_app.TournamentCreatePending, Is.True);
            _transport.RaiseDisconnected("transport close");
            Assert.That(_app.TournamentCreatePending, Is.False, "cevap gelmeyecek: form kilitli kalmamali");
        }

        [Test]
        public void ReconnectDoesNotRejoinWhenServerPausedMe()
        {
            OpenTournament5AsAli();
            _app.JoinTournament();
            _transport.Receive("arena_joined", "{\"tournament_id\":5}");
            _transport.Receive("arena_standings", StandingsAliPaused);

            _transport.RaiseDisconnected("transport close");
            _transport.RaiseConnected();
            Assert.That(_transport.EmittedOf("arena_join").Count, Is.EqualTo(1));
        }

        [Test]
        public void OldServerWithoutArenaEventsDoesNotCrash()
        {
            OpenTournament5AsAli();
            _app.JoinTournament();
            // Eski sunucu arena_* olaylarini bilmez: hic cevap yok
            Assert.That(_app.ArenaJoinedId, Is.Null);
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Tournament));
            Assert.DoesNotThrow(() => _transport.Receive("arena_standings", "{}"));
            Assert.DoesNotThrow(() => _transport.Receive("arena_state", "{}"));
            Assert.DoesNotThrow(() => _transport.Receive("arena_created", "{}"));
            _app.RequestBack();
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));

            // Normal oyun eski sunucunun game_over'iyla aynen calisir
            StartOnlineGameAsP1();
            _transport.Receive("game_over", ServerMessages.GameOver(1, "forfeit", "timeout"));
            Assert.That(_app.InArenaGame, Is.False);
            Assert.That(_app.CanRequestRematch, Is.True);
            Assert.That(_app.ArenaNextGamePending, Is.False);
        }

        [Test]
        public void LeavingArenaAreaToMenuForgetsArenaSession()
        {
            OpenTournament5AsAli();
            _app.JoinTournament();
            _transport.Receive("arena_joined", "{\"tournament_id\":5}");
            _app.RequestBack();
            _app.RequestBack();
            Assert.That(_app.Screen, Is.EqualTo(AppScreen.Menu));
            Assert.That(_app.ArenaJoinedId, Is.Null);
            Assert.That(_transport.DisconnectCalls, Is.EqualTo(1));
        }
    }
}
