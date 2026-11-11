"""REST API testleri: kayit, giris, profil, liderlik tablosu, mac gecmisi, saglik."""

import pytest


def signup(http, username="alice", password="pw123456"):
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
        {}, {'username': 'alice'}, {'password': 'pw123456'},
        {'username': '', 'password': 'pw123456'}, {'username': '   ', 'password': 'pw123456'},
        {'username': 123, 'password': 'pw123456'}, {'username': 'alice', 'password': ['x']},
    ])
    def test_missing_or_wrong_type_fields(self, http, database, body):
        assert http.post('/signup', json=body).status_code == 400

    @pytest.mark.parametrize("username, password", [
        ("ab", "pw123456"),                 # kisa kullanici adi
        ("a" * 21, "pw123456"),             # uzun kullanici adi
        ("bad name", "pw123456"),           # bosluk
        ("<script>", "pw123456"),           # gecersiz karakter
        ("Misafir_42", "pw123456"),         # misafir on eki ayrilmis
        ("alice", "pw"),                 # kisa sifre
        ("alice", "pw12345"),            # 7 karakter: sinirin bir altinda
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
        r = http.post('/login', json={'username': 'alice', 'password': 'pw123456'})
        assert r.status_code == 200
        user = r.get_json()['user']
        assert user['username'] == 'alice' and user['rating'] == 1200
        assert 'password_hash' not in user

    def test_username_is_trimmed(self, http, database):
        signup(http)
        assert http.post('/login', json={'username': '  alice ', 'password': 'pw123456'}).status_code == 200

    def test_wrong_password(self, http, database):
        signup(http)
        assert http.post('/login', json={'username': 'alice', 'password': 'x'}).status_code == 401

    def test_missing_fields(self, http, database):
        assert http.post('/login', json={}).status_code == 400

    def test_existing_short_password_still_logs_in(self, http, database):
        """Uzunluk kurali sadece kayitta uygulanir; eski hesaplar kilitlenmez."""
        database.create_user("eski", "abc")
        assert signup(http, "yeni", "abc").status_code == 400
        assert http.post('/login', json={'username': 'eski', 'password': 'abc'}).status_code == 200


def login(http, username="alice", password="pw123456"):
    return http.post('/login', json={'username': username, 'password': password})


@pytest.mark.db
class TestThrottling:
    def test_failed_logins_lock_the_username(self, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'LOGIN_MAX_FAILURES', 3)
        signup(http)
        for _ in range(3):
            assert login(http, password='wrong').status_code == 401
        r = login(http)   # dogru sifre bile kilit suresince reddedilir
        assert r.status_code == 429 and 'error' in r.get_json()
        assert 1 <= int(r.headers['Retry-After']) <= server.config.LOGIN_LOCKOUT_SECONDS
        assert r.get_json()['retry_after'] == int(r.headers['Retry-After'])

    def test_lockout_is_per_username(self, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'LOGIN_MAX_FAILURES', 2)
        signup(http, 'alice')
        signup(http, 'bob')
        for _ in range(2):
            login(http, 'alice', 'wrong')
        assert login(http, 'alice').status_code == 429
        assert login(http, 'bob').status_code == 200

    def test_success_resets_failure_count(self, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'LOGIN_MAX_FAILURES', 3)
        signup(http)
        for _ in range(3):
            assert login(http, password='wrong').status_code == 401
            assert login(http, password='wrong').status_code == 401
            assert login(http).status_code == 200

    def test_lockout_ends_when_window_passes(self, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'LOGIN_MAX_FAILURES', 1)
        signup(http)
        assert login(http, password='wrong').status_code == 401
        assert login(http).status_code == 429
        real_time = server.time.time
        monkeypatch.setattr(server.time, 'time', lambda: real_time() + server.config.LOGIN_LOCKOUT_SECONDS + 1)
        assert login(http).status_code == 200

    def test_locked_login_does_not_check_password(self, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'LOGIN_MAX_FAILURES', 1)
        signup(http)
        login(http, password='wrong')
        monkeypatch.setattr(server.db, 'verify_user', lambda *a: pytest.fail("PBKDF2 calisti"))
        assert login(http).status_code == 429

    def test_ip_limit_covers_login_and_signup(self, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'AUTH_IP_MAX_REQUESTS', 3)
        assert signup(http).status_code == 201
        assert login(http).status_code == 200
        assert http.post('/login', json={}).status_code == 400     # gecersiz istek de sayilir
        for r in (login(http), signup(http, 'bob')):
            assert r.status_code == 429 and int(r.headers['Retry-After']) >= 1
        assert http.get('/leaderboard').status_code == 200         # diger uclar etkilenmez

    def test_ip_limit_ignores_forwarded_header(self, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'AUTH_IP_MAX_REQUESTS', 1)
        assert signup(http).status_code == 201
        r = http.post('/login', json={'username': 'alice', 'password': 'pw123456'},
                      headers={'X-Forwarded-For': '203.0.113.9'})
        assert r.status_code == 429

    def test_zero_disables_limits(self, http, server, database, monkeypatch):
        monkeypatch.setattr(server.config, 'LOGIN_MAX_FAILURES', 0)
        monkeypatch.setattr(server.config, 'AUTH_IP_MAX_REQUESTS', 0)
        signup(http)
        for _ in range(10):
            assert login(http, password='wrong').status_code == 401
        assert login(http).status_code == 200


class TestAttemptLimiter:
    def test_counts_within_window_and_reports_wait(self, server):
        limiter = server.AttemptLimiter()
        assert [limiter.hit('k', 2, 60) for _ in range(2)] == [0, 0]
        assert 1 <= limiter.hit('k', 2, 60) <= 60
        assert limiter.hit('other', 2, 60) == 0
        limiter.reset('k')
        assert limiter.hit('k', 2, 60) == 0

    def test_memory_is_bounded(self, server, monkeypatch):
        monkeypatch.setattr(server.AttemptLimiter, 'MAX_KEYS', 50)
        limiter = server.AttemptLimiter()
        for i in range(500):
            limiter.hit(f'user{i}', 5, 60)
        assert len(limiter._attempts) <= 50
        assert 'user499' in limiter._attempts      # en yeni anahtarlar korunur

    def test_expired_keys_are_pruned_first(self, server, monkeypatch):
        monkeypatch.setattr(server.AttemptLimiter, 'MAX_KEYS', 10)
        limiter = server.AttemptLimiter()
        for i in range(10):
            limiter.hit(f'old{i}', 5, 60)
        real_time = server.time.time
        monkeypatch.setattr(server.time, 'time', lambda: real_time() + 61)
        limiter.hit('new', 5, 60)
        assert list(limiter._attempts) == ['new']


class TestWithoutDatabase:
    def test_auth_reports_service_unavailable(self, http, no_database):
        assert signup(http).status_code == 503
        assert http.post('/login', json={'username': 'alice', 'password': 'pw123456'}).status_code == 503

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
