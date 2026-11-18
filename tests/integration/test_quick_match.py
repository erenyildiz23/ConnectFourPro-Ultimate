"""Hizli eslesme kuyrugu: quick_match_join / quick_match_cancel olaylari."""

import pytest

from conftest import P1_VERTICAL_WIN, identity, login_token, play, start_match, wait_until


@pytest.fixture(autouse=True)
def _empty_queue(server):
    with server.GAMES_LOCK:
        server.QUICK_QUEUE.clear()
    yield
    with server.GAMES_LOCK:
        server.QUICK_QUEUE.clear()


def sid_of(server, client):
    """Test istemcisinin sunucudaki socket sid'i."""
    return server.socketio.server.manager.sid_from_eio_sid(client.client.eio_sid, '/')


def queue_sids(server):
    with server.GAMES_LOCK:
        return [entry['sid'] for entry in server.QUICK_QUEUE]


def quick_pair(sio, p1="alice", p2="bob", tokens=(None, None)):
    """Iki istemciyi sirayla kuyruga sokar ve eslesmeyi bekler: (oda_id, a, b)."""
    a, b = sio(), sio()
    a.emit('quick_match_join', identity(p1, tokens[0]))
    a.wait_for('quick_match_waiting')
    b.emit('quick_match_join', identity(p2, tokens[1]))
    room_id = a.wait_for('game_joined')['room_id']
    b.wait_for('game_joined')
    a.wait_for('game_start')
    b.wait_for('game_start')
    return room_id, a, b


