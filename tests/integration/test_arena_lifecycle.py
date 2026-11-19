"""Arena turnuvasi yasam dongusu: baslama, iptal, bitis ve yeniden baslatma (zaman monkeypatch ile)."""

from datetime import datetime, timedelta, timezone

import pytest

T0 = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def clock(server, monkeypatch):
    """server._utcnow'u kontrol eder; ARENAS ve tarama onbellegini sifirlar."""
    state = {'now': T0}
    monkeypatch.setattr(server, '_utcnow', lambda: state['now'])

    def reset():
        server.ARENAS.clear()
        server._arena_scan_at = 0.0
        server._arena_candidates = []

    reset()

    def advance_to(when):
        state['now'] = when
        server._arena_scan_at = 0.0   # 10 sn'lik tarama kisitini atla

    state['advance_to'] = advance_to
    yield state
    reset()


def _tick(server, clock, when):
    clock['advance_to'](when)
    server.enforce_arena_lifecycle()


def _status(database, tid):
    return database.get_tournament(tid)['status']


def test_lifecycle_is_noop_without_database(server, no_database, clock):
    server.enforce_arena_lifecycle()
    assert server.ARENAS == {}


@pytest.mark.db
class TestLifecycle:
    def _make(self, database, starts_at=T0, duration=15, members=("bob", "carol")):
        database.create_user("alice", "pw")
        tid = database.create_tournament("alice", duration, starts_at)
        for m in members:
            database.create_user(m, "pw")
            database.join_tournament(tid, m)
        return tid

    def test_scheduled_starts_at_time(self, server, database, clock):
        tid = self._make(database, starts_at=T0 + timedelta(minutes=5))
        _tick(server, clock, T0)
        assert _status(database, tid) == 'scheduled' and tid not in server.ARENAS
        _tick(server, clock, T0 + timedelta(minutes=5))
        t = database.get_tournament(tid)
        assert t['status'] == 'running' and t['started_at'] == T0 + timedelta(minutes=5)
        a = server.ARENAS[tid]
        assert a['pairing'] is True and a['queue'] == [] and a['last_opponent'] == {}

    def test_cancel_when_under_two_after_ten_minutes(self, server, database, clock):
        tid = self._make(database, members=("bob",))
        _tick(server, clock, T0)
        assert _status(database, tid) == 'running'
        _tick(server, clock, T0 + timedelta(minutes=9, seconds=59))
        assert _status(database, tid) == 'running'
        _tick(server, clock, T0 + timedelta(minutes=10))
        assert _status(database, tid) == 'cancelled' and tid not in server.ARENAS

    def test_wait_counts_from_actual_start(self, server, database, clock):
        tid = self._make(database, starts_at=T0, duration=60, members=())
        late = T0 + timedelta(minutes=30)   # sunucu uyuyordu, simdi baslatir
        _tick(server, clock, late)
        t = database.get_tournament(tid)
        assert t['status'] == 'running' and t['started_at'] == late
        _tick(server, clock, late + timedelta(minutes=9))
        assert _status(database, tid) == 'running'
        _tick(server, clock, late + timedelta(minutes=10))
        assert _status(database, tid) == 'cancelled'

    def test_two_members_not_cancelled_after_ten_minutes(self, server, database, clock):
        tid = self._make(database)
        _tick(server, clock, T0)
        _tick(server, clock, T0 + timedelta(minutes=10))
        assert _status(database, tid) == 'running' and server.ARENAS[tid]['quorum'] is True

    def test_slept_through_whole_tournament_finishes_directly(self, server, database, clock):
        tid = self._make(database)
        _tick(server, clock, T0 + timedelta(minutes=20))
        assert _status(database, tid) == 'finished' and tid not in server.ARENAS

    def test_count_tournament_players(self, database):
        tid = self._make(database)
        assert database.count_tournament_players(tid) == 2
        assert database.count_tournament_players(9999) == 0

    def test_stop_pairing_at_end_then_finish_when_no_games(self, server, database, clock):
        tid = self._make(database)
        _tick(server, clock, T0)
        live = {'tournament_id': tid, 'game': type('G', (), {'game_over': False})()}
        with server.GAMES_LOCK:
            server.GAMES['live-room'] = live
        end = T0 + timedelta(minutes=15)
        _tick(server, clock, end)
        assert _status(database, tid) == 'running'
        assert server.ARENAS[tid]['pairing'] is False
        live['game'].game_over = True
        _tick(server, clock, end + timedelta(seconds=1))
        assert _status(database, tid) == 'finished' and tid not in server.ARENAS

    def test_finish_cap_fifteen_minutes(self, server, database, clock):
        tid = self._make(database)
        _tick(server, clock, T0)
        live = {'tournament_id': tid, 'game': type('G', (), {'game_over': False})()}
        with server.GAMES_LOCK:
            server.GAMES['live-room'] = live
        end = T0 + timedelta(minutes=15)
        _tick(server, clock, end + timedelta(minutes=14, seconds=59))
        assert _status(database, tid) == 'running'
        _tick(server, clock, end + timedelta(minutes=15))
        assert _status(database, tid) == 'finished' and tid not in server.ARENAS

    def test_restart_restores_running_tournament(self, server, database, clock):
        tid = self._make(database)
        database.set_player_paused(tid, "carol", True)
        _tick(server, clock, T0)
        assert tid in server.ARENAS
        server.ARENAS.clear()   # surec yeniden basladi
        clock['now'] = T0 + timedelta(minutes=1)
        server._load_arenas_from_db()
        a = server.ARENAS[tid]
        assert a['pairing'] is True and a['queue'] == []
        assert a['started_at'] == T0
        rows = {r['username']: r['paused'] for r in database.get_standings_rows(tid)}
        assert rows == {"bob": False, "carol": True}

    def test_restore_fills_missing_started_at(self, server, database, clock):
        tid = self._make(database)
        database.set_tournament_status(tid, 'running')   # started_at bos
        clock['now'] = T0 + timedelta(minutes=2)
        server._load_arenas_from_db()
        assert database.get_tournament(tid)['started_at'] == T0 + timedelta(minutes=2)
        assert server.ARENAS[tid]['pairing'] is True


