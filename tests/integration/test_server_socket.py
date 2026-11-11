"""Socket.IO olay testleri: odalar, hamle dogrulama, seyirci, kopma/yeniden baglanma, temizlik."""

import time

import pytest

from conftest import DRAW_SEQUENCE, P1_VERTICAL_WIN, identity, login_token, play, start_match, wait_until


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
        a2.emit('join_game', {'room_id': room_id, 'user_id': 'alice', 'rejoin_token': a.rejoin_token})
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

    def test_valid_rejoin_token_takes_over_seat_while_old_socket_still_registered(self, sio, server):
        """Soket olu ama sunucu henuz fark etmedi (ping zaman asimi): kanitli baglanti koltugu alir."""
        room_id, a, b = start_match(sio)
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        joined = b2.wait_for('game_joined')
        assert joined['rejoined'] and joined['player_piece'] == 2
        assert b.wait_for('error')['msg'] == 'Baska bir baglantidan oyuna girildi'
        assert a.events('opponent_disconnected') == [] and a.events('opponent_reconnected') == []
        a.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        assert b2.wait_for('move_made')['history'] == [3]
        b2.emit('make_move', {'room_id': room_id, 'col': 4, 'player_piece': 2})
        assert a.wait_for('move_made')['history'] == [3, 4]
        # Eski soket artik hamle yapamaz ve odadan cikarilmistir
        b.clear()
        b.emit('make_move', {'room_id': room_id, 'col': 0, 'player_piece': 2})
        assert b.wait_for('error')['msg'] == 'Bu oyunda hamle yapma yetkiniz yok!'
        assert b.events('move_made') == []

    def test_old_socket_disconnect_after_takeover_is_ignored(self, sio, server):
        room_id, a, b = start_match(sio)
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        b2.wait_for('game_joined')
        b.disconnect()
        time.sleep(1.5)   # Sure (1 sn) dolsa bile hicbir sey olmamali
        assert server.GAMES[room_id]['disconnected'] == {}
        assert a.events('opponent_disconnected') == [] and a.events('game_over') == []
        assert not server.GAMES[room_id]['game'].game_over

    @pytest.mark.parametrize("payload", [{}, {'rejoin_token': 'wrong'}, {'rejoin_token': 123}])
    def test_connected_seat_is_not_taken_without_valid_proof(self, sio, server, payload):
        room_id, a, b = start_match(sio)
        old_sid = server.GAMES[room_id]['p2_sid']
        intruder = sio()
        intruder.emit('join_game', {'room_id': room_id, 'user_id': 'bob', **payload})
        assert intruder.wait_for('error')['msg'] == 'Bu oyuna zaten bagli durumdasiniz'
        assert server.GAMES[room_id]['p2_sid'] == old_sid
        assert b.events('error') == []

    def test_other_seats_rejoin_token_does_not_take_over(self, sio, server):
        room_id, a, b = start_match(sio)
        intruder = sio()
        intruder.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': a.rejoin_token})
        assert intruder.wait_for('error')['msg'] == 'Bu oyuna zaten bagli durumdasiniz'

    def test_rejoin_finished_room_after_blip(self, sio, server):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        b.wait_for('game_over')
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        joined = b2.wait_for('game_joined')
        assert joined['rejoined'] and joined['current_state']['game_over'] is True

    def test_rejoin_after_forfeit_delivers_result(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, [3])
        b.wait_for('move_made')
        b.disconnect()
        over = a.wait_for('game_over', timeout=4)
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        joined = b2.wait_for('game_joined')
        assert joined['current_state']['game_over'] and joined['current_state']['winner'] == 1
        assert joined['result'] == over
        assert over['reason'] == 'forfeit' and over['detail'] == 'disconnect'
        assert b2.events('game_over') == []   # Olay tekrarlanmaz; sonuc game_joined'da

    def test_rejoin_running_game_has_no_result(self, sio):
        room_id, a, b = start_match(sio)
        b.disconnect()
        a.wait_for('opponent_disconnected')
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        assert 'result' not in b2.wait_for('game_joined')

    def test_spectator_joining_finished_room_gets_result(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        over = a.wait_for('game_over')
        s = sio()
        s.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        assert s.wait_for('game_joined')['result'] == over

    @pytest.mark.parametrize("token", ["\u015f" * 22, "", "x" * 22])
    def test_non_ascii_or_empty_rejoin_token_gets_normal_error(self, sio, server, token):
        room_id, a, b = start_match(sio)
        x = sio()
        x.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': token})
        assert x.wait_for('error')['msg'] == 'Bu oyuna zaten bagli durumdasiniz'
        b.disconnect()
        a.wait_for('opponent_disconnected')
        y = sio()
        y.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': token})
        assert y.wait_for('error')['msg'] == 'Yeniden baglanma anahtari gecersiz'

    def test_one_socket_cannot_hold_both_seats(self, sio, server):
        room_id, a, b = start_match(sio)
        b.emit('join_game', {'room_id': room_id, 'user_id': 'alice', 'rejoin_token': a.rejoin_token})
        assert b.wait_for('error')['msg'] == 'Bu oyuna zaten bagli durumdasiniz'
        room = server.GAMES[room_id]
        assert room['p1_sid'] != room['p2_sid']
        assert a.events('error') == []

    def test_stale_grace_task_does_not_end_rematch(self, sio, server, monkeypatch):
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 2)
        room_id, a, b = start_match(sio)
        b.disconnect()
        a.wait_for('opponent_disconnected')
        a.emit('leave_game', {'room_id': room_id})
        assert wait_until(lambda: server.GAMES[room_id]['game'].game_over)
        a2, b2 = sio(), sio()
        a2.emit('join_game', {'room_id': room_id, 'user_id': 'alice', 'rejoin_token': a.rejoin_token})
        a2.wait_for('game_joined')
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        b2.wait_for('game_joined')
        for c in (a2, b2):
            c.emit('rematch_request', {'room_id': room_id})
        a2.wait_for('game_start')
        time.sleep(2.5)
        assert not server.GAMES[room_id]['game'].game_over and server.GAMES[room_id]['game_no'] == 2

    def test_takeover_in_finished_room_keeps_pending_rematch(self, sio, server):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        b.wait_for('game_over')
        a.emit('rematch_request', {'room_id': room_id})
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        b2.wait_for('game_joined')
        b2.emit('rematch_request', {'room_id': room_id})
        assert a.wait_for('game_start')['rematch'] and b2.wait_for('game_start')['rematch']
        assert b.events('game_start') == []

    def test_leave_game_is_immediate_forfeit(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, [3])
        a.emit('leave_game', {'room_id': room_id})
        over = b.wait_for('game_over')
        assert over['winner'] == 2 and over['reason'] == 'forfeit' and over['detail'] == 'leave'

    def test_leave_waiting_room_cancels_it(self, sio, server):
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        room_id = a.wait_for('game_created')['room_id']
        a.emit('leave_game', {'room_id': room_id})
        assert wait_until(lambda: room_id not in server.GAMES)


