"""Hizli macta ilk hamle gelmezse puansiz iptal: baslangic payindan sonra 30 sn icinde ilk
hamleyi yapmayan oyuncunun oyunu kazanansiz, puansiz ve kayitsiz biter (reason 'aborted')."""
import time

import pytest

from conftest import P1_VERTICAL_WIN, identity, login_token, play, start_match

DELAY = 5
ABORT = 30
NET = 2   # Ag payi (MOVE_TIME_GRACE_SECONDS): pencereden sonra 2 sn icinde gelen ilk hamle gecerli


class FakeClock:
    def __init__(self, start=2_000_000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


@pytest.fixture
def clock(server, monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(server, '_now', fake)
    monkeypatch.setattr(server.config, 'MOVE_TIME_GRACE_SECONDS', NET)
    monkeypatch.setattr(server.config, 'CLOCK_START_DELAY_SECONDS', DELAY)
    monkeypatch.setattr(server.config, 'FIRST_MOVE_ABORT_SECONDS', ABORT)
    return fake


@pytest.fixture(autouse=True)
def _empty_queue(server):
    with server.GAMES_LOCK:
        server.QUICK_QUEUE.clear()
    yield
    with server.GAMES_LOCK:
        server.QUICK_QUEUE.clear()


def quick_pair(sio, p1="alice", p2="bob", tokens=(None, None)):
    a, b = sio(), sio()
    a.emit('quick_match_join', identity(p1, tokens[0]))
    a.wait_for('quick_match_waiting')
    b.emit('quick_match_join', identity(p2, tokens[1]))
    room_id = a.wait_for('game_joined')['room_id']
    a.rejoin_token = a.last('game_joined')['rejoin_token']
    b.rejoin_token = b.wait_for('game_joined')['rejoin_token']
    a.wait_for('game_start')
    b.wait_for('game_start')
    return room_id, a, b


def move(client, room_id, col, piece):
    client.emit('make_move', {'room_id': room_id, 'col': col, 'player_piece': piece})


def forbid_db(server, monkeypatch):
    """Iptal edilen oyun ELO'ya ve veritabanina dokunmamali."""
    def boom(*args, **kwargs):
        raise AssertionError("iptal edilen oyun veritabanina yazilmamali")
    monkeypatch.setattr(server.db, 'update_elo_by_username', boom)
    monkeypatch.setattr(server.db, 'record_game', boom)


def assert_aborted(payload):
    assert payload['reason'] == 'aborted' and payload['detail'] == 'first_move'
    assert payload['winner'] is None and payload['winner_uid'] is None
    assert payload['elo_changes'] == {'p1': 0, 'p2': 0}
    assert payload['new_ratings'] == {'p1': None, 'p2': None}
    assert payload['move_count'] == 0


class TestFirstMoveAbort:
    def test_quick_room_is_flagged(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        assert server.GAMES[room_id]['quick'] is True
        normal_id, *_ = start_match(sio, "carol", "dave")
        assert server.GAMES[normal_id]['quick'] is False

    def test_not_before_window_ends(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        clock.advance(DELAY + ABORT + NET)   # Tam sinirda (ag payi dahil): henuz iptal yok
        assert server.enforce_move_deadlines() == 0
        assert not server.GAMES[room_id]['game'].game_over
        assert a.events('game_over') == []

    def test_start_delay_is_not_counted(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        clock.advance(ABORT + 1)   # 30 sn gecti ama payin 5 sn'si sayilmaz
        assert server.enforce_move_deadlines() == 0

    def test_aborts_after_window(self, sio, server, clock, monkeypatch):
        forbid_db(server, monkeypatch)
        room_id, a, b = quick_pair(sio)
        spectator = sio()
        spectator.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        spectator.wait_for('game_joined')
        with server.GAMES_LOCK:   # Iki taraf kayitli gibi: yine de puanlanmaz/kaydedilmez
            server.GAMES[room_id]['p1_auth'] = server.GAMES[room_id]['p2_auth'] = True
        clock.advance(DELAY + ABORT + NET + 0.5)
        assert server.enforce_move_deadlines() == 1
        for c in (a, b, spectator):
            assert_aborted(c.wait_for('game_over'))
        room = server.GAMES[room_id]
        assert room['game'].game_over and room['game'].winner is None
        assert room['end_reason'] == 'aborted' and room['result']['reason'] == 'aborted'
        assert a.events('elo_update') == [] and b.events('elo_update') == []
        assert server.enforce_move_deadlines() == 0   # bir kez biter
        with server.GAMES_LOCK:
            assert server._clock_fields(room)['clock_running'] == 0

    def test_late_first_move_is_rejected_and_aborts(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        clock.advance(DELAY + ABORT + NET + 0.5)
        move(a, room_id, 3, 1)   # izleyici gorevi calismadan gelen gec hamle
        assert_aborted(b.wait_for('game_over'))
        assert server.GAMES[room_id]['game'].move_history == []

    def test_first_move_in_time_closes_window(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        clock.advance(DELAY + ABORT - 1)
        move(a, room_id, 3, 1)
        b.wait_for('move_made')
        clock.advance(60)   # P2 uzun dusunur: 3+2 saati isler, iptal yok
        assert server.enforce_move_deadlines() == 0
        assert not server.GAMES[room_id]['game'].game_over

    def test_first_move_within_network_grace_is_accepted(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        clock.advance(DELAY + ABORT + 1)   # pencere doldu ama ag payi icinde
        move(a, room_id, 3, 1)
        assert b.wait_for('move_made')['history'] == [3]
        assert not server.GAMES[room_id]['game'].game_over
        clock.advance(10)
        assert server.enforce_move_deadlines() == 0

    def test_clock_fields_report_pending_window(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        for c in (a, b):
            assert c.last('game_start')['first_move_pending'] is True
            assert c.last('game_joined')['first_move_pending'] is True
        move(a, room_id, 3, 1)
        assert b.wait_for('move_made')['first_move_pending'] is False
        normal_id, c, d = start_match(sio, "carol", "dave")
        with server.GAMES_LOCK:
            assert server._clock_fields(server.GAMES[normal_id])['first_move_pending'] is False

    def test_disconnect_event_reports_pending_window(self, sio, server, clock, monkeypatch):
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 30)
        room_id, a, b = quick_pair(sio)
        b.disconnect()
        assert a.wait_for('opponent_disconnected')['first_move_pending'] is True

    @pytest.mark.parametrize("leaver", [1, 2])
    def test_leave_during_window_aborts_unrated(self, sio, server, clock, monkeypatch, leaver):
        forbid_db(server, monkeypatch)
        room_id, a, b = quick_pair(sio)
        with server.GAMES_LOCK:
            server.GAMES[room_id]['p1_auth'] = server.GAMES[room_id]['p2_auth'] = True
        quitter, stayer = (a, b) if leaver == 1 else (b, a)
        clock.advance(DELAY + 3)
        quitter.emit('leave_game', {'room_id': room_id})
        assert_aborted(stayer.wait_for('game_over'))
        assert stayer.events('elo_update') == []
        room = server.GAMES[room_id]
        assert room['end_reason'] == 'aborted' and room['game'].winner is None

    def test_leave_after_first_move_is_still_forfeit(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        move(a, room_id, 3, 1)
        b.wait_for('move_made')
        b.emit('leave_game', {'room_id': room_id})
        over = a.wait_for('game_over')
        assert over['reason'] == 'forfeit' and over['detail'] == 'leave' and over['winner'] == 1

    def test_normal_room_leave_before_first_move_is_forfeit(self, sio, server, clock):
        room_id, a, b = start_match(sio)
        a.emit('leave_game', {'room_id': room_id})
        over = b.wait_for('game_over')
        assert over['reason'] == 'forfeit' and over['detail'] == 'leave'

    def test_normal_timed_room_has_no_window(self, sio, server, clock):
        a, b = sio(), sio()
        a.emit('create_game', {'user_id': 'alice', 'time_control': '3+2'})
        room_id = a.wait_for('game_created')['room_id']
        b.emit('join_game', {'room_id': room_id, 'user_id': 'bob'})
        b.wait_for('game_start')
        clock.advance(DELAY + ABORT + 10)
        assert server.enforce_move_deadlines() == 0
        assert not server.GAMES[room_id]['game'].game_over

    def test_normal_untimed_room_has_no_window(self, sio, server, clock):
        room_id, a, b = start_match(sio)
        clock.advance(DELAY + ABORT + 10)
        assert server.enforce_move_deadlines() == 0
        assert not server.GAMES[room_id]['game'].game_over

    def test_rematch_has_window_again(self, sio, server, clock):
        room_id, a, b = quick_pair(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        b.wait_for('game_over')
        a.clear()
        b.clear()
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        for c in (a, b):
            c.wait_for('game_start')
        room = server.GAMES[room_id]
        assert room['quick'] is True
        clock.advance(DELAY + ABORT + NET)
        assert server.enforce_move_deadlines() == 0
        clock.advance(1)
        assert server.enforce_move_deadlines() == 1
        for c in (a, b):
            assert_aborted(c.wait_for('game_over'))

    def test_first_mover_disconnect_aborts_instead_of_forfeit(self, sio, server, clock, monkeypatch):
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 0)
        room_id, a, b = quick_pair(sio)   # Sira P1'de (a)
        a.disconnect()
        b.wait_for('opponent_disconnected')
        # Kopma suresi doldu ama ilk hamle penceresi acik: hukmen yenilgi yok
        time.sleep(0.3)
        assert b.events('game_over') == []
        assert not server.GAMES[room_id]['game'].game_over
        clock.advance(DELAY + ABORT + NET + 1)
        assert server.enforce_move_deadlines() == 1
        assert_aborted(b.wait_for('game_over'))

    def test_non_mover_disconnect_forfeit_waits_for_window(self, sio, server, clock, monkeypatch):
        """Ilk hamleden once kopan (sirasi gelmeyen) oyuncu da hukmen yenilmez; pencere ilk
        hamleyle kapanirsa ve hala kopuksa hukmen yenilgi o zaman islenir."""
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 0)
        room_id, a, b = quick_pair(sio)
        b.disconnect()
        a.wait_for('opponent_disconnected')
        time.sleep(0.3)
        assert not server.GAMES[room_id]['game'].game_over
        clock.advance(DELAY + 3)
        move(a, room_id, 3, 1)
        over = a.wait_for('game_over', timeout=5)
        assert over['reason'] == 'forfeit' and over['detail'] == 'disconnect' and over['winner'] == 1

    def test_non_mover_disconnect_then_abort(self, sio, server, clock, monkeypatch):
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 0)
        room_id, a, b = quick_pair(sio)
        b.disconnect()
        a.wait_for('opponent_disconnected')
        clock.advance(DELAY + ABORT + NET + 1)
        assert server.enforce_move_deadlines() == 1
        assert_aborted(a.wait_for('game_over'))


@pytest.mark.db
class TestFirstMoveAbortRegistered:
    def test_registered_abort_is_unrated_and_not_recorded(self, sio, http, server, database, clock):
        tokens = (login_token(http, "alice"), login_token(http, "bob"))
        room_id, a, b = quick_pair(sio, tokens=tokens)
        clock.advance(DELAY + ABORT + NET + 1)
        assert server.enforce_move_deadlines() == 1
        assert_aborted(a.wait_for('game_over'))
        assert a.events('elo_update') == [] and b.events('elo_update') == []
        for name in ("alice", "bob"):
            assert server.db.get_user_by_username(name)['rating'] == 1200
            assert server.db.get_user_games(name) == []
