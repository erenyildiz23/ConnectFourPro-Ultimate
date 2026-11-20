"""Arena turnuvasi oyunlari: kuyruk, eslestirme, puanlama, ilk hamle iptali, dislama."""

from datetime import datetime, timedelta, timezone

import pytest

from conftest import (DRAW_SEQUENCE, P1_VERTICAL_WIN, P2_VERTICAL_WIN, identity, login_token, play, start_match,
                      wait_until)

T0 = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)
DELAY = 5
ABORT = 30
NET = 2


class FakeClock:
    def __init__(self, start=3_000_000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, seconds):
        self.t += seconds


@pytest.fixture
def arena_env(server, monkeypatch):
    """_utcnow ve _now kontrol edilir; arena ve kuyruk durumu sifirlanir."""
    state = {'now': T0, 'mono': FakeClock()}
    monkeypatch.setattr(server, '_utcnow', lambda: state['now'])
    monkeypatch.setattr(server, '_now', state['mono'])
    monkeypatch.setattr(server.config, 'MOVE_TIME_GRACE_SECONDS', NET)
    monkeypatch.setattr(server.config, 'CLOCK_START_DELAY_SECONDS', DELAY)
    monkeypatch.setattr(server.config, 'FIRST_MOVE_ABORT_SECONDS', ABORT)
    # Siradaki oyun beklemesi testlerde kapali (beklemenin kendisi ayri testlerde)
    monkeypatch.setattr(server.arena, 'ARENA_NEXT_GAME_DELAY', 0)

    def reset():
        with server.GAMES_LOCK:
            server.QUICK_QUEUE.clear()
        with server.ARENAS_LOCK:
            server.ARENAS.clear()
            server.ARENA_SIDS.clear()
        server._arena_scan_at = 0.0
        server._arena_candidates = []

    reset()

    def tick(when):
        state['now'] = when
        server._arena_scan_at = 0.0
        server.enforce_arena_lifecycle()

    state['tick'] = tick
    yield state
    reset()


def move(client, room_id, col, piece):
    client.emit('make_move', {'room_id': room_id, 'col': col, 'player_piece': piece})


def queue_names(server, tid):
    with server.ARENAS_LOCK:
        return [e['username'] for e in server.ARENAS[tid]['queue']]


def standings(database, tid):
    return {r['username']: r for r in database.get_standings_rows(tid)}


class Player:
    """Kayitli arena oyuncusu: soket + token."""

    def __init__(self, sio, http, name):
        self.name = name
        self.token = login_token(http, name)
        self.c = sio()

    def join(self, tid):
        self.c.emit('arena_join', {'token': self.token, 'tournament_id': tid})
        self.c.wait_for('arena_joined')

    def games(self):
        return self.c.events('game_joined')


def next_game(players, count):
    """Her oyuncunun `count`. game_joined'ini bekler; (oda, p1, p2) dondurur."""
    for p in players:
        assert wait_until(lambda p=p: len(p.games()) >= count), f"{p.name}: {count}. oyun yok"
    joined = {p.name: p.games()[count - 1] for p in players}
    room_id = joined[players[0].name]['room_id']
    assert all(j['room_id'] == room_id for j in joined.values())
    p1 = next(p for p in players if joined[p.name]['player_piece'] == 1)
    p2 = next(p for p in players if joined[p.name]['player_piece'] == 2)
    return room_id, p1, p2


def make_tournament(database, http, creator='host', duration=15, starts_at=T0):
    login_token(http, creator)
    return database.create_tournament(creator, duration, starts_at)


# =============================================================================
# VERITABANSIZ TESTLER (sahte db katmani)
# =============================================================================

class FakeArenaDb:
    def __init__(self):
        self.rows = {}
        self.paused_calls = []
        self.recorded = []

    def row(self, name):
        return self.rows.setdefault(name, {'username': name, 'rating': 1200, 'score': 0,
                                           'games_played': 0, 'streak': 0, 'paused': False,
                                           'recent': ''})

    def get_standings_rows(self, tid):
        return [dict(r) for r in self.rows.values()]

    def apply_tournament_result(self, tid, username, points, new_streak, outcome):
        r = self.row(username)
        r['score'] += points
        r['games_played'] += 1
        r['streak'] = new_streak
        r['recent'] = (r['recent'] + outcome)[-5:]
        return True

    def set_player_paused(self, tid, username, paused):
        self.paused_calls.append((tid, username, paused))
        self.row(username)['paused'] = paused
        return True

    def record_game(self, *args, **kwargs):
        self.recorded.append((args, kwargs))
        return True

    def update_elo_by_username(self, winner, loser):
        return {'winner_change': 0, 'loser_change': 0}


@pytest.fixture
def fake_db(server, no_database, monkeypatch):
    f = FakeArenaDb()
    for name in ('get_standings_rows', 'apply_tournament_result', 'set_player_paused',
                 'record_game', 'update_elo_by_username'):
        monkeypatch.setattr(server.db, name, getattr(f, name))
    return f


