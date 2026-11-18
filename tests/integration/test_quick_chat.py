"""Hazir sohbet (chat_quick -> chat_message) testleri."""
import pytest

from conftest import P1_VERTICAL_WIN, play, start_match, wait_until


def flush(*clients):
    """Sunucuya gidis-donus yaparak onceki olaylarin islendiginden emin olur."""
    for c in clients:
        seen = len(c.events('latency_pong'))
        c.emit('latency_ping', {'t': 1})
        assert wait_until(lambda c=c, seen=seen: len(c.events('latency_pong')) > seen, 3.0)


def add_spectator(sio, room_id):
    s = sio()
    s.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
    assert s.wait_for('game_joined')['role'] == 'spectator'
    s.clear()
    return s


@pytest.fixture
def fake_clock(server, monkeypatch):
    """server.time.time'i elle ilerletilen bir saatle degistirir."""
    clock = {'now': 1000.0}
    monkeypatch.setattr(server.time, 'time', lambda: clock['now'])
    return clock


class TestQuickChat:
    def test_player_message_reaches_room(self, sio):
        room_id, a, b = start_match(sio)
        spec = add_spectator(sio, room_id)
        a.emit('chat_quick', {'room_id': room_id, 'msg_id': 3})
        for c in (a, b, spec):
            msg = c.wait_for('chat_message')
            assert msg == {'room_id': room_id, 'from_piece': 1, 'msg_id': 3}
        b.emit('chat_quick', {'room_id': room_id, 'msg_id': 7})
        assert spec.wait_for('chat_message')['from_piece'] in (1, 2)
        assert [m['from_piece'] for m in spec.events('chat_message')][-1] == 2

    def test_spectator_cannot_send(self, sio):
        room_id, a, b = start_match(sio)
        spec = add_spectator(sio, room_id)
        spec.emit('chat_quick', {'room_id': room_id, 'msg_id': 1})
        flush(a, b, spec)
        assert a.events('chat_message') == []
        assert b.events('chat_message') == []
        assert spec.events('chat_message') == []

    @pytest.mark.parametrize('bad', [-1, 8, "1", True, None, 1.0])
    def test_invalid_msg_id_ignored(self, sio, bad):
        room_id, a, b = start_match(sio)
        a.emit('chat_quick', {'room_id': room_id, 'msg_id': bad})
        flush(a, b)
        assert a.events('chat_message') == []
        assert b.events('chat_message') == []
        assert a.events('error') == []

    def test_rate_limited(self, sio, fake_clock):
        room_id, a, b = start_match(sio)
        a.emit('chat_quick', {'room_id': room_id, 'msg_id': 0})
        a.emit('chat_quick', {'room_id': room_id, 'msg_id': 1})
        flush(b)
        assert [m['msg_id'] for m in b.events('chat_message')] == [0]
        fake_clock['now'] += 2.1
        a.emit('chat_quick', {'room_id': room_id, 'msg_id': 2})
        flush(b)
        assert [m['msg_id'] for m in b.events('chat_message')] == [0, 2]

    def test_works_after_game_over(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        b.emit('chat_quick', {'room_id': room_id, 'msg_id': 5})
        msg = a.wait_for('chat_message')
        assert msg['from_piece'] == 2 and msg['msg_id'] == 5

    def test_unknown_room_ignored(self, sio):
        room_id, a, b = start_match(sio)
        a.emit('chat_quick', {'room_id': 'ZZZZZZ', 'msg_id': 1})
        a.emit('chat_quick', 'garbage')
        flush(a, b)
        assert a.events('chat_message') == []
        assert a.events('error') == []

    def test_disconnect_clears_rate_state(self, sio, server):
        room_id, a, b = start_match(sio)
        a.emit('chat_quick', {'room_id': room_id, 'msg_id': 0})
        b.wait_for('chat_message')
        assert len(server.LAST_CHAT_AT) == 1
        a.disconnect()
        assert wait_gone(server)


def wait_gone(server):
    return wait_until(lambda: not server.LAST_CHAT_AT, 3.0)