def test_count_players_none_without_database(no_database):
    assert no_database.count_tournament_players(1) is None


class FakeDb:
    """Veritabani olmadan yasam dongusunu denemek icin sahte db katmani."""

    def __init__(self, status='scheduled', duration=15, count=1, write_ok=True):
        self.t = {'id': 1, 'status': status, 'starts_at': T0,
                  'ends_at': T0 + timedelta(minutes=duration), 'started_at': None}
        self.count, self.write_ok, self.writes = count, write_ok, []

    def list_tournaments(self, now):
        return [dict(self.t)]

    def set_tournament_status(self, tid, status, started_at=None, ends_at=None):
        self.writes.append(status)
        if not self.write_ok:
            return False
        self.t['status'] = status
        self.t['started_at'] = started_at or self.t['started_at']
        return True

    def count_tournament_players(self, tid):
        return self.count


@pytest.fixture
def fake(server, clock, monkeypatch):
    def make(**kw):
        f = FakeDb(**kw)
        for name in ('list_tournaments', 'set_tournament_status', 'count_tournament_players'):
            monkeypatch.setattr(server.db, name, getattr(f, name))
        emitted = []
        monkeypatch.setattr(server, '_emit_arena_state', lambda tid, st, e: emitted.append(st))
        f.emitted = emitted
        return f
    return make


def test_transient_count_failure_does_not_cancel(server, clock, fake):
    f = fake(status='running')
    f.t['started_at'] = T0
    _tick(server, clock, T0)
    f.count = None   # DB hatasi
    _tick(server, clock, T0 + timedelta(minutes=11))
    assert f.t['status'] == 'running' and 1 in server.ARENAS
    f.count = 0
    _tick(server, clock, T0 + timedelta(minutes=12))
    assert f.t['status'] == 'cancelled'


def test_quorum_stops_count_queries(server, clock, fake):
    f = fake(status='running', count=2)
    f.t['started_at'] = T0
    _tick(server, clock, T0 + timedelta(minutes=11))
    f.count = None
    _tick(server, clock, T0 + timedelta(minutes=12))
    assert f.t['status'] == 'running' and server.ARENAS[1]['quorum'] is True


def test_failed_finish_write_keeps_arena_and_skips_emit(server, clock, fake):
    f = fake(status='running', count=2)
    f.t['started_at'] = T0
    _tick(server, clock, T0 + timedelta(minutes=1))
    f.write_ok = False
    _tick(server, clock, T0 + timedelta(minutes=15))
    assert 1 in server.ARENAS and f.emitted == []
    f.write_ok = True
    _tick(server, clock, T0 + timedelta(minutes=16))
    assert 1 not in server.ARENAS and f.emitted == ['finished']


def test_failed_start_write_does_not_register(server, clock, fake):
    f = fake(write_ok=False)
    _tick(server, clock, T0)
    assert server.ARENAS == {} and f.emitted == []


def test_slept_through_emits_single_state(server, clock, fake):
    f = fake(count=1)
    _tick(server, clock, T0 + timedelta(minutes=20))
    assert f.writes == ['cancelled'] and f.emitted == ['cancelled'] and server.ARENAS == {}
    f2 = fake(count=3)
    _tick(server, clock, T0 + timedelta(minutes=20))
    assert f2.writes == ['finished'] and f2.emitted == ['finished']