def sid_of(server, client, name):
    """Test istemcisinin sunucu tarafindaki sid'i (hizli kuyruk uzerinden okunur)."""
    client.emit('quick_match_join', identity(name))
    client.wait_for('quick_match_waiting')
    with server.GAMES_LOCK:
        sid = next(e['sid'] for e in server.QUICK_QUEUE if e['uid'] == name)
        server._quick_remove_locked(sid)
    client.clear()
    return sid


def entry(sid, name):
    return {'sid': sid, 'username': name, 'info': {'username': name, 'rating': 1200}, 'auth': True}


def hand_arena(server, tid=1, queue=(), pairing=True):
    with server.ARENAS_LOCK:
        server.ARENAS[tid] = {'queue': list(queue), 'last_opponent': {}, 'started_at': T0,
                              'ends_at': T0 + timedelta(minutes=15), 'starts_at': T0,
                              'pairing': pairing}


def hand_pair(server, sio, fake_db, names=('alice', 'bob'), setup=None):
    clients = [sio() for _ in names]
    # Misafir adi kayitli adla cakismasin (sahte kayitli kullanicilar icin)
    sids = [sid_of(server, c, f"g_{n}") for c, n in zip(clients, names, strict=True)]
    for n in names:
        fake_db.row(n)
    hand_arena(server, 1, [entry(s, n) for s, n in zip(sids, names, strict=True)])
    with server.ARENAS_LOCK:   # uretimde kuyruga yalnizca arena_join/arena_resume ile girilir
        for s, n in zip(sids, names, strict=True):
            server.ARENA_SIDS[(1, n)] = s
    if setup:
        setup(sids)
    server._arena_pair(1)
    return clients, sids


@pytest.fixture
def registered(server, monkeypatch):
    """Veritabansiz kayitli kullanici: token gecerli, get_user_by_username sahte."""
    names = {'alice', 'bob', 'carol'}

    def fake_user(name):
        return {'username': name, 'rating': 1200, 'wins': 0, 'losses': 0} if name in names else None

    monkeypatch.setattr(server.db, 'get_user_by_username', fake_user)
    return lambda name: {'token': server.issue_session_token(name)}


class TestPerUserExclusivity:
    def test_second_socket_refused_while_seated_in_arena_game(self, server, sio, arena_env,
                                                              fake_db, registered):
        (a, b), _ = hand_pair(server, sio, fake_db)
        a.wait_for('game_joined')
        host = sio()
        host.emit('create_game', identity('host9'))
        room_id = host.wait_for('game_created')['room_id']
        dev2 = sio()
        for event, data in (('quick_match_join', registered('alice')),
                            ('create_game', registered('alice')),
                            ('join_game', {'room_id': room_id, **registered('alice')})):
            dev2.clear()
            dev2.emit(event, data)
            assert dev2.wait_for('error')['code'] == 'already_in_game', event
        assert server.QUICK_QUEUE == [] and server.GAMES[room_id]['p2_uid'] is None

    def test_second_socket_refused_while_username_in_arena_queue(self, server, sio, arena_env,
                                                                 no_database, registered):
        c = sio()
        sid = sid_of(server, c, 'g_alice')
        hand_arena(server, 1, [entry(sid, 'alice')])
        dev2 = sio()
        dev2.emit('quick_match_join', registered('alice'))
        assert dev2.wait_for('error')['code'] == 'already_in_game'
        assert server.QUICK_QUEUE == []

    def test_quick_pair_drops_entry_of_user_in_arena_game(self, server, sio, arena_env,
                                                          fake_db, registered):
        (a, b), _ = hand_pair(server, sio, fake_db)
        a.wait_for('game_joined')
        dev2 = sio()
        dev2_sid = sid_of(server, dev2, 'g_dev2')
        with server.GAMES_LOCK:   # cihaz 2 kaydi arena eslesmesinden once kuyruga girmisti
            server.QUICK_QUEUE.append({'sid': dev2_sid, 'uid': 'alice', 'auth': True,
                                       'info': {'username': 'alice', 'rating': 1200}})
        g = sio()
        g.emit('quick_match_join', identity('guest9'))
        g.wait_for('quick_match_waiting')
        assert g.events('game_joined') == [] and dev2.events('game_joined') == []
        assert [e['uid'] for e in server.QUICK_QUEUE] == ['guest9']

    def test_arena_enqueue_removes_same_user_quick_entry(self, server, sio, arena_env,
                                                         no_database):
        c, dev2 = sio(), sio()
        sid = sid_of(server, c, 'g_alice')
        dev2_sid = sid_of(server, dev2, 'g_dev2')
        hand_arena(server, 1)
        with server.GAMES_LOCK:
            server.QUICK_QUEUE.append({'sid': dev2_sid, 'uid': 'alice', 'auth': True,
                                       'info': {'username': 'alice', 'rating': 1200}})
            server._arena_enqueue_locked(1, sid, 'alice', {'username': 'alice'})
        assert server.QUICK_QUEUE == []
        assert dev2.wait_for('quick_match_cancelled') == {}
        assert queue_names(server, 1) == ['alice']


