"""Socket.IO olay testleri: odalar, hamle dogrulama, seyirci, kopma/yeniden baglanma, temizlik."""

import time

import pytest

from conftest import DRAW_SEQUENCE, P1_VERTICAL_WIN, play, start_match, wait_until


def errors(client):
    return [e['msg'] for e in client.events('error')]


class TestRooms:
    def test_create_game(self, sio, http):
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        data = a.wait_for('game_created')
        assert data['player_piece'] == 1 and len(data['room_id']) == 5 and data['room_id'].isupper()
        listed = http.get('/active_games').get_json()
        assert listed == [{'room_id': data['room_id'], 'p1': 'alice', 'p1_elo': 1200, 'p2': 'Bekleniyor...',
                           'p2_elo': 0, 'status': 'WAITING', 'move_count': 0}]

    def test_second_create_replaces_waiting_room(self, sio, server):
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        first = a.wait_for('game_created')['room_id']
        a.clear()
        a.emit('create_game', {'user_id': 'alice'})
        second = a.wait_for('game_created')['room_id']
        assert first != second and list(server.GAMES) == [second]

    @pytest.mark.parametrize("payload", [None, "alice", {}, {'user_id': ''}, {'user_id': None}])
    def test_create_with_invalid_payload(self, sio, server, payload):
        a = sio()
        a.emit('create_game', payload)
        assert a.wait_for('error')['msg'] == 'Gecersiz kullanici'
        assert not server.GAMES

    def test_join_starts_game_for_both(self, sio, http):
        a, b = sio(), sio()
        a.emit('create_game', {'user_id': 'alice'})
        room_id = a.wait_for('game_created')['room_id']
        b.emit('join_game', {'room_id': room_id.lower(), 'user_id': 'bob'})   # kucuk harf de kabul
        joined = b.wait_for('game_joined')
        assert joined['player_piece'] == 2 and joined['role'] == 'player'
        assert joined['opponent_info']['username'] == 'alice'
        assert a.wait_for('game_start')['opponent_name'] == 'bob'
        assert b.wait_for('game_start')['opponent_name'] == 'alice'
        assert http.get('/active_games').get_json()[0]['status'] == 'PLAYING'

    @pytest.mark.parametrize("room_id, expected", [("ZZZZZ", "Oda bulunamadi"), ("bad!", "Gecersiz istek"),
                                                   ("", "Gecersiz istek")])
    def test_join_unknown_or_invalid_room(self, sio, room_id, expected):
        b = sio()
        b.emit('join_game', {'room_id': room_id, 'user_id': 'bob'})
        assert b.wait_for('error')['msg'] == expected

    def test_cannot_join_own_waiting_room(self, sio):
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        room_id = a.wait_for('game_created')['room_id']
        a.emit('join_game', {'room_id': room_id, 'user_id': 'alice'})
        assert a.wait_for('error')['msg'] == 'Kendi oyununuza katilamazsiniz'

    def test_third_user_becomes_spectator_and_sees_moves(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, [3])
        s = sio()
        s.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        joined = s.wait_for('game_joined')
        assert joined['role'] == 'spectator' and joined['current_state']['history'] == [3]
        assert joined['p1_info']['username'] == 'alice' and joined['p2_info']['username'] == 'bob'
        b.emit('make_move', {'room_id': room_id, 'col': 4, 'player_piece': 2})
        assert s.wait_for('move_made')['history'] == [3, 4]

    def test_latency_ping_echo(self, sio):
        a = sio()
        a.emit('latency_ping', {'t': 123, 'pad': 'x' * 100})
        assert a.wait_for('latency_pong') == {'t': 123, 'pad': 'x' * 100}