class TestCleanup:
    def test_stale_rooms_are_removed(self, sio, server):
        waiting = sio()
        waiting.emit('create_game', {'user_id': 'w'})
        waiting_id = waiting.wait_for('game_created')['room_id']
        idle_id, a, b = start_match(sio, 'p1', 'p2')
        fresh_id, c, d = start_match(sio, 'p3', 'p4')

        with server.GAMES_LOCK:
            server.GAMES[waiting_id]['created_at'] -= server.config.WAITING_TIMEOUT + 1
            server.GAMES[idle_id]['last_move_at'] -= server.config.INACTIVE_TIMEOUT + 1

        assert server.cleanup_old_games() == 2
        assert list(server.GAMES) == [fresh_id]
        assert a.wait_for('game_ended')['reason'] == 'timeout'

    def test_cleanup_is_not_exposed_over_http(self, http):
        assert http.post('/cleanup').status_code in (404, 405)

    def test_finished_rooms_are_removed_after_timeout(self, sio, server):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        assert server.cleanup_old_games() == 0
        server.GAMES[room_id]['last_move_at'] -= server.config.FINISHED_TIMEOUT + 1
        assert server.cleanup_old_games() == 1


class TestMoveTimer:
    """Sunucu tarafli hamle suresi: sure dolunca sira sendeki hukmen yenilir."""

    @pytest.fixture(autouse=True)
    def timer_on(self, server, monkeypatch):
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 30)
        monkeypatch.setattr(server.config, 'MOVE_TIME_GRACE_SECONDS', 2)

    def test_game_start_and_move_made_carry_clock(self, sio):
        a, b = sio(), sio()
        a.emit('create_game', {'user_id': 'alice'})
        room_id = a.wait_for('game_created')['room_id']
        b.emit('join_game', {'room_id': room_id, 'user_id': 'bob'})
        for c in (a, b):
            start = c.wait_for('game_start')
            assert start['move_time'] == 30 and 27 <= start['turn_seconds_left'] <= 30
        a.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        moved = b.wait_for('move_made')
        assert moved['move_time'] == 30 and 27 <= moved['turn_seconds_left'] <= 30

    def test_winning_move_has_no_clock(self, sio):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        assert a.events('move_made')[-1]['turn_seconds_left'] is None

    def test_timeout_forfeits_player_to_move(self, sio, server):
        room_id, a, b = start_match(sio)
        server.GAMES[room_id]['turn_deadline'] -= 100
        assert server.enforce_move_deadlines() == 1
        for c in (a, b):
            over = c.wait_for('game_over')
            assert over['winner'] == 2 and over['reason'] == 'forfeit' and over['detail'] == 'timeout'
        assert server.enforce_move_deadlines() == 0   # Ikinci kez bitirilmez
        assert server.GAMES[room_id]['turn_deadline'] is None

    def test_deadline_not_reached_does_nothing(self, sio, server):
        room_id, a, b = start_match(sio)
        server.GAMES[room_id]['turn_deadline'] -= 31   # Tolerans (2 sn) icinde
        assert server.enforce_move_deadlines() == 0
        assert a.events('game_over') == []

    def test_clock_switches_to_opponent_after_move(self, sio, server):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, [3])
        b.wait_for('move_made')
        server.GAMES[room_id]['turn_deadline'] -= 100
        assert server.enforce_move_deadlines() == 1
        assert a.wait_for('game_over')['winner'] == 1   # P2 sirasindaydi

    def test_late_move_is_rejected_and_forfeits(self, sio, server):
        room_id, a, b = start_match(sio)
        server.GAMES[room_id]['turn_deadline'] -= 100
        a.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        over = b.wait_for('game_over')
        assert over['winner'] == 2 and over['detail'] == 'timeout'
        assert server.GAMES[room_id]['game'].move_history == []

    def test_move_inside_grace_is_accepted(self, sio, server):
        room_id, a, b = start_match(sio)
        server.GAMES[room_id]['turn_deadline'] -= 31
        a.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        assert b.wait_for('move_made')['history'] == [3]

    def test_no_clock_in_waiting_room_or_after_game_over(self, sio, server):
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        room_id = a.wait_for('game_created')['room_id']
        server.GAMES[room_id]['created_at'] -= 100
        assert server.GAMES[room_id]['turn_deadline'] is None and server.enforce_move_deadlines() == 0
        room_id, c, d = start_match(sio, 'p3', 'p4')
        play(room_id, c, d, P1_VERTICAL_WIN)
        c.wait_for('game_over')
        assert server.GAMES[room_id]['turn_deadline'] is None and server.enforce_move_deadlines() == 0

    def test_timer_disabled_with_zero(self, sio, server, monkeypatch):
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 0)
        a, b = sio(), sio()
        a.emit('create_game', {'user_id': 'alice'})
        room_id = a.wait_for('game_created')['room_id']
        b.emit('join_game', {'room_id': room_id, 'user_id': 'bob'})
        start = a.wait_for('game_start')
        assert start['move_time'] == 0 and start['turn_seconds_left'] is None
        room = server.GAMES[room_id]
        assert room['turn_deadline'] is None
        room['last_move_at'] -= 100
        assert server.enforce_move_deadlines() == 0
        a.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        assert b.wait_for('move_made')['turn_seconds_left'] is None

    def test_clock_keeps_running_while_disconnected(self, sio, server, monkeypatch):
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 2)
        room_id, a, b = start_match(sio)
        a.disconnect()   # Sira a'da
        b.wait_for('opponent_disconnected')
        server.GAMES[room_id]['turn_deadline'] -= 100
        assert server.enforce_move_deadlines() == 1
        assert b.wait_for('game_over')['detail'] == 'timeout'
        time.sleep(2.5)   # Tolerans dolsa bile ikinci game_over gelmez
        assert len(b.events('game_over')) == 1

    def test_grace_expiry_reports_disconnect_detail(self, sio):
        room_id, a, b = start_match(sio)
        b.disconnect()
        over = a.wait_for('game_over', timeout=4)
        assert over['reason'] == 'forfeit' and over['detail'] == 'disconnect'

    def test_rejoin_and_spectator_get_remaining_time(self, sio, server):
        room_id, a, b = start_match(sio)
        server.GAMES[room_id]['turn_deadline'] -= 10
        a.disconnect()
        b.wait_for('opponent_disconnected')
        a2 = sio()
        a2.emit('join_game', {'room_id': room_id, 'user_id': 'alice', 'rejoin_token': a.rejoin_token})
        joined = a2.wait_for('game_joined')
        assert joined['move_time'] == 30 and 17 <= joined['turn_seconds_left'] <= 20
        s = sio()
        s.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        assert 17 <= s.wait_for('game_joined')['turn_seconds_left'] <= 20

    def test_default_move_time_is_off(self):
        import importlib
        import os

        import config as cfg
        saved = os.environ.pop('MOVE_TIME_SECONDS', None)
        try:
            importlib.reload(cfg)
            assert cfg.MOVE_TIME_SECONDS == 0
        finally:
            if saved is not None:
                os.environ['MOVE_TIME_SECONDS'] = saved
            importlib.reload(cfg)

    def test_present_player_not_forfeited_while_opponent_is_absent(self, sio, server, monkeypatch):
        monkeypatch.setattr(server.config, 'RECONNECT_GRACE_SECONDS', 3)
        room_id, a, b = start_match(sio)   # Sira P1'de
        server.GAMES[room_id]['turn_deadline'] -= 29
        b.disconnect()
        a.wait_for('opponent_disconnected')
        server.GAMES[room_id]['turn_deadline'] -= 100
        assert server.enforce_move_deadlines() == 0
        a.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})   # Gec ama rakip yok
        assert a.wait_for('move_made')['history'] == [3]
        over = a.wait_for('game_over', timeout=5)   # Kopuk oyuncu hukmen yenilir
        assert over['winner'] == 1 and over['detail'] == 'disconnect'

    def test_clock_paused_report_and_restart_on_return(self, sio, server):
        room_id, a, b = start_match(sio)
        server.GAMES[room_id]['turn_deadline'] -= 100
        b.disconnect()
        a.wait_for('opponent_disconnected')
        s = sio()
        s.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        assert s.wait_for('game_joined')['turn_seconds_left'] is None   # Duraklatildi
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        joined = b2.wait_for('game_joined')
        assert 27 <= joined['turn_seconds_left'] <= 30   # Bekleyen alti yeni sure aldi
        assert server.enforce_move_deadlines() == 0
        assert not server.GAMES[room_id]['game'].game_over

    def test_rematch_after_timeout(self, sio, server):
        room_id, a, b = start_match(sio)
        server.GAMES[room_id]['turn_deadline'] -= 100
        server.enforce_move_deadlines()
        a.wait_for('game_over')
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        assert a.wait_for('game_start')['game_no'] == 2
        assert 27 <= b.wait_for('game_start')['turn_seconds_left'] <= 30

    def test_watchdog_loop_is_started_only_when_enabled(self, server, monkeypatch):
        started = []
        monkeypatch.setattr(server.socketio, 'start_background_task', lambda fn, *a: started.append(fn.__name__))
        server.start_cleanup_thread()
        assert started == ['cleanup_loop', 'move_clock_loop']
        started.clear()
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 0)
        server.start_cleanup_thread()
        assert started == ['cleanup_loop']