class TestRacesAndCutoff:
    def test_disconnect_during_start_snapshot_not_enqueued(self, server, sio, arena_env,
                                                           fake_db, monkeypatch):
        a, b = sio(), sio()
        sa, sb = sid_of(server, a, 'g_alice'), sid_of(server, b, 'g_bob')
        fake_db.row('alice')
        fake_db.row('bob')
        hand_arena(server, 1)
        with server.ARENAS_LOCK:
            server.ARENA_SIDS[(1, 'alice')] = sa
            server.ARENA_SIDS[(1, 'bob')] = sb
        real = fake_db.get_standings_rows
        fired = []

        def rows_then_disconnect(tid):
            out = real(tid)
            if not fired:
                fired.append(1)
                a.disconnect()   # anlik goruntu ile kuyruga alma arasinda kopma
            return out

        monkeypatch.setattr(server.db, 'get_standings_rows', rows_then_disconnect)
        server._arena_enqueue_waiting(1)
        assert fired and queue_names(server, 1) == ['bob']
        assert b.events('game_joined') == []

    def test_no_pairing_after_ends_at_before_tick(self, server, sio, arena_env, fake_db):
        arena_env['now'] = T0 + timedelta(minutes=15)   # yasam dongusu henuz calismadi
        (a, b), _ = hand_pair(server, sio, fake_db)
        assert a.events('game_joined') == [] and b.events('game_joined') == []

    def test_no_requeue_after_ends_at_before_tick(self, server, sio, arena_env, fake_db):
        (a, b), _ = hand_pair(server, sio, fake_db)
        room_id = a.wait_for('game_joined')['room_id']
        arena_env['now'] = T0 + timedelta(minutes=15, seconds=1)
        play(room_id, a, b, P1_VERTICAL_WIN)
        assert a.wait_for('game_over')['arena']['points'] == {'alice': 2, 'bob': 0}
        assert queue_names(server, 1) == [] and len(a.events('game_joined')) == 1

    def test_pairing_pauses_other_tournaments(self, server, sio, arena_env, fake_db):
        def setup(sids):
            hand_arena(server, 2, [entry(sids[1], 'bob')])   # el ile: bob 2'de de sirada
            with server.ARENAS_LOCK:
                server.ARENA_SIDS[(3, 'alice')] = sids[0]   # 3 henuz baslamadi
                server.ARENA_SIDS[(1, 'alice')] = sids[0]
        (a, b), _ = hand_pair(server, sio, fake_db, setup=setup)
        a.wait_for('game_joined')
        assert sorted(fake_db.paused_calls) == [(2, 'bob', True), (3, 'alice', True)]
        assert queue_names(server, 2) == []


