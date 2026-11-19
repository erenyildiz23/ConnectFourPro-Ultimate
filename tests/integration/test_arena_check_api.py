"""Arena hile kontrolu uc noktalari (gece taramasi bunlari kullanir)."""

from datetime import datetime, timezone

import pytest

import config

HEADER = 'X-Arena-Check-Secret'


@pytest.fixture
def secret(monkeypatch):
    monkeypatch.setattr(config, 'ARENA_CHECK_SECRET', 's3cret-test')
    return 's3cret-test'


def make_tournament(database, status):
    for name in ('alice', 'bob'):
        database.create_user(name, 'pw123456')
    tid = database.create_tournament('alice', 15, datetime.now(timezone.utc))
    assert tid
    assert database.set_tournament_status(tid, status)
    return tid


def test_unchecked_empty_without_database(http, no_database):
    resp = http.get('/tournaments/unchecked')
    assert resp.status_code == 200
    assert resp.get_json() == {'tournament_ids': []}


def test_mark_checked_503_when_secret_unset(http, monkeypatch):
    monkeypatch.setattr(config, 'ARENA_CHECK_SECRET', None)
    resp = http.post('/tournaments/1/checked', headers={HEADER: 'anything'})
    assert resp.status_code == 503
    assert 'error' in resp.get_json()


def test_mark_checked_403_on_missing_or_wrong_secret(http, secret):
    assert http.post('/tournaments/1/checked').status_code == 403
    assert http.post('/tournaments/1/checked', headers={HEADER: 'wrong'}).status_code == 403
    assert http.post('/tournaments/1/checked', headers={HEADER: ''}).status_code == 403


@pytest.mark.db
class TestArenaCheckDb:
    def test_games_endpoint_requires_finished(self, http, database):
        assert http.get('/tournaments/9999/games').status_code == 404
        tid = make_tournament(database, 'running')
        assert http.get(f'/tournaments/{tid}/games').status_code == 409
        database.set_tournament_status(tid, 'finished')
        assert database.record_game('alice', 'bob', 'alice', '[3, 3, 4, 4, 3, 3, 4]', 'normal', tid)
        resp = http.get(f'/tournaments/{tid}/games')
        assert resp.status_code == 200
        games = resp.get_json()['games']
        assert len(games) == 1
        assert set(games[0]) == {'game_id', 'player1', 'player2', 'winner', 'moves', 'end_reason'}
        assert games[0]['winner'] == 'alice' and games[0]['moves'] == [3, 3, 4, 4, 3, 3, 4]

    def test_unchecked_list(self, http, database):
        assert http.get('/tournaments/unchecked').get_json() == {'tournament_ids': []}
        running = make_tournament(database, 'running')
        assert http.get('/tournaments/unchecked').get_json() == {'tournament_ids': []}
        database.set_tournament_status(running, 'finished')
        assert http.get('/tournaments/unchecked').get_json() == {'tournament_ids': [running]}

    def test_mark_checked_requires_secret(self, http, database, monkeypatch):
        tid = make_tournament(database, 'finished')
        url = f'/tournaments/{tid}/checked'
        monkeypatch.setattr(config, 'ARENA_CHECK_SECRET', None)
        assert http.post(url, headers={HEADER: 'x'}).status_code == 503
        monkeypatch.setattr(config, 'ARENA_CHECK_SECRET', 's3cret-test')
        assert http.post(url, headers={HEADER: 'wrong'}).status_code == 403
        assert http.get('/tournaments/unchecked').get_json() == {'tournament_ids': [tid]}
        resp = http.post(url, headers={HEADER: 's3cret-test'})
        assert resp.status_code == 200 and resp.get_json() == {'ok': True}
        assert http.get('/tournaments/unchecked').get_json() == {'tournament_ids': []}

    def test_mark_checked_unknown_and_unfinished(self, http, database, secret):
        headers = {HEADER: secret}
        assert http.post('/tournaments/9999/checked', headers=headers).status_code == 404
        tid = make_tournament(database, 'running')
        assert http.post(f'/tournaments/{tid}/checked', headers=headers).status_code == 409