def finish_game(room_id, a, b):
    play(room_id, a, b, P1_VERTICAL_WIN)
    a.wait_for('game_over')
    b.wait_for('game_over')
    a.clear()
    b.clear()


class TestRematch:
    def test_single_request_only_offers(self, sio, server):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        a.emit('rematch_request', {'room_id': room_id})
        offer = b.wait_for('rematch_offered')
        assert offer['from_piece'] == 1 and offer['from'] == 'alice'
        a.emit('rematch_request', {'room_id': room_id})   # Tekrar: yeni bir sey olmaz
        time.sleep(0.2)
        assert len(b.events('rematch_offered')) == 1 and b.events('game_start') == []
        assert server.GAMES[room_id]['game'].game_over

    def test_both_requests_restart_with_swapped_seats(self, sio, server):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        a.emit('rematch_request', {'room_id': room_id})
        b.emit('rematch_request', {'room_id': room_id})
        start_a, start_b = a.wait_for('game_start'), b.wait_for('game_start')
        assert start_a['rematch'] and start_a['game_no'] == 2 and start_a['room_id'] == room_id
        assert start_a['player_piece'] == 2 and start_b['player_piece'] == 1
        assert start_a['opponent_name'] == 'bob' and start_b['opponent_name'] == 'alice'
        assert server.GAMES[room_id]['game'].move_history == [] and not server.GAMES[room_id]['game'].game_over
        a.clear()
        b.clear()
        a.emit('make_move', {'room_id': room_id, 'col': 0, 'player_piece': 1})   # Eski koltuk gecersiz
        assert a.wait_for('error')['msg'] == 'Bu oyunda hamle yapma yetkiniz yok!'
        # Ikinci oyun da normal biter (b artik P1)
        play(room_id, b, a, P1_VERTICAL_WIN)
        assert a.wait_for('game_over')['winner'] == 1

    def test_rematch_rejected_during_game(self, sio):
        room_id, a, b = start_match(sio)
        a.emit('rematch_request', {'room_id': room_id})
        assert a.wait_for('error')['msg'] == 'Oyun devam ediyor'

    def test_spectator_cannot_request_rematch(self, sio, server):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        s = sio()
        s.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        s.wait_for('game_joined')
        s.emit('rematch_request', {'room_id': room_id})
        assert s.wait_for('error')['msg'] == 'Sadece oyuncular rovans isteyebilir'
        assert server.GAMES[room_id]['rematch'] == set()

    @pytest.mark.parametrize("payload", [None, "x", {'room_id': 'ZZZZZ'}])
    def test_rematch_unknown_room(self, sio, payload):
        a = sio()
        a.emit('rematch_request', payload)
        assert a.wait_for('error')['msg'] == 'Oda bulunamadi'

    def test_rematch_without_arguments_or_bad_room_id(self, sio):
        a = sio()
        a.client.emit('rematch_request')
        assert a.wait_for('error')['msg'] == 'Oda bulunamadi'
        a.clear()
        for bad in ({'room_id': 123}, {'room_id': ['x']}, {'room_id': None}):
            a.emit('rematch_request', bad)
        assert wait_until(lambda: len(errors(a)) == 3)
        assert set(errors(a)) == {'Oda bulunamadi'}

    def test_opponent_leaving_makes_rematch_unavailable(self, sio, server):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        a.emit('leave_game', {'room_id': room_id})
        assert b.wait_for('rematch_unavailable')['reason'] == 'opponent_left'
        b.emit('rematch_request', {'room_id': room_id})
        b.wait_for('rematch_unavailable')
        assert server.GAMES[room_id]['game'].game_over and b.events('game_start') == []

    def test_opponent_disconnect_after_game_over_makes_rematch_unavailable(self, sio, server):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        a.emit('rematch_request', {'room_id': room_id})
        b.wait_for('rematch_offered')
        a.disconnect()
        b.wait_for('rematch_unavailable')
        b.emit('rematch_request', {'room_id': room_id})
        assert wait_until(lambda: len(b.events('rematch_unavailable')) == 2)
        assert b.events('game_start') == [] and server.GAMES[room_id]['game'].game_over

    def test_forfeit_winner_cannot_rematch_against_absent_player(self, sio):
        room_id, a, b = start_match(sio)
        a.emit('leave_game', {'room_id': room_id})
        b.wait_for('game_over')
        b.emit('rematch_request', {'room_id': room_id})
        b.wait_for('rematch_unavailable')

    def test_returning_player_can_rematch_again(self, sio, server):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        b.disconnect()
        a.wait_for('rematch_unavailable')
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': b.rejoin_token})
        b2.wait_for('game_joined')
        for c in (a, b2):
            c.emit('rematch_request', {'room_id': room_id})
        assert a.wait_for('game_start')['rematch'] and b2.wait_for('game_start')['rematch']

    def test_spectator_gets_rematch_started_with_empty_board(self, sio):
        room_id, a, b = start_match(sio)
        s = sio()
        s.emit('join_game', {'room_id': room_id, 'user_id': 'carol'})
        s.wait_for('game_joined')
        finish_game(room_id, a, b)
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        started = s.wait_for('rematch_started')
        assert started['current_state']['history'] == [] and started['game_no'] == 2
        assert started['p1_info']['username'] == 'bob' and started['p2_info']['username'] == 'alice'
        assert s.events('game_start') == []

    def test_room_listed_again_after_rematch(self, sio, http):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        assert http.get('/active_games').get_json() == []
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        a.wait_for('game_start')
        assert http.get('/active_games').get_json()[0]['status'] == 'PLAYING'

    def test_guest_rejoin_token_follows_seat_swap(self, sio):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        a.wait_for('game_start')
        a.disconnect()
        b.wait_for('opponent_disconnected')
        a2 = sio()
        a2.emit('join_game', {'room_id': room_id, 'user_id': 'alice', 'rejoin_token': a.rejoin_token})
        assert a2.wait_for('game_joined')['player_piece'] == 2
        # Baskasinin anahtari yeni koltugu da aciklamaz
        x = sio()
        x.emit('join_game', {'room_id': room_id, 'user_id': 'bob', 'rejoin_token': a.rejoin_token})
        assert x.wait_for('error')['msg'] == 'Bu oyuna zaten bagli durumdasiniz'

    def test_pending_offer_does_not_extend_finished_room_lifetime(self, sio, server):
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        a.emit('rematch_request', {'room_id': room_id})
        b.wait_for('rematch_offered')
        server.GAMES[room_id]['last_move_at'] -= server.config.FINISHED_TIMEOUT + 1
        assert server.cleanup_old_games() == 1

    def test_rematch_restarts_move_clock(self, sio, server, monkeypatch):
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 30)
        room_id, a, b = start_match(sio)
        finish_game(room_id, a, b)
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        start = a.wait_for('game_start')
        assert 27 <= start['turn_seconds_left'] <= 30
        assert server.GAMES[room_id]['turn_deadline'] is not None