class TestArenaNoDb:
    def test_pair_locked_builds_tournament_room(self, server, sio, arena_env, fake_db):
        (a, b), _ = hand_pair(server, sio, fake_db)
        ja, jb = a.wait_for('game_joined'), b.wait_for('game_joined')
        assert ja['tournament_id'] == 1 and jb['tournament_id'] == 1
        assert ja['time_control'] == '3+2' and ja['quick'] is True
        assert {ja['player_piece'], jb['player_piece']} == {1, 2}
        assert a.wait_for('game_start')['tournament_id'] == 1
        room = server.GAMES[ja['room_id']]
        assert room['tournament_id'] == 1 and room['p1_auth'] and room['p2_auth']
        assert server.ARENAS[1]['queue'] == []
        assert server.ARENAS[1]['last_opponent'] == {'alice': 'bob', 'bob': 'alice'}

    def test_finish_scores_and_requeues(self, server, sio, arena_env, fake_db):
        (a, b), _ = hand_pair(server, sio, fake_db)
        room_id = a.wait_for('game_joined')['room_id']
        play(room_id, a, b, P1_VERTICAL_WIN)
        over = a.wait_for('game_over')
        assert over['arena'] == {'tournament_id': 1, 'points': {'alice': 2, 'bob': 0}}
        assert fake_db.rows['alice']['score'] == 2 and fake_db.rows['alice']['streak'] == 1
        assert fake_db.rows['bob']['games_played'] == 1
        assert [kw.get('tournament_id') for _, kw in fake_db.recorded] == [1]
        # Iki oyuncu kuyruga doner ve (baska aday yok) yeniden eslesir
        assert wait_until(lambda: len(a.events('game_joined')) == 2)
        assert a.events('game_joined')[1]['room_id'] != room_id

    def test_colors_alternate_between_games(self, server, sio, arena_env, fake_db):
        # Ayni iki oyuncu art arda eslesince ilk hamle (P1) sirayla degisir
        (a, b), _ = hand_pair(server, sio, fake_db)
        pieces = []
        for n in range(1, 4):
            assert wait_until(lambda n=n: len(a.events('game_joined')) >= n and len(b.events('game_joined')) >= n)
            ja = a.events('game_joined')[n - 1]
            pieces.append(ja['player_piece'])
            p1, p2 = (a, b) if ja['player_piece'] == 1 else (b, a)
            play(ja['room_id'], p1, p2, P1_VERTICAL_WIN)
            assert wait_until(lambda n=n: len(a.events('game_over')) >= n)
        assert pieces[0] != pieces[1] and pieces[1] != pieces[2]

    def test_rematch_ignored_in_tournament_room(self, server, sio, no_database):
        room_id, a, b = start_match(sio)
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        with server.GAMES_LOCK:
            server.GAMES[room_id]['tournament_id'] = 1
        a.clear()
        b.clear()
        a.emit('rematch_request', {'room_id': room_id})
        b.emit('rematch_request', {'room_id': room_id})
        for c in (a, b):
            c.pull()
            assert c.events('rematch_offered') == [] and c.events('game_start') == []
            assert c.events('error') == []
        assert server.GAMES[room_id]['rematch'] == set() and server.GAMES[room_id]['game_no'] == 1

    def test_arena_queued_sid_blocked_from_quick_and_create(self, server, sio, arena_env, no_database):
        c = sio()
        sid = sid_of(server, c, 'alice')
        hand_arena(server, 1, [entry(sid, 'alice')])
        c.emit('quick_match_join', identity('alice'))
        assert c.wait_for('error')['code'] == 'already_in_game'
        assert server.QUICK_QUEUE == []
        c.clear()
        c.emit('create_game', identity('alice'))
        assert c.wait_for('error')['code'] == 'already_in_game'
        assert c.events('game_created') == []

    def test_arena_queued_sid_cannot_take_seat(self, server, sio, arena_env, no_database):
        host = sio()
        host.emit('create_game', identity('carol'))
        room_id = host.wait_for('game_created')['room_id']
        c = sio()
        sid = sid_of(server, c, 'alice')
        hand_arena(server, 1, [entry(sid, 'alice')])
        c.emit('join_game', {'room_id': room_id, **identity('alice')})
        assert c.wait_for('error')['code'] == 'already_in_game'
        assert server.GAMES[room_id]['p2_uid'] is None

    def test_disconnect_drops_from_arena_queue(self, server, sio, arena_env, no_database):
        c = sio()
        sid = sid_of(server, c, 'alice')
        hand_arena(server, 1, [entry(sid, 'alice')])
        hand_arena(server, 2, [entry(sid, 'alice')])
        with server.ARENAS_LOCK:
            server.ARENA_SIDS[(1, 'alice')] = sid
        c.disconnect()
        assert queue_names(server, 1) == [] and queue_names(server, 2) == []
        assert server.ARENA_SIDS == {}

    def test_first_move_abort_pauses_culprit_requeues_other(self, server, sio, arena_env, fake_db):
        (a, b), _ = hand_pair(server, sio, fake_db)
        joined = a.wait_for('game_joined')
        culprit = 'alice' if joined['player_piece'] == 1 else 'bob'
        other = 'bob' if culprit == 'alice' else 'alice'
        arena_env['mono'].advance(DELAY + ABORT + NET + 0.5)
        assert server.enforce_move_deadlines() == 1
        assert a.wait_for('game_over')['reason'] == 'aborted'
        assert fake_db.paused_calls == [(1, culprit, True)]
        assert fake_db.recorded == []
        assert all(r['games_played'] == 0 and r['score'] == 0 for r in fake_db.rows.values())
        assert queue_names(server, 1) == [other]

    def test_leave_during_first_move_window_pauses_leaver(self, server, sio, arena_env, fake_db):
        (a, b), _ = hand_pair(server, sio, fake_db)
        joined = b.wait_for('game_joined')
        assert b.events('game_joined')
        b.emit('leave_game', {'room_id': joined['room_id']})
        a.wait_for('game_over')
        assert fake_db.paused_calls == [(1, 'bob', True)]
        assert queue_names(server, 1) == ['alice']

    def test_no_requeue_when_pairing_stopped(self, server, sio, arena_env, fake_db):
        (a, b), _ = hand_pair(server, sio, fake_db)
        room_id = a.wait_for('game_joined')['room_id']
        with server.ARENAS_LOCK:
            server.ARENAS[1]['pairing'] = False
            server.ARENAS[1]['queue'] = []
        play(room_id, a, b, P1_VERTICAL_WIN)
        assert a.wait_for('game_over')['arena']['points'] == {'alice': 2, 'bob': 0}
        assert queue_names(server, 1) == [] and len(a.events('game_joined')) == 1