class TestMoveValidation:
    def test_valid_move_is_broadcast(self, sio):
        room_id, a, b = start_match(sio)
        a.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        for client in (a, b):
            data = client.wait_for('move_made')
            assert data['col'] == 3 and data['history'] == [3] and data['current'] == 2

    def test_not_your_turn(self, sio, server):
        room_id, a, b = start_match(sio)
        b.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 2})
        assert b.wait_for('error')['msg'] == 'Sira sizde degil!'
        assert server.GAMES[room_id]['game'].move_history == []

    def test_cannot_move_for_opponent(self, sio, server):
        room_id, a, b = start_match(sio)
        b.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        assert b.wait_for('error')['msg'] == 'Bu oyunda hamle yapma yetkiniz yok!'
        assert server.GAMES[room_id]['game'].move_history == []

    def test_spectator_cannot_move(self, sio, server):
        room_id, a, b = start_match(sio)
        s = sio()
        s.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        s.wait_for('game_joined')
        for piece in (1, 2, 0, None):
            s.emit('make_move', {'room_id': room_id, 'col': 0, 'player_piece': piece})
        assert wait_until(lambda: len(errors(s)) == 4)
        assert set(errors(s)) == {'Bu oyunda hamle yapma yetkiniz yok!'}
        assert server.GAMES[room_id]['game'].move_history == []

    @pytest.mark.parametrize("col", ["3", True, None, 3.0, -1, 7, [3]])
    def test_invalid_columns(self, sio, server, col):
        room_id, a, b = start_match(sio)
        a.emit('make_move', {'room_id': room_id, 'col': col, 'player_piece': 1})
        assert a.wait_for('error')['msg'] == 'Gecersiz hamle!'
        assert server.GAMES[room_id]['game'].move_history == []

    def test_full_column(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, [0] * 6)
        a.clear()
        a.emit('make_move', {'room_id': room_id, 'col': 0, 'player_piece': 1})
        assert a.wait_for('error')['msg'] == 'Gecersiz hamle!'

    def test_move_before_opponent_joins(self, sio):
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        room_id = a.wait_for('game_created')['room_id']
        a.emit('make_move', {'room_id': room_id, 'col': 0, 'player_piece': 1})
        assert a.wait_for('error')['msg'] == 'Rakip bekleniyor!'

    @pytest.mark.parametrize("payload", [None, "garbage", 42, {'room_id': 'ZZZZZ', 'col': 0, 'player_piece': 1}])
    def test_malformed_payloads_do_not_crash(self, sio, payload):
        a = sio()
        a.emit('make_move', payload)
        assert a.wait_for('error')['msg'] == 'Oda bulunamadi'


class TestGameEnd:
    def test_win_ends_game(self, sio, server):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        over = a.wait_for('game_over')
        assert over['winner'] == 1 and over['reason'] == 'normal' and over['move_count'] == 7
        assert b.wait_for('game_over')['winner'] == 1
        assert a.events('elo_update') == []   # misafir/kayitsiz oyuncu -> ELO yok
        a.emit('make_move', {'room_id': room_id, 'col': 5, 'player_piece': 2})
        b.emit('make_move', {'room_id': room_id, 'col': 5, 'player_piece': 2})
        assert b.wait_for('error')['msg'] == 'Oyun bitti'

    def test_draw(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, DRAW_SEQUENCE)
        over = a.wait_for('game_over')
        assert over['winner'] is None and over['move_count'] == 42

    def test_finished_game_not_listed_in_lobby(self, sio, http):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        assert http.get('/active_games').get_json() == []


