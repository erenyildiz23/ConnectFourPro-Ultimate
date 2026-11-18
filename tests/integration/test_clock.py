"""Satranc saati (3+2) testleri: sunucu otoritesinde kalan sure, ek sure, duraklama, rovans."""
import pytest

from conftest import P1_VERTICAL_WIN, play, start_match

GRACE = 2


class FakeClock:
    """Sunucunun saat hesabinda kullandigi _now() yerine elle ilerletilen saat."""

    def __init__(self, start=1_000_000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


@pytest.fixture
def clock(server, monkeypatch):
    fake = FakeClock()
    monkeypatch.setattr(server, '_now', fake)
    monkeypatch.setattr(server.config, 'MOVE_TIME_GRACE_SECONDS', GRACE)
    monkeypatch.setattr(server.config, 'CLOCK_START_DELAY_SECONDS', 5)
    return fake


@pytest.fixture(autouse=True)
def _empty_queue(server):
    with server.GAMES_LOCK:
        server.QUICK_QUEUE.clear()
    yield
    with server.GAMES_LOCK:
        server.QUICK_QUEUE.clear()


def start_timed(sio, p1="alice", p2="bob"):
    """3+2 oda kurar ve P2'yi oturtur: (oda_id, a, b, p2_game_joined)."""
    a, b = sio(), sio()
    a.emit('create_game', {'user_id': p1, 'time_control': '3+2'})
    created = a.wait_for('game_created')
    room_id = created['room_id']
    b.emit('join_game', {'room_id': room_id, 'user_id': p2})
    joined = b.wait_for('game_joined')
    a.rejoin_token, b.rejoin_token = created['rejoin_token'], joined['rejoin_token']
    a.wait_for('game_start')
    b.wait_for('game_start')
    return room_id, a, b, joined


def fields(server, room_id):
    with server.GAMES_LOCK:
        return server._clock_fields(server.GAMES[room_id])


def move(client, room_id, col, piece):
    client.emit('make_move', {'room_id': room_id, 'col': col, 'player_piece': piece})


class TestChessClock:
    def test_untimed_room_unchanged(self, sio, server, clock):
        a2, b2 = sio(), sio()
        a2.emit('create_game', {'user_id': 'p3'})
        rid = a2.wait_for('game_created')['room_id']
        b2.emit('join_game', {'room_id': rid, 'user_id': 'p4'})
        joined = b2.wait_for('game_joined')
        start = a2.wait_for('game_start')
        for payload in (start, joined):
            assert payload['time_control'] is None
            assert payload['clock_p1'] is None and payload['clock_p2'] is None
            assert payload['clock_running'] == 0
            assert payload['move_time'] == 0 and payload['turn_seconds_left'] is None
        room = server.GAMES[rid]
        assert room['time_control'] is None and room['turn_deadline'] is None
        clock.advance(10_000)
        assert server.enforce_move_deadlines() == 0
        move(a2, rid, 3, 1)
        moved = b2.wait_for('move_made')
        assert moved['clock_p1'] is None and moved['turn_seconds_left'] is None

    def test_untimed_room_keeps_move_time(self, sio, server, clock, monkeypatch):
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 30)
        room_id, a, b = start_match(sio)
        assert server.GAMES[room_id]['turn_deadline'] is not None
        server.GAMES[room_id]['turn_deadline'] -= 100
        assert server.enforce_move_deadlines() == 1
        assert a.wait_for('game_over')['detail'] == 'timeout'

    def test_timed_room_ignores_move_time(self, sio, server, clock, monkeypatch):
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 30)
        room_id, a, b, joined = start_timed(sio)
        assert server.GAMES[room_id]['turn_deadline'] is None
        start = a.last('game_start')
        # Eski istemci alanlari saat gosterir; 30 sn hamle suresi degil (move_time 0)
        assert start['move_time'] == 0 and start['turn_seconds_left'] == 185
        clock.advance(60)   # Hamle basina 30 sn sinir yok
        assert server.enforce_move_deadlines() == 0

    def test_old_client_fields_follow_running_clock(self, sio, server, clock):
        """Eski istemci (pygame, eski WebGL) yalnizca turn_seconds_left okur: sureli odada
        isleyen koltugun kalan suresi + baslangic payi gelir, saatle birlikte azalir."""
        room_id, a, b, joined = start_timed(sio)
        for payload in (a.last('game_start'), b.last('game_start'), joined):
            assert payload['turn_seconds_left'] == 185 and payload['move_time'] == 0
        clock.advance(3)
        assert fields(server, room_id)['turn_seconds_left'] == 182   # pay icinde: 180 + 2
        clock.advance(7)
        f = fields(server, room_id)
        assert f['turn_seconds_left'] == f['clock_p1'] == 175
        move(a, room_id, 3, 1)
        moved = b.wait_for('move_made')
        assert moved['clock_running'] == 2 and moved['turn_seconds_left'] == moved['clock_p2'] == 180
        clock.advance(7.5)
        f = fields(server, room_id)
        assert f['turn_seconds_left'] == f['clock_p2'] == 173

    def test_untimed_room_old_fields_unchanged(self, sio, server, clock, monkeypatch):
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 30)
        room_id, a, b = start_match(sio)
        start = fields(server, room_id)
        assert start['move_time'] == 30 and start['turn_seconds_left'] in (29, 30)
        assert start['time_control'] is None and start['clock_running'] == 0
        b.disconnect()   # suresiz odada da kopma olayi saat alanlarini tasir (degerler eskisi gibi)
        gone = a.wait_for('opponent_disconnected')
        assert gone['time_control'] is None and gone['clock_p1'] is None and gone['clock_running'] == 0
        # Sira P1'de, rakibi kopuk: sayac eskisi gibi duraklar
        assert gone['move_time'] == 30 and gone['turn_seconds_left'] is None

    def test_timed_room_reports_full_clocks_at_start(self, sio, server, clock):
        room_id, a, b, joined = start_timed(sio)
        for payload in (a.last('game_start'), b.last('game_start'), joined):
            assert payload['time_control'] == '3+2'
            assert payload['clock_p1'] == 180 and payload['clock_p2'] == 180
            assert payload['clock_running'] == 1
        room = server.GAMES[room_id]
        assert room['time_control'] == {'base': 180, 'inc': 2}
        assert room['clock_turn_started'] == clock() + 5

    def test_start_delay_not_charged(self, sio, server, clock):
        room_id, a, b, _ = start_timed(sio)
        assert a.last('game_start')['clock_delay'] == 5
        clock.advance(4)
        f = fields(server, room_id)
        assert f['clock_p1'] == 180 and f['clock_delay'] == 1
        move(a, room_id, 3, 1)
        moved = b.wait_for('move_made')
        assert moved['clock_p1'] == 182 and moved['clock_p2'] == 180
        assert moved['clock_running'] == 2 and moved['clock_delay'] == 0

    def test_increment_after_move(self, sio, server, clock):
        room_id, a, b, _ = start_timed(sio)
        clock.advance(10)   # 5 sn pay + 5 sn dusunme
        assert fields(server, room_id)['clock_p1'] == 175
        move(a, room_id, 3, 1)
        assert b.wait_for('move_made')['clock_p1'] == 177
        clock.advance(7)    # P2 hemen sayar (pay sadece ilk sirada)
        assert fields(server, room_id)['clock_p2'] == 173
        move(b, room_id, 4, 2)
        moved = a.wait_for('move_made')
        assert moved['clock_p2'] == 175 and moved['clock_p1'] == 177 and moved['clock_running'] == 1

    def test_flag_fall_forfeits(self, sio, server, clock):
        room_id, a, b, _ = start_timed(sio)
        clock.advance(185 + GRACE)   # Tam sinirda: kalan + pay == 0
        assert server.enforce_move_deadlines() == 0
        clock.advance(1)
        assert server.enforce_move_deadlines() == 1
        for c in (a, b):
            over = c.wait_for('game_over')
            assert over['reason'] == 'forfeit' and over['detail'] == 'timeout' and over['winner'] == 2
        assert server.enforce_move_deadlines() == 0
        assert fields(server, room_id)['clock_running'] == 0
        assert fields(server, room_id)['turn_seconds_left'] is None   # biten oyunda sayac yok

    def test_move_within_grace_accepted(self, sio, server, clock):
        room_id, a, b, _ = start_timed(sio)
        clock.advance(185 + GRACE - 0.5)
        move(a, room_id, 3, 1)
        moved = b.wait_for('move_made')
        assert moved['history'] == [3] and moved['clock_p1'] == 1   # -1.5 + 2 = 0.5 -> 1
        assert not server.GAMES[room_id]['game'].game_over

    def test_move_after_grace_forfeits(self, sio, server, clock):
        room_id, a, b, _ = start_timed(sio)
        clock.advance(186 + GRACE)
        move(a, room_id, 3, 1)
        over = b.wait_for('game_over')
        assert over['winner'] == 2 and over['detail'] == 'timeout'
        assert server.GAMES[room_id]['game'].move_history == []

    def test_waiting_player_clock_pauses_when_mover_opponent_disconnected(self, sio, server, clock,
                                                                           monkeypatch):
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 3)
        room_id, a, b, _ = start_timed(sio)   # Sira P1'de
        c = sio()   # seyirci de saat alanlariyla senkron kalir
        c.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        c.wait_for('game_joined')
        clock.advance(10)
        b.disconnect()
        for client in (a, c):
            gone = client.wait_for('opponent_disconnected')
            assert gone['time_control'] == '3+2'
            assert gone['clock_p1'] == 175 and gone['clock_p2'] == 180
            assert gone['clock_running'] == 0 and gone['clock_delay'] == 0
            assert gone['turn_seconds_left'] is None   # duraklamada eski istemci sayac gostermez
        clock.advance(500)
        f = fields(server, room_id)
        assert f['clock_p1'] == 175 and f['clock_running'] == 0
        assert f['turn_seconds_left'] is None
        assert server.enforce_move_deadlines() == 0
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        joined = b2.wait_for('game_joined')
        assert joined['clock_p1'] == 175 and joined['clock_running'] == 1
        for client in (a, c):
            back = client.wait_for('opponent_reconnected')
            assert back['clock_p1'] == 175 and back['clock_p2'] == 180
            assert back['clock_running'] == 1 and back['turn_seconds_left'] == 175
        clock.advance(3)
        move(a, room_id, 3, 1)
        moved = b2.wait_for('move_made')
        assert moved['clock_p1'] == 174 and moved['clock_running'] == 2

    def test_disconnected_mover_clock_keeps_running(self, sio, server, clock, monkeypatch):
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 3)
        room_id, a, b, _ = start_timed(sio)   # Sira P1'de
        a.disconnect()
        gone = b.wait_for('opponent_disconnected')
        assert gone['clock_running'] == 1 and gone['clock_delay'] == 5
        assert gone['clock_p1'] == 180 and gone['turn_seconds_left'] == 185
        clock.advance(15)
        f = fields(server, room_id)
        assert f['clock_p1'] == 170 and f['clock_running'] == 1
        clock.advance(171 + GRACE)
        assert server.enforce_move_deadlines() == 1
        over = b.wait_for('game_over')
        assert over['winner'] == 2 and over['detail'] == 'timeout'

    def test_rematch_resets_clocks(self, sio, server, clock):
        room_id, a, b, _ = start_timed(sio)
        clock.advance(50)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        b.wait_for('game_over')
        a.clear()
        b.clear()
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        for c in (a, b):
            start = c.wait_for('game_start')
            assert start['clock_p1'] == 180 and start['clock_p2'] == 180
            assert start['clock_running'] == 1 and start['time_control'] == '3+2'
        assert b.wait_for('rematch_started')['clock_p1'] == 180
        room = server.GAMES[room_id]
        assert room['clock'] == {1: 180, 2: 180} and room['clock_turn_started'] == clock() + 5

    def test_quick_match_is_timed(self, sio, server, clock):
        a, b = sio(), sio()
        a.emit('quick_match_join', {'user_id': 'alice'})
        a.wait_for('quick_match_waiting')
        b.emit('quick_match_join', {'user_id': 'bob'})
        for c in (a, b):
            for payload in (c.wait_for('game_joined'), c.wait_for('game_start')):
                assert payload['time_control'] == '3+2'
                assert payload['clock_p1'] == 180 and payload['clock_p2'] == 180
        room_id = a.last('game_joined')['room_id']
        assert server.GAMES[room_id]['time_control'] == {'base': 180, 'inc': 2}
        assert server.GAMES[room_id]['clock_turn_started'] == clock() + 5

    def test_active_games_lists_time_control(self, sio, http, clock):
        timed_room, *_ = start_timed(sio)
        c = sio()
        c.emit('create_game', {'user_id': 'carol'})
        untimed_room = c.wait_for('game_created')['room_id']
        listed = {g['room_id']: g for g in http.get('/active_games').get_json()}
        assert listed[timed_room]['time_control'] == '3+2'
        assert listed[untimed_room]['time_control'] is None

    @pytest.mark.parametrize("value", ['5+0', '', 3, None, {'base': 1, 'inc': 0}, True])
    def test_unknown_time_control_is_untimed(self, sio, server, clock, value):
        a = sio()
        a.emit('create_game', {'user_id': 'alice', 'time_control': value})
        room_id = a.wait_for('game_created')['room_id']
        assert server.GAMES[room_id]['time_control'] is None