class TestNextGameDelay:
    """Spec 8.3: sonuc ekrani ve "Siradaki oyun" icin kisa bekleme, sonra yeniden eslesme."""

    def test_requeue_waits_before_next_game(self, server, sio, arena_env, fake_db, monkeypatch):
        monkeypatch.setattr(server.arena, 'ARENA_NEXT_GAME_DELAY', 0.4)
        (a, b), _ = hand_pair(server, sio, fake_db)
        room_id = a.wait_for('game_joined')['room_id']
        play(room_id, a, b, P1_VERTICAL_WIN)
        a.wait_for('game_over')
        b.wait_for('game_over')
        assert queue_names(server, 1) == []
        assert len(a.events('game_joined')) == 1 and len(b.events('game_joined')) == 1
        assert wait_until(lambda: len(a.events('game_joined')) == 2
                          and len(b.events('game_joined')) == 2)
        assert a.events('game_joined')[1]['room_id'] != room_id

    def test_default_delay_is_short_pause(self, server):
        import arena
        assert arena.ARENA_NEXT_GAME_DELAY == 4

    @pytest.mark.parametrize('change', ['paused', 'new_sid', 'pairing_closed', 'gone', 'seated'])
    def test_delayed_requeue_rechecks_state(self, server, sio, arena_env, fake_db, change):
        a, b = sio(), sio()
        sa, sb = sid_of(server, a, 'g_alice'), sid_of(server, b, 'g_bob')
        fake_db.row('alice')
        fake_db.row('bob')
        hand_arena(server, 1)
        with server.ARENAS_LOCK:
            server.ARENA_SIDS[(1, 'alice')] = sa
            server.ARENA_SIDS[(1, 'bob')] = sb
        # Bekleme sirasinda alice'in durumu degisti
        if change == 'paused':
            fake_db.row('alice')['paused'] = True
        elif change == 'new_sid':
            with server.ARENAS_LOCK:
                server.ARENA_SIDS[(1, 'alice')] = 'baska-soket'
        elif change == 'pairing_closed':
            arena_env['now'] = T0 + timedelta(minutes=15)
        elif change == 'gone':
            with server.ARENAS_LOCK:
                del server.ARENA_SIDS[(1, 'alice')]
        elif change == 'seated':
            host = sio()
            host.emit('create_game', identity('carol'))
            rid = host.wait_for('game_created')['room_id']
            with server.GAMES_LOCK:
                server._seat_second_player(server.GAMES[rid], sa, 'alice',
                                           {'username': 'alice'}, True)
        server._arena_requeue_now(1, [('alice', sa), ('bob', sb)])
        expected = [] if change == 'pairing_closed' else ['bob']
        assert queue_names(server, 1) == expected
        assert a.events('game_joined') == [] and b.events('game_joined') == []

    def test_delayed_requeue_pairs_when_unchanged(self, server, sio, arena_env, fake_db):
        a, b = sio(), sio()
        sa, sb = sid_of(server, a, 'g_alice'), sid_of(server, b, 'g_bob')
        fake_db.row('alice')
        fake_db.row('bob')
        hand_arena(server, 1)
        with server.ARENAS_LOCK:
            server.ARENA_SIDS[(1, 'alice')] = sa
            server.ARENA_SIDS[(1, 'bob')] = sb
        server._arena_requeue_now(1, [('alice', sa), ('bob', sb)])
        assert a.wait_for('game_joined')['room_id'] == b.wait_for('game_joined')['room_id']


def _seats(clients, names, room_joined):
    """(p1 istemci, p1 adi, p2 istemci, p2 adi)."""
    by_piece = {}
    for c, n, j in zip(clients, names, room_joined, strict=True):
        by_piece[j['player_piece']] = (c, n)
    return (*by_piece[1], *by_piece[2])


class TestAfkTimeout:
    """Hic hamle yapmadan suresi biten turnuva oyuncusu duraklatilir (P2 AFK dongusu)."""

    @staticmethod
    def _moves(server, room_id, seq):
        """seq: (istemci, sutun, tas) hamleleri; her biri sunucuda islenene kadar beklenir."""
        for n, (c, col, piece) in enumerate(seq, start=1):
            move(c, room_id, col, piece)
            assert wait_until(lambda n=n: len(server.GAMES[room_id]['game'].move_history) == n)

    def test_p2_times_out_without_moving_is_paused(self, server, sio, arena_env, fake_db):
        (a, b), _ = hand_pair(server, sio, fake_db)
        joined = [a.wait_for('game_joined'), b.wait_for('game_joined')]
        room_id = joined[0]['room_id']
        c1, n1, c2, n2 = _seats((a, b), ('alice', 'bob'), joined)
        self._moves(server, room_id, [(c1, 3, 1)])
        arena_env['mono'].advance(1000)
        assert server.enforce_move_deadlines() == 1
        over = c1.wait_for('game_over')
        assert over['reason'] == 'forfeit' and over['detail'] == 'timeout'
        assert over['arena']['points'] == {n1: 2, n2: 0}   # sure yenilgisi yine sayilir
        assert fake_db.paused_calls == [(1, n2, True)]
        assert fake_db.rows[n2]['paused'] is True
        assert wait_until(lambda: queue_names(server, 1) == [n1])
        assert len(c2.events('game_joined')) == 1

    def test_timeout_after_moving_is_not_paused(self, server, sio, arena_env, fake_db):
        (a, b), _ = hand_pair(server, sio, fake_db)
        joined = [a.wait_for('game_joined'), b.wait_for('game_joined')]
        room_id = joined[0]['room_id']
        c1, n1, c2, n2 = _seats((a, b), ('alice', 'bob'), joined)
        self._moves(server, room_id, [(c1, 3, 1), (c2, 4, 2), (c1, 3, 1)])
        arena_env['mono'].advance(1000)   # P2 bir hamle yapmisti: normal sure yenilgisi
        assert server.enforce_move_deadlines() == 1
        assert c1.wait_for('game_over')['detail'] == 'timeout'
        assert fake_db.paused_calls == []
        # Ikisi de kuyruga doner ve yeniden eslesir
        assert wait_until(lambda: len(a.events('game_joined')) == 2
                          and len(b.events('game_joined')) == 2)