@pytest.mark.db
class TestRegisteredPlayers:
    def test_elo_update_and_history_after_win(self, sio, http, database):
        tokens = (login_token(http, "alice"), login_token(http, "bob"))
        room_id, a, b = start_match(sio, tokens=tokens)
        play(room_id, a, b, P1_VERTICAL_WIN)
        elo_a, elo_b = a.wait_for('elo_update'), b.wait_for('elo_update')
        assert elo_a == {'new_elo': 1215, 'change': 15, 'winner': True}
        assert elo_b == {'new_elo': 1185, 'change': -15, 'winner': False}
        over = a.wait_for('game_over')
        assert over['elo_changes'] == {'p1': 15, 'p2': -15}
        assert over['new_ratings'] == {'p1': 1215, 'p2': 1185}
        assert http.get('/user/alice/games').get_json()['games'][0]['result'] == 'win'

    def test_forfeit_updates_elo_and_is_recorded(self, sio, http, database):
        tokens = (login_token(http, "alice"), login_token(http, "bob"))
        room_id, a, b = start_match(sio, tokens=tokens)
        b.emit('leave_game', {'room_id': room_id})
        assert a.wait_for('elo_update')['change'] == 15
        game = http.get('/user/bob/games').get_json()['games'][0]
        assert game['result'] == 'loss' and game['end_reason'] == 'forfeit'

    def test_draw_is_recorded_without_elo_change(self, sio, http, database):
        tokens = (login_token(http, "alice"), login_token(http, "bob"))
        room_id, a, b = start_match(sio, tokens=tokens)
        play(room_id, a, b, DRAW_SEQUENCE)
        a.wait_for('game_over')
        assert a.events('elo_update') == []
        assert http.get('/user/alice/games').get_json()['games'][0]['result'] == 'draw'
        assert http.get('/user/alice').get_json()['user']['rating'] == 1200

    def test_registered_live_seat_needs_rejoin_token_too(self, sio, http, database):
        tokens = (login_token(http, 'alice'), login_token(http, 'bob'))
        room_id, a, b = start_match(sio, tokens=tokens)
        # Sadece oturum token'i canli koltugu ele gecirmez (sizan token oyuncuyu atamasin)
        c = sio()
        c.emit('join_game', {'room_id': room_id, **identity('bob', tokens[1])})
        assert c.wait_for('error')['msg'] == 'Bu oyuna zaten bagli durumdasiniz'
        assert b.events('error') == []
        # Token + koltuk anahtari birlikte: devralir
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, **identity('bob', tokens[1]),
                              'rejoin_token': b.rejoin_token})
        assert b2.wait_for('game_joined')['rejoined']
        assert b.wait_for('error')['msg'] == 'Baska bir baglantidan oyuna girildi'
        # Baskasinin koltuk anahtari + kendi token'i baska koltugu acmaz
        d = sio()
        d.emit('join_game', {'room_id': room_id, **identity('alice', tokens[0]),
                             'rejoin_token': b.rejoin_token})
        assert d.wait_for('error')['msg'] == 'Bu oyuna zaten bagli durumdasiniz'

    def test_registered_disconnected_seat_needs_only_session_token(self, sio, http, database):
        tokens = (login_token(http, 'alice'), login_token(http, 'bob'))
        room_id, a, b = start_match(sio, tokens=tokens)
        b.disconnect()
        a.wait_for('opponent_disconnected')
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, **identity('bob', tokens[1])})
        assert b2.wait_for('game_joined')['rejoined']

    def test_mixed_auth_rematch_stays_unrated(self, sio, http, server, database):
        tok = login_token(http, 'alice')
        room_id, a, b = start_match(sio, tokens=(tok, None))
        finish_game(room_id, a, b)
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        a.wait_for('game_start')
        room = server.GAMES[room_id]
        assert (room['p1_uid'], room['p1_auth']) == ('bob', False)
        assert (room['p2_uid'], room['p2_auth']) == ('alice', True)
        a.clear()
        b.clear()
        play(room_id, b, a, P1_VERTICAL_WIN)
        assert a.wait_for('game_over')['elo_changes'] == {'p1': 0, 'p2': 0}
        assert http.get('/user/alice/games').get_json()['games'] == []
        assert http.get('/user/alice').get_json()['user']['rating'] == 1200

    def test_timeout_then_late_move_records_one_game(self, sio, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 30)
        tokens = (login_token(http, "alice"), login_token(http, "bob"))
        room_id, a, b = start_match(sio, tokens=tokens)
        server.GAMES[room_id]['turn_deadline'] -= 100
        assert server.enforce_move_deadlines() == 1
        a.emit('make_move', {'room_id': room_id, 'col': 3, 'player_piece': 1})
        assert a.wait_for('error')['msg'] == 'Oyun bitti'
        assert server.enforce_move_deadlines() == 0
        assert len(http.get('/user/alice/games').get_json()['games']) == 1
        assert http.get('/user/bob').get_json()['user']['rating'] == 1215
        assert http.get('/user/alice').get_json()['user']['rating'] == 1185

    def test_forfeit_result_carries_elo_for_returning_player(self, sio, http, database):
        tokens = (login_token(http, 'alice'), login_token(http, 'bob'))
        room_id, a, b = start_match(sio, tokens=tokens)
        b.disconnect()
        a.wait_for('game_over', timeout=4)
        b2 = sio()
        b2.emit('join_game', {'room_id': room_id, **identity('bob', tokens[1])})
        result = b2.wait_for('game_joined')['result']
        assert result['elo_changes'] == {'p1': 15, 'p2': -15} and result['new_ratings'] == {'p1': 1215, 'p2': 1185}

    def test_timeout_updates_elo_and_history(self, sio, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'MOVE_TIME_SECONDS', 30)
        tokens = (login_token(http, "alice"), login_token(http, "bob"))
        room_id, a, b = start_match(sio, tokens=tokens)
        server.GAMES[room_id]['turn_deadline'] -= 100
        assert server.enforce_move_deadlines() == 1
        assert b.wait_for('elo_update')['change'] == 15
        assert http.get('/user/alice/games').get_json()['games'][0]['end_reason'] == 'forfeit'

    def test_rematch_is_rated_again_and_shows_new_elo(self, sio, http, database):
        tokens = (login_token(http, "alice"), login_token(http, "bob"))
        room_id, a, b = start_match(sio, tokens=tokens)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        for c in (a, b):
            c.emit('rematch_request', {'room_id': room_id})
        start_a, start_b = a.wait_for('game_start'), b.wait_for('game_start')
        assert start_a['opponent_elo'] == 1185 and start_b['opponent_elo'] == 1215   # Yeni puanlar
        assert start_a['p1_info']['username'] == 'bob'
        a.clear()
        b.clear()
        # Koltuklar degisti: bob = P1 ve bu kez bob kazanir
        play(room_id, b, a, P1_VERTICAL_WIN)
        over = a.wait_for('game_over')
        assert over['winner'] == 1 and over['winner_uid'] == 'bob'
        assert over['elo_changes']['p1'] > 0 and over['elo_changes']['p2'] < 0
        assert len(http.get('/user/alice/games').get_json()['games']) == 2