class TestQuickMatch:
    def test_two_players_get_matched(self, sio, server):
        room_id, a, b = quick_pair(sio)
        ja, jb = a.last('game_joined'), b.last('game_joined')
        assert ja['player_piece'] == 1 and jb['player_piece'] == 2
        for joined in (ja, jb):
            assert joined['room_id'] == room_id and joined['role'] == 'player'
            assert joined['quick'] is True and joined['rejoin_token']
        assert ja['opponent_info']['username'] == 'bob'
        assert jb['opponent_info']['username'] == 'alice'
        assert a.last('game_start')['opponent_name'] == 'bob'
        assert b.last('game_start')['opponent_name'] == 'alice'
        assert list(server.GAMES) == [room_id]
        room = server.GAMES[room_id]
        assert room['p1_sid'] == sid_of(server, a) and room['p2_sid'] == sid_of(server, b)
        assert ja['rejoin_token'] == room['p1_rejoin'] and jb['rejoin_token'] == room['p2_rejoin']
        assert queue_sids(server) == []
        # Normal oda gibi isler: hamleler iki tarafa gider
        play(room_id, a, b, [3])
        assert b.wait_for('move_made')['history'] == [3]

    def test_first_waits(self, sio, server):
        a = sio()
        a.emit('quick_match_join', identity('alice'))
        assert a.wait_for('quick_match_waiting') == {}
        assert a.events('game_joined') == [] and not server.GAMES
        assert queue_sids(server) == [sid_of(server, a)]

    def test_cancel_removes_from_queue(self, sio, server):
        a, b = sio(), sio()
        a.emit('quick_match_join', identity('alice'))
        a.wait_for('quick_match_waiting')
        a.emit('quick_match_cancel', {})
        assert a.wait_for('quick_match_cancelled') == {}
        b.emit('quick_match_join', identity('bob'))
        b.wait_for('quick_match_waiting')
        assert a.events('game_joined') == [] and b.events('game_joined') == []
        assert queue_sids(server) == [sid_of(server, b)] and not server.GAMES

    def test_disconnect_removes_from_queue(self, sio, server):
        a, b = sio(), sio()
        a.emit('quick_match_join', identity('alice'))
        a.wait_for('quick_match_waiting')
        a.disconnect()
        assert wait_until(lambda: queue_sids(server) == [])
        b.emit('quick_match_join', identity('bob'))
        b.wait_for('quick_match_waiting')
        assert b.events('game_joined') == [] and not server.GAMES

    def test_same_identity_not_matched_with_itself(self, sio, server):
        a1, a2 = sio(), sio()
        a1.emit('quick_match_join', identity('alice'))
        a1.wait_for('quick_match_waiting')
        a2.emit('quick_match_join', identity('alice'))
        a2.wait_for('quick_match_waiting')
        assert a1.events('game_joined') == [] and a2.events('game_joined') == []
        assert not server.GAMES
        assert queue_sids(server) == [sid_of(server, a2)]

    def test_join_removes_own_waiting_room(self, sio, server):
        a = sio()
        a.emit('create_game', identity('alice'))
        a.wait_for('game_created')
        assert len(server.GAMES) == 1
        a.emit('quick_match_join', identity('alice'))
        a.wait_for('quick_match_waiting')
        assert not server.GAMES
        assert queue_sids(server) == [sid_of(server, a)]

    def test_guest_name_with_other_connections_waiting_room_is_rejected(self, sio, server):
        a, imposter = sio(), sio()
        a.emit('create_game', identity('alice'))
        room_id = a.wait_for('game_created')['room_id']
        imposter.emit('quick_match_join', identity('alice'))
        assert imposter.wait_for('error')['code'] == 'guest_name_taken'
        assert list(server.GAMES) == [room_id] and queue_sids(server) == []

    def test_seated_player_cannot_queue(self, sio, server):
        room_id, a, b = start_match(sio)
        a.emit('quick_match_join', identity('alice'))
        err = a.wait_for('error')
        assert err == {'msg': 'Zaten bir oyundasiniz', 'code': 'already_in_game'}
        assert queue_sids(server) == [] and list(server.GAMES) == [room_id]

    def test_finished_game_does_not_block_queue(self, sio, server):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        a.emit('quick_match_join', identity('alice'))
        a.wait_for('quick_match_waiting')
        assert queue_sids(server) == [sid_of(server, a)]

    def test_taking_a_seat_leaves_the_queue(self, sio, server):
        a, b = sio(), sio()
        b.emit('quick_match_join', identity('bob'))
        b.wait_for('quick_match_waiting')
        a.emit('create_game', identity('alice'))
        room_id = a.wait_for('game_created')['room_id']
        b.emit('join_game', {'room_id': room_id, **identity('bob')})
        b.wait_for('game_start')
        assert queue_sids(server) == []

    def test_creating_a_room_leaves_the_queue(self, sio, server):
        a = sio()
        a.emit('quick_match_join', identity('alice'))
        a.wait_for('quick_match_waiting')
        a.emit('create_game', identity('alice'))
        a.wait_for('game_created')
        assert queue_sids(server) == []

    def test_invalid_identity_is_rejected(self, sio, server):
        a = sio()
        a.emit('quick_match_join', {'user_id': ''})
        assert a.wait_for('error')['code'] == 'invalid_user'
        assert queue_sids(server) == []

    def test_disconnected_quick_player_can_rejoin_with_token(self, sio, server):
        room_id, a, b = quick_pair(sio)
        token = a.last('game_joined')['rejoin_token']
        a.disconnect()
        a2 = sio()
        a2.emit('join_game', {'room_id': room_id, 'rejoin_token': token, **identity('alice')})
        joined = a2.wait_for('game_joined')
        assert joined['rejoined'] is True and joined['player_piece'] == 1


@pytest.mark.db
class TestQuickMatchRegistered:
    def test_registered_vs_registered_quick_match_is_rated(self, sio, http, database):
        tokens = (login_token(http, "alice"), login_token(http, "bob"))
        room_id, a, b = quick_pair(sio, tokens=tokens)
        play(room_id, a, b, P1_VERTICAL_WIN)
        assert a.wait_for('elo_update') == {'new_elo': 1215, 'change': 15, 'winner': True}
        assert b.wait_for('elo_update') == {'new_elo': 1185, 'change': -15, 'winner': False}