def running_tournament(tid=1):
    return {'id': tid, 'creator': 'host', 'duration_minutes': 15, 'starts_at': T0,
            'ends_at': T0 + timedelta(minutes=15), 'started_at': T0, 'status': 'running',
            'players': 2}


@pytest.fixture
def running_db(server, fake_db, monkeypatch):
    """Veritabansiz 'running' turnuva #1 (sunucu yeniden baslamis: ARENAS bos)."""
    t = running_tournament()
    monkeypatch.setattr(server.db, 'get_tournament', lambda tid: dict(t) if tid == 1 else None)
    monkeypatch.setattr(server.db, 'list_tournaments', lambda now: [dict(t)])
    monkeypatch.setattr(server.db, 'set_tournament_status', lambda *a, **k: True)
    monkeypatch.setattr(server.db, 'count_tournament_players', lambda tid: len(fake_db.rows))

    def join(tid, name):
        fake_db.row(name)['paused'] = False
        return True

    monkeypatch.setattr(server.db, 'join_tournament', join)
    return fake_db


class TestAdoptAfterRestart:
    """Yeniden baslama / uyanma: ARENAS bos iken gelen arena_join kaybolmamali."""

    def test_join_before_first_tick_is_paired(self, server, sio, arena_env, running_db,
                                              registered):
        arena_env['now'] = T0 + timedelta(minutes=1)
        a, b = sio(), sio()
        for c, name in ((a, 'alice'), (b, 'bob')):
            c.emit('arena_join', {**registered(name), 'tournament_id': 1})
            c.wait_for('arena_joined')
        arena_env['tick'](T0 + timedelta(minutes=1))
        ja, jb = a.wait_for('game_joined'), b.wait_for('game_joined')
        assert ja['tournament_id'] == 1 and ja['room_id'] == jb['room_id']

    def test_tick_adoption_drains_registered_sids(self, server, sio, arena_env, running_db):
        a, b = sio(), sio()
        sa, sb = sid_of(server, a, 'g_alice'), sid_of(server, b, 'g_bob')
        running_db.row('alice')
        running_db.row('bob')
        with server.ARENAS_LOCK:   # arena_join benimsemeden once islendi
            server.ARENA_SIDS[(1, 'alice')] = sa
            server.ARENA_SIDS[(1, 'bob')] = sb
        arena_env['tick'](T0 + timedelta(minutes=1))
        ja, jb = a.wait_for('game_joined'), b.wait_for('game_joined')
        assert ja['room_id'] == jb['room_id']

    def test_tick_adoption_after_ends_at_does_not_pair(self, server, sio, arena_env, running_db):
        a, b = sio(), sio()
        sa, sb = sid_of(server, a, 'g_alice'), sid_of(server, b, 'g_bob')
        running_db.row('alice')
        running_db.row('bob')
        with server.ARENAS_LOCK:
            server.ARENA_SIDS[(1, 'alice')] = sa
            server.ARENA_SIDS[(1, 'bob')] = sb
        # ends_at gecti: benimseme eslestirmeyi kapali kurar, kimse eslesmez
        arena_env['tick'](T0 + timedelta(minutes=15, seconds=1))
        assert a.events('game_joined') == [] and b.events('game_joined') == []


# =============================================================================
# VERITABANLI TESTLER
# =============================================================================

