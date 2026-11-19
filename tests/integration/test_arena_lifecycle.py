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
        tid = self._make(database, starts_at=T0, members=())
        late = T0 + timedelta(minutes=30)   # sunucu uyuyordu, simdi baslatir
        _tick(server, clock, late)
        t = database.get_tournament(tid)
        assert t['status'] == 'running' and t['started_at'] == late
        _tick(server, clock, late + timedelta(minutes=1))
        assert _status(database, tid) == 'running'

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