class TestCors:
    """Varsayilan: tarayicidan sadece sunucunun kendi origin'i baglanabilir."""

    @pytest.mark.parametrize("origin, status", [
        (None, 200),                        # tarayici olmayan istemci (pygame, Unity Editor)
        ("http://localhost", 200),          # ayni origin (/play)
        ("http://evil.example", 400),
    ])
    def test_handshake_origin_check(self, http, origin, status):
        headers = {'Origin': origin} if origin else {}
        r = http.get('/socket.io/?EIO=4&transport=polling', headers=headers)
        assert r.status_code == status


class TestIdentity:
    """Kimlik istemcinin yazdigi ada degil, sunucunun verdigi token/anahtara dayanir."""

    def test_login_and_signup_return_verifiable_token(self, http, server, database):
        r = http.post('/signup', json={'username': 'alice', 'password': 'pw123456'})
        assert server.verify_session_token(r.get_json()['token']) == 'alice'
        r = http.post('/login', json={'username': 'alice', 'password': 'pw123456'})
        assert server.verify_session_token(r.get_json()['token']) == 'alice'

    @pytest.mark.parametrize("token", ["", "garbage", "alice", 123, "x" * 600])
    def test_forged_or_malformed_token_is_rejected(self, sio, server, token):
        a = sio()
        a.emit('create_game', {'user_id': 'alice', 'token': token})
        assert a.wait_for('error')['msg'] == 'Oturum gecersiz, tekrar giris yapin'
        assert not server.GAMES

    @pytest.mark.parametrize("name", [
        "bad name", "a\tb", "x\x00y", "<script>", "a/b", "\u202eevil", "a" * 41,
    ])
    def test_invalid_guest_name_is_rejected(self, sio, server, name):
        a = sio()
        a.emit('create_game', {'user_id': name})
        assert a.wait_for('error')['msg'] == 'Gecersiz kullanici'
        assert not server.GAMES
        room_id, _, _ = start_match(sio, 'p1', 'p2')
        b = sio()
        b.emit('join_game', {'room_id': room_id, 'user_id': name})
        assert b.wait_for('error')['msg'] == 'Gecersiz istek'

    @pytest.mark.parametrize("name", ["Misafir_123456", "w", "bench_a_1f2e3d", "ömer.çelik-2", "a" * 40, 42])
    def test_valid_guest_name_is_accepted(self, sio, name):
        a = sio()
        a.emit('create_game', {'user_id': name})
        assert a.wait_for('game_created')['your_info']['username'] == str(name)

    def test_token_signed_with_other_key_is_rejected(self, sio, server, database):
        from itsdangerous import URLSafeTimedSerializer
        database.create_user('alice', 'pw123456')
        forged = URLSafeTimedSerializer('not-the-key', salt='connect4-session').dumps('alice')
        a = sio()
        a.emit('create_game', {'token': forged})
        assert a.wait_for('error')['msg'] == 'Oturum gecersiz, tekrar giris yapin'

    def test_expired_token_is_rejected(self, sio, http, server, database, monkeypatch):
        token = login_token(http, 'alice')
        monkeypatch.setattr(server.config, 'SESSION_MAX_AGE', -1)
        a = sio()
        a.emit('create_game', {'token': token})
        assert a.wait_for('error')['msg'] == 'Oturum gecersiz, tekrar giris yapin'

    def test_registered_name_cannot_be_used_without_token(self, sio, http, server, database):
        login_token(http, 'alice')
        a = sio()
        a.emit('create_game', {'user_id': 'alice'})
        assert a.wait_for('error')['msg'] == 'Bu kullanici adi kayitli, giris yapin'
        room_id, _, _ = start_match(sio, 'p1', 'p2')
        b = sio()
        b.emit('join_game', {'room_id': room_id, 'user_id': 'alice'})
        assert b.wait_for('error')['msg'] == 'Bu kullanici adi kayitli, giris yapin'
        assert server.GAMES[room_id]['p1_uid'] == 'p1'

    def test_token_identity_overrides_claimed_user_id(self, sio, http, database):
        token = login_token(http, 'alice')
        login_token(http, 'bob')
        a = sio()
        a.emit('create_game', {'user_id': 'bob', 'token': token})
        assert a.wait_for('game_created')['your_info']['username'] == 'alice'

    def test_impersonating_victim_cannot_tank_their_elo(self, sio, http, database):
        """Eski saldiri: kurbanin adiyla oda acip kendi hesabina hukmen kaybetmek."""
        login_token(http, 'victim')
        attacker = login_token(http, 'attacker')
        fake = sio()
        fake.emit('create_game', {'user_id': 'victim'})
        assert fake.wait_for('error')['msg'] == 'Bu kullanici adi kayitli, giris yapin'
        # Misafir adiyla oynanan oyun kayitli rakibin puanini degistirmez
        room_id, a, b = start_match(sio, 'guest_x', 'attacker', tokens=(None, attacker))
        a.emit('leave_game', {'room_id': room_id})
        assert b.wait_for('game_over')['elo_changes'] == {'p1': 0, 'p2': 0}
        assert b.events('elo_update') == []
        assert http.get('/user/attacker').get_json()['user']['rating'] == 1200
        assert http.get('/user/victim').get_json()['user']['rating'] == 1200
        assert http.get('/user/attacker/games').get_json()['games'] == []

    def test_guest_seat_cannot_be_taken_without_rejoin_token(self, sio, server):
        room_id, a, b = start_match(sio)
        a.disconnect()
        b.wait_for('opponent_disconnected')
        for payload in ({'user_id': 'alice'}, {'user_id': 'alice', 'rejoin_token': 'wrong'},
                        {'user_id': 'alice', 'rejoin_token': b.rejoin_token}):
            intruder = sio()
            intruder.emit('join_game', {'room_id': room_id, **payload})
            assert intruder.wait_for('error')['msg'] == 'Yeniden baglanma anahtari gecersiz'
        assert 1 in server.GAMES[room_id]['disconnected']

    def test_registered_player_rejoins_with_session_token(self, sio, http, database):
        tokens = (login_token(http, 'alice'), login_token(http, 'bob'))
        room_id, a, b = start_match(sio, tokens=tokens)
        a.disconnect()
        b.wait_for('opponent_disconnected')
        a2 = sio()
        a2.emit('join_game', {'room_id': room_id, **identity('alice', tokens[0])})
        assert a2.wait_for('game_joined')['rejoined']

    def test_guest_cannot_replace_another_connections_waiting_room(self, sio, server):
        a = sio()
        a.emit('create_game', {'user_id': 'Misafir_000001'})
        room_id = a.wait_for('game_created')['room_id']
        b = sio()
        b.emit('create_game', {'user_id': 'Misafir_000001'})
        assert b.wait_for('error')['msg'] == 'Bu misafir adi kullanimda'
        assert list(server.GAMES) == [room_id]