class TestDisconnectAndReconnect:
    def test_creator_leaving_waiting_room_deletes_it(self, sio, server):
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        a.wait_for('game_created')
        a.disconnect()
        assert wait_until(lambda: not server.GAMES)

    def test_reconnect_within_grace_period_resumes_game(self, sio, server):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, [3, 4])
        b.wait_for('move_made')
        a.disconnect()
        notice = b.wait_for('opponent_disconnected')
        assert notice['grace_seconds'] == 1

        a2 = sio()
        a2.emit('join_game', {'room_id': room_id, 'user_id': 'alice'})
        rejoined = a2.wait_for('game_joined')
        assert rejoined['rejoined'] and rejoined['player_piece'] == 1
        assert rejoined['current_state']['history'] == [3, 4]
        b.wait_for('opponent_reconnected')

        time.sleep(1.3)  # Sure dolsa bile oyun hukmen bitmemeli
        assert b.events('game_over') == []
        a2.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        assert b.wait_for('move_made')['history'] == [3, 4, 3]

    def test_no_reconnect_means_forfeit(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, [3])
        b.wait_for('move_made')
        b.disconnect()
        over = a.wait_for('game_over', timeout=4)
        assert over['winner'] == 1 and over['reason'] == 'forfeit'

    def test_second_connection_cannot_steal_active_seat(self, sio):
        room_id, a, b = start_match(sio)
        intruder = sio()
        intruder.emit('join_game', {'room_id': room_id, 'user_id': 'alice'})
        assert intruder.wait_for('error')['msg'] == 'Bu oyuna zaten bagli durumdasiniz'

    def test_leave_game_is_immediate_forfeit(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, [3])
        a.emit('leave_game', {'room_id': room_id})
        over = b.wait_for('game_over')
        assert over['winner'] == 2 and over['reason'] == 'forfeit'

    def test_leave_waiting_room_cancels_it(self, sio, server):
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        room_id = a.wait_for('game_created')['room_id']
        a.emit('leave_game', {'room_id': room_id})
        assert wait_until(lambda: room_id not in server.GAMES)


class TestCleanup:
    def test_stale_rooms_are_removed(self, sio, server, http):
        waiting = sio()
        waiting.emit('create_game', {'user_id': 'w'})
        waiting_id = waiting.wait_for('game_created')['room_id']
        idle_id, a, b = start_match(sio, 'p1', 'p2')
        fresh_id, c, d = start_match(sio, 'p3', 'p4')

        with server.GAMES_LOCK:
            server.GAMES[waiting_id]['created_at'] -= server.config.WAITING_TIMEOUT + 1
            server.GAMES[idle_id]['last_move_at'] -= server.config.INACTIVE_TIMEOUT + 1

        assert http.post('/cleanup').get_json()['removed'] == 2
        assert list(server.GAMES) == [fresh_id]
        assert a.wait_for('game_ended')['reason'] == 'timeout'

    def test_finished_rooms_are_removed_after_timeout(self, sio, server):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        assert server.cleanup_old_games() == 0
        server.GAMES[room_id]['last_move_at'] -= server.config.FINISHED_TIMEOUT + 1
        assert server.cleanup_old_games() == 1


@pytest.mark.db
class TestRegisteredPlayers:
    def test_elo_update_and_history_after_win(self, sio, http, database):
        for name in ("alice", "bob"):
            http.post('/signup', json={'username': name, 'password': 'pw123'})
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        elo_a, elo_b = a.wait_for('elo_update'), b.wait_for('elo_update')
        assert elo_a == {'new_elo': 1215, 'change': 15, 'winner': True}
        assert elo_b == {'new_elo': 1185, 'change': -15, 'winner': False}
        over = a.wait_for('game_over')
        assert over['elo_changes'] == {'p1': 15, 'p2': -15}
        assert over['new_ratings'] == {'p1': 1215, 'p2': 1185}
        assert http.get('/user/alice/games').get_json()['games'][0]['result'] == 'win'

    def test_forfeit_updates_elo_and_is_recorded(self, sio, http, database):
        for name in ("alice", "bob"):
            http.post('/signup', json={'username': name, 'password': 'pw123'})
        room_id, a, b = start_match(sio)
        b.emit('leave_game', {'room_id': room_id})
        assert a.wait_for('elo_update')['change'] == 15
        game = http.get('/user/bob/games').get_json()['games'][0]
        assert game['result'] == 'loss' and game['end_reason'] == 'forfeit'

    def test_draw_is_recorded_without_elo_change(self, sio, http, database):
        for name in ("alice", "bob"):
            http.post('/signup', json={'username': name, 'password': 'pw123'})
        room_id, a, b = start_match(sio)
        play(room_id, a, b, DRAW_SEQUENCE)
        a.wait_for('game_over')
        assert a.events('elo_update') == []
        assert http.get('/user/alice/games').get_json()['games'][0]['result'] == 'draw'
        assert http.get('/user/alice').get_json()['user']['rating'] == 1200
