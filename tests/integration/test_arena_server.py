"""Arena turnuvasi sunucu olaylari ve REST uc noktalari."""

import pytest

from conftest import identity, login_token


def tok(http, name):
    return login_token(http, name)


def create(sio, http, name="alice", duration=15, start_in=0):
    c = sio()
    c.emit('arena_create', {'token': tok(http, name), 'duration': duration, 'start_in_minutes': start_in})
    return c


def error_code(client):
    return client.wait_for('error')['code']


def test_guest_cannot_create_arena(sio, no_database):
    c = sio()
    c.emit('arena_create', {**identity('guest1'), 'duration': 15, 'start_in_minutes': 0})
    assert error_code(c) == 'not_registered'


def test_guest_cannot_join_or_pause(sio, no_database):
    c = sio()
    for ev in ('arena_join', 'arena_pause', 'arena_resume'):
        c.emit(ev, {**identity('guest1'), 'tournament_id': 1})
        assert error_code(c) == 'not_registered'
        c.clear()


@pytest.mark.db
class TestArenaDb:
    def test_create_validates_duration_and_start(self, sio, http, database):
        t = tok(http, 'alice')
        c = sio()
        cases = [(20, 0, 'bad_duration'), ('15', 0, 'bad_duration'),
                 (15, -1, 'bad_start'), (15, 24 * 60 + 1, 'bad_start'), (15, 'x', 'bad_start')]
        for dur, start, code in cases:
            c.emit('arena_create', {'token': t, 'duration': dur, 'start_in_minutes': start})
            assert error_code(c) == code
            c.clear()
        c.emit('arena_create', {'token': t, 'duration': 30, 'start_in_minutes': 24 * 60})
        made = c.wait_for('arena_created')['tournament']
        assert made['creator'] == 'alice' and made['duration_minutes'] == 30
        assert made['status'] == 'scheduled' and made['players'] == 0
        assert isinstance(made['starts_at'], str) and isinstance(made['ends_at'], str)

    def test_creator_limit_one_active(self, sio, http, database):
        c = create(sio, http)
        c.wait_for('arena_created')
        c.emit('arena_create', {'token': tok(http, 'alice'), 'duration': 15, 'start_in_minutes': 0})
        assert error_code(c) == 'arena_limit'
        other = create(sio, http, 'bob')
        other.wait_for('arena_created')

    def test_list_and_detail_endpoints(self, sio, http, database):
        c = create(sio, http)
        tid = c.wait_for('arena_created')['tournament']['id']
        c.emit('arena_join', {'token': tok(http, 'alice'), 'tournament_id': tid})
        c.wait_for('arena_joined')
        items = http.get('/tournaments').get_json()['tournaments']
        assert [i['id'] for i in items] == [tid] and items[0]['players'] == 1
        assert set(items[0]) == {'id', 'creator', 'duration_minutes', 'starts_at', 'ends_at',
                                 'status', 'players'}
        detail = http.get(f'/tournaments/{tid}').get_json()
        assert detail['tournament']['id'] == tid
        row = detail['standings'][0]
        assert row['username'] == 'alice' and row['rank'] == 1 and row['score'] == 0
        assert set(row) == {'rank', 'username', 'score', 'games_played', 'streak', 'on_fire',
                            'paused', 'recent'}
        assert http.get('/tournaments/9999').status_code == 404

    def test_join_requires_registration(self, sio, http, database):
        c = create(sio, http)
        tid = c.wait_for('arena_created')['tournament']['id']
        g = sio()
        g.emit('arena_join', {**identity('guest1'), 'tournament_id': tid})
        assert error_code(g) == 'not_registered'
        assert http.get(f'/tournaments/{tid}').get_json()['standings'] == []

    def test_join_unknown_tournament(self, sio, http, database):
        c = sio()
        c.emit('arena_join', {'token': tok(http, 'alice'), 'tournament_id': 12345})
        assert error_code(c) == 'arena_not_found'

    def test_join_broadcasts_standings(self, sio, http, database):
        a = create(sio, http)
        tid = a.wait_for('arena_created')['tournament']['id']
        a.emit('arena_join', {'token': tok(http, 'alice'), 'tournament_id': tid})
        assert a.wait_for('arena_joined') == {'tournament_id': tid}
        a.clear()
        b = sio()
        b.emit('arena_join', {'token': tok(http, 'bob'), 'tournament_id': tid})
        b.wait_for('arena_joined')
        for client in (a, b):
            msg = client.wait_for('arena_standings')
            assert msg['tournament_id'] == tid
            assert sorted(r['username'] for r in msg['standings']) == ['alice', 'bob']

    def test_guest_can_watch_standings(self, sio, http, database):
        a = create(sio, http)
        tid = a.wait_for('arena_created')['tournament']['id']
        a.emit('arena_join', {'token': tok(http, 'alice'), 'tournament_id': tid})
        a.wait_for('arena_joined')
        g = sio()
        g.emit('arena_watch', {'tournament_id': tid})
        st = g.wait_for('arena_standings')
        assert st['tournament_id'] == tid and [r['username'] for r in st['standings']] == ['alice']
        g.emit('arena_watch', {'tournament_id': 9999})
        assert error_code(g) == 'arena_not_found'

    def test_pause_resume_updates_standings(self, sio, http, database):
        a = create(sio, http)
        tid = a.wait_for('arena_created')['tournament']['id']
        t = tok(http, 'alice')
        a.emit('arena_join', {'token': t, 'tournament_id': tid})
        a.wait_for('arena_joined')
        a.clear()
        a.emit('arena_pause', {'token': t, 'tournament_id': tid})
        assert a.wait_for('arena_standings')['standings'][0]['paused'] is True
        a.clear()
        a.emit('arena_resume', {'token': t, 'tournament_id': tid})
        assert a.wait_for('arena_standings')['standings'][0]['paused'] is False
        b = sio()
        b.emit('arena_pause', {'token': tok(http, 'bob'), 'tournament_id': tid})
        assert error_code(b) == 'arena_not_found'

    def test_join_finished_tournament_rejected(self, sio, http, database):
        a = create(sio, http)
        tid = a.wait_for('arena_created')['tournament']['id']
        database.set_tournament_status(tid, 'finished')
        a.emit('arena_join', {'token': tok(http, 'alice'), 'tournament_id': tid})
        assert error_code(a) == 'arena_over'
