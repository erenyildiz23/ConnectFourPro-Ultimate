"""REST API testleri: kayit, giris, profil, liderlik tablosu, mac gecmisi, saglik."""

import pytest


def signup(http, username="alice", password="pw123"):
    return http.post('/signup', json={'username': username, 'password': password})


@pytest.mark.db
class TestSignup:
    def test_success(self, http, database):
        r = signup(http)
        assert r.status_code == 201 and isinstance(r.get_json()['user_id'], int)

    def test_duplicate(self, http, database):
        signup(http)
        assert signup(http).status_code == 409

    @pytest.mark.parametrize("body", [
        {}, {'username': 'alice'}, {'password': 'pw123'},
        {'username': '', 'password': 'pw123'}, {'username': '   ', 'password': 'pw123'},
        {'username': 123, 'password': 'pw123'}, {'username': 'alice', 'password': ['x']},
    ])
    def test_missing_or_wrong_type_fields(self, http, database, body):
        assert http.post('/signup', json=body).status_code == 400

    @pytest.mark.parametrize("username, password", [
        ("ab", "pw123"),                 # kisa kullanici adi
        ("a" * 21, "pw123"),             # uzun kullanici adi
        ("bad name", "pw123"),           # bosluk
        ("<script>", "pw123"),           # gecersiz karakter
        ("Misafir_42", "pw123"),         # misafir on eki ayrilmis
        ("alice", "pw"),                 # kisa sifre
    ])
    def test_validation(self, http, database, username, password):
        assert signup(http, username, password).status_code == 400

    def test_malformed_json(self, http, database):
        r = http.post('/signup', data='{not json', content_type='application/json')
        assert r.status_code == 400

    def test_unicode_username_allowed(self, http, database):
        assert signup(http, "ömer_çelik").status_code == 201


@pytest.mark.db
class TestLogin:
    def test_success_returns_profile_without_hash(self, http, database):
        signup(http)
        r = http.post('/login', json={'username': 'alice', 'password': 'pw123'})
        assert r.status_code == 200
        user = r.get_json()['user']
        assert user['username'] == 'alice' and user['rating'] == 1200
        assert 'password_hash' not in user

    def test_username_is_trimmed(self, http, database):
        signup(http)
        assert http.post('/login', json={'username': '  alice ', 'password': 'pw123'}).status_code == 200

    def test_wrong_password(self, http, database):
        signup(http)
        assert http.post('/login', json={'username': 'alice', 'password': 'x'}).status_code == 401

    def test_missing_fields(self, http, database):
        assert http.post('/login', json={}).status_code == 400


class TestWithoutDatabase:
    def test_auth_reports_service_unavailable(self, http, no_database):
        assert signup(http).status_code == 503
        assert http.post('/login', json={'username': 'alice', 'password': 'pw123'}).status_code == 503

    def test_health_reports_database_down(self, http, no_database):
        body = http.get('/health').get_json()
        assert body['status'] == 'healthy' and body['database'] is False

    def test_leaderboard_empty(self, http, no_database):
        assert http.get('/leaderboard').get_json() == []


@pytest.mark.db
class TestQueries:
    def test_user_profile(self, http, database):
        signup(http)
        assert http.get('/user/alice').get_json()['user']['username'] == 'alice'
        assert http.get('/user/ghost').status_code == 404

    def test_leaderboard_limit_is_clamped(self, http, database):
        for i in range(3):
            signup(http, f"player{i}")
        assert len(http.get('/leaderboard?limit=2').get_json()) == 2
        assert len(http.get('/leaderboard?limit=0').get_json()) == 1
        assert len(http.get('/leaderboard?limit=100000').get_json()) == 3

    def test_game_history(self, http, database):
        signup(http, "alice")
        signup(http, "bob")
        database.record_game("alice", "bob", "alice", "[0, 1, 0, 1, 0, 1, 0]")
        games = http.get('/user/alice/games').get_json()['games']
        assert len(games) == 1 and games[0]['result'] == 'win' and games[0]['winner'] == 'alice'
        assert http.get('/user/bob/games').get_json()['games'][0]['result'] == 'loss'
        assert http.get('/user/ghost/games').status_code == 404

    def test_health(self, http, database):
        body = http.get('/health').get_json()
        assert body == {'status': 'healthy', 'database': True, 'active_games': 0, 'connected_users': 0}