@pytest.mark.db
class TestArenaGames:
    def _start_two(self, server, sio, http, database, arena_env, names=('alice', 'bob')):
        tid = make_tournament(database, http)
        players = [Player(sio, http, n) for n in names]
        for p in players:
            p.join(tid)
        arena_env['tick'](T0)   # baslar; once katilanlar kuyruga alinip eslesir
        return tid, players

    def test_rejoin_after_restart_before_tick_is_paired(self, server, sio, http, database,
                                                       arena_env):
        tid = make_tournament(database, http)
        arena_env['tick'](T0)   # kimse yokken baslar
        assert database.get_tournament(tid)['status'] == 'running'
        with server.ARENAS_LOCK:   # surec yeniden basladi / uyandi: bellek bos
            server.ARENAS.clear()
            server.ARENA_SIDS.clear()
        arena_env['now'] = T0 + timedelta(minutes=1)
        a, b = Player(sio, http, 'alice'), Player(sio, http, 'bob')
        a.join(tid)
        b.join(tid)
        room_id, *_ = next_game([a, b], 1)
        arena_env['tick'](T0 + timedelta(minutes=1))
        assert len(a.games()) == 1 and server.GAMES[room_id]['tournament_id'] == tid

    def test_two_joined_players_get_paired_3plus2(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        for p in (a, b):
            j = p.games()[0]
            assert j['tournament_id'] == tid and j['time_control'] == '3+2'
            assert p.c.wait_for('game_start')['tournament_id'] == tid
        assert server.GAMES[room_id]['tournament_id'] == tid

    def test_win_scores_and_requeues(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        play(room_id, p1.c, p2.c, P1_VERTICAL_WIN)
        over = p1.c.wait_for('game_over')
        assert over['arena'] == {'tournament_id': tid, 'points': {p1.name: 2, p2.name: 0}}
        rows = standings(database, tid)
        assert rows[p1.name]['score'] == 2 and rows[p1.name]['streak'] == 1
        assert rows[p2.name]['score'] == 0 and rows[p2.name]['games_played'] == 1
        new_room, *_ = next_game([a, b], 2)   # ikisi de kuyruga dondu, yeniden eslesti
        assert new_room != room_id

    def test_next_game_after_delay_skips_player_paused_meanwhile(self, server, sio, http,
                                                                database, arena_env, monkeypatch):
        monkeypatch.setattr(server.arena, 'ARENA_NEXT_GAME_DELAY', 0.5)
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        play(room_id, p1.c, p2.c, P1_VERTICAL_WIN)
        p1.c.wait_for('game_over')
        assert queue_names(server, tid) == []   # bekleme: hemen eslesme yok
        p2.c.emit('arena_pause', {'token': p2.token, 'tournament_id': tid})
        assert wait_until(lambda: standings(database, tid)[p2.name]['paused'] is True)
        assert wait_until(lambda: queue_names(server, tid) == [p1.name])
        assert len(p1.games()) == 1 and len(p2.games()) == 1

    def test_streak_third_win_four_points(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        winner = None
        got = []
        for n in (1, 2, 3):
            room_id, p1, p2 = next_game([a, b], n)
            # Renkler sirayla degisir; ayni oyuncu her oyunu (P1 ya da P2 olarak) kazanir
            winner = winner or p1
            play(room_id, p1.c, p2.c, P1_VERTICAL_WIN if p1 is winner else P2_VERTICAL_WIN)
            assert wait_until(lambda n=n, w=winner: len(w.c.events('game_over')) >= n)
            got.append(winner.c.events('game_over')[n - 1]['arena']['points'][winner.name])
        assert got == [2, 2, 4]
        assert standings(database, tid)[winner.name]['streak'] == 3

    def test_draw_scores_one(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        play(room_id, p1.c, p2.c, DRAW_SEQUENCE)
        over = p1.c.wait_for('game_over')
        assert over['winner'] is None
        assert over['arena']['points'] == {p1.name: 1, p2.name: 1}
        rows = standings(database, tid)
        assert rows[p1.name]['score'] == 1 and rows[p2.name]['score'] == 1

    def test_forfeit_counts_as_win(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        move(p1.c, room_id, 3, 1)
        p2.c.wait_for('move_made')
        p2.c.emit('leave_game', {'room_id': room_id})
        over = p1.c.wait_for('game_over')
        assert over['reason'] == 'forfeit'
        assert over['arena']['points'] == {p1.name: 2, p2.name: 0}
        rows = standings(database, tid)
        assert rows[p1.name]['recent'] == 'W' and rows[p2.name]['recent'] == 'L'
        assert queue_names(server, tid) == [p1.name]   # ayrilan kuyruga donmez

    def test_first_move_abort_no_score_and_pauses_culprit(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        arena_env['mono'].advance(DELAY + ABORT + NET + 0.5)
        assert server.enforce_move_deadlines() == 1
        assert p1.c.wait_for('game_over')['reason'] == 'aborted'
        rows = standings(database, tid)
        assert rows[p1.name]['paused'] is True and rows[p2.name]['paused'] is False
        assert all(r['games_played'] == 0 and r['score'] == 0 for r in rows.values())
        assert database.tournament_games(tid) == []
        assert queue_names(server, tid) == [p2.name]

    def test_p2_timeout_without_moving_pauses_p2(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        move(p1.c, room_id, 3, 1)
        p2.c.wait_for('move_made')
        arena_env['mono'].advance(1000)
        assert server.enforce_move_deadlines() == 1
        over = p1.c.wait_for('game_over')
        assert over['detail'] == 'timeout' and over['arena']['points'] == {p1.name: 2, p2.name: 0}
        rows = standings(database, tid)
        assert rows[p2.name]['paused'] is True and rows[p1.name]['paused'] is False
        assert wait_until(lambda: queue_names(server, tid) == [p1.name])

    def test_no_rematch_in_arena(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        with server.ARENAS_LOCK:
            server.ARENAS[tid]['pairing'] = False   # yeniden eslesme olmasin, oda incelensin
        play(room_id, p1.c, p2.c, P1_VERTICAL_WIN)
        p1.c.wait_for('game_over')
        for p in (p1, p2):
            p.c.clear()
            p.c.emit('rematch_request', {'room_id': room_id})
        for p in (p1, p2):
            p.c.pull()
            assert p.c.events('rematch_offered') == [] and p.c.events('game_start') == []
            assert p.c.events('error') == []
        assert server.GAMES[room_id]['game_no'] == 1

    def test_avoid_immediate_rematch_with_three_players(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        c = Player(sio, http, 'carol')
        c.join(tid)
        assert queue_names(server, tid) == ['carol']
        play(room_id, p1.c, p2.c, P1_VERTICAL_WIN)
        p1.c.wait_for('game_over')
        assert wait_until(lambda: len(c.games()) == 1)
        opponent = c.games()[0]['opponent_info']['username']
        loner = p2 if opponent == p1.name else p1
        assert opponent in (p1.name, p2.name)
        assert queue_names(server, tid) == [loner.name]   # eski rakibiyle art arda eslesmedi
        assert len(loner.games()) == 1

    def test_arena_player_cannot_quick_match(self, server, sio, http, database, arena_env):
        tid = make_tournament(database, http)
        arena_env['tick'](T0)
        a = Player(sio, http, 'alice')
        a.join(tid)
        assert queue_names(server, tid) == ['alice']
        a.c.emit('quick_match_join', {'token': a.token})
        assert a.c.wait_for('error')['code'] == 'already_in_game'
        a.c.clear()
        a.c.emit('create_game', {'token': a.token})
        assert a.c.wait_for('error')['code'] == 'already_in_game'
        assert server.QUICK_QUEUE == [] and queue_names(server, tid) == ['alice']

    def test_joining_second_queue_pauses_first(self, server, sio, http, database, arena_env):
        t1 = make_tournament(database, http, creator='host1')
        t2 = make_tournament(database, http, creator='host2')
        arena_env['tick'](T0)
        a = Player(sio, http, 'alice')
        a.join(t1)
        assert queue_names(server, t1) == ['alice']
        a.join(t2)
        assert queue_names(server, t1) == [] and queue_names(server, t2) == ['alice']
        assert standings(database, t1)['alice']['paused'] is True
        assert standings(database, t2)['alice']['paused'] is False

    def test_pause_leaves_queue_and_resume_rejoins(self, server, sio, http, database, arena_env):
        tid = make_tournament(database, http)
        arena_env['tick'](T0)
        a = Player(sio, http, 'alice')
        a.join(tid)
        a.c.emit('arena_pause', {'token': a.token, 'tournament_id': tid})
        assert a.c.wait_for('arena_standings')
        assert wait_until(lambda: queue_names(server, tid) == [])
        a.c.emit('arena_resume', {'token': a.token, 'tournament_id': tid})
        assert wait_until(lambda: queue_names(server, tid) == ['alice'])

    def test_game_in_progress_at_end_still_scores(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        arena_env['tick'](T0 + timedelta(minutes=15))
        assert server.ARENAS[tid]['pairing'] is False
        play(room_id, p1.c, p2.c, P1_VERTICAL_WIN)
        assert p1.c.wait_for('game_over')['arena']['points'][p1.name] == 2
        assert standings(database, tid)[p1.name]['score'] == 2
        assert queue_names(server, tid) == []
        assert len(p1.games()) == 1 and len(p2.games()) == 1
        arena_env['tick'](T0 + timedelta(minutes=15, seconds=1))
        assert database.get_tournament(tid)['status'] == 'finished'

    def test_no_pairing_after_end(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        next_game([a, b], 1)
        arena_env['tick'](T0 + timedelta(minutes=15))   # oyun suruyor: eslestirme durur
        late = [Player(sio, http, n) for n in ('carol', 'dave')]
        for p in late:
            p.join(tid)
        assert queue_names(server, tid) == []
        assert all(p.games() == [] for p in late)

    def test_tournament_game_recorded_with_tournament_id(self, server, sio, http, database, arena_env):
        tid, (a, b) = self._start_two(server, sio, http, database, arena_env)
        room_id, p1, p2 = next_game([a, b], 1)
        play(room_id, p1.c, p2.c, P1_VERTICAL_WIN)
        p1.c.wait_for('game_over')
        games = database.tournament_games(tid)
        assert len(games) == 1
        g = games[0]
        assert (g['player1'], g['player2'], g['winner']) == (p1.name, p2.name, p1.name)
        assert g['moves'] == P1_VERTICAL_WIN
