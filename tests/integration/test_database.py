"""Veritabani katmani entegrasyon testleri (PostgreSQL). FR-01, FR-02, FR-07, FR-10."""

import hashlib

import pytest

pytestmark = pytest.mark.db


class TestUsers:
    def test_create_and_verify(self, database):
        uid = database.create_user("alice", "pw123456")
        assert isinstance(uid, int)
        user = database.verify_user("alice", "pw123456")
        assert user == {'user_id': uid, 'username': 'alice', 'rating': 1200, 'wins': 0, 'losses': 0}
        assert 'password_hash' not in user

    def test_duplicate_username_returns_none(self, database):
        assert database.create_user("alice", "a")
        assert database.create_user("alice", "b") is None
        assert database.get_user_count() == 1

    def test_wrong_password_and_unknown_user(self, database):
        database.create_user("alice", "pw123456")
        assert database.verify_user("alice", "nope") is None
        assert database.verify_user("ghost", "pw123456") is None

    def test_password_is_not_stored_in_plain_text(self, database):
        database.create_user("alice", "pw123456")
        with database.get_db_cursor() as c:
            c.execute("SELECT password_hash FROM users WHERE username = 'alice'")
            stored = c.fetchone()['password_hash']
        assert stored.startswith("pbkdf2_sha256$") and "pw123456" not in stored

    def test_legacy_account_logs_in_and_is_upgraded(self, database):
        with database.get_db_cursor() as c:
            c.execute("INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                      ("legacy", hashlib.sha256(b"old").hexdigest()))
        assert database.verify_user("legacy", "old")
        with database.get_db_cursor() as c:
            c.execute("SELECT password_hash FROM users WHERE username = 'legacy'")
            assert c.fetchone()['password_hash'].startswith("pbkdf2_sha256$")
        assert database.verify_user("legacy", "old")
        assert database.verify_user("legacy", "wrong") is None

    def test_lookup_by_name_and_id(self, database):
        uid = database.create_user("alice", "pw")
        assert database.get_user_by_username("alice")['user_id'] == uid
        assert database.get_user_by_id(uid)['username'] == "alice"
        assert database.get_user_by_username("ghost") is None


class TestEloAndGames:
    def test_elo_update_is_symmetric(self, database):
        database.create_user("alice", "pw")
        database.create_user("bob", "pw")
        result = database.update_elo_by_username("alice", "bob")
        assert result == {'winner_change': 15, 'loser_change': -15}
        alice, bob = database.get_user_by_username("alice"), database.get_user_by_username("bob")
        assert (alice['rating'], alice['wins'], alice['losses']) == (1215, 1, 0)
        assert (bob['rating'], bob['wins'], bob['losses']) == (1185, 0, 1)

    def test_elo_skipped_for_unregistered_player(self, database):
        database.create_user("alice", "pw")
        assert database.update_elo_by_username("alice", "Misafir_1") == {'winner_change': 0, 'loser_change': 0}
        assert database.get_user_by_username("alice")['rating'] == 1200

    def test_leaderboard_is_sorted(self, database):
        for name in ("a_user", "b_user", "c_user"):
            database.create_user(name, "pw")
        database.update_elo_by_username("c_user", "a_user")
        top = database.get_top_players(limit=2)
        assert [p['username'] for p in top] == ["c_user", "b_user"]

    def test_record_and_history(self, database):
        database.create_user("alice", "pw")
        database.create_user("bob", "pw")
        assert database.record_game("alice", "bob", "alice", "[0, 1, 0]")
        assert database.record_game("alice", "bob", None, "[]")                    # beraberlik
        assert database.record_game("bob", "alice", "bob", "[3]", end_reason="forfeit")
        assert not database.record_game("alice", "Misafir_1", "alice", "[]")      # misafir

        history = database.get_user_games("alice")
        assert [g['result'] for g in history] == ['loss', 'draw', 'win']
        assert history[0]['end_reason'] == 'forfeit'
        assert {g['player1'] for g in history} == {"alice", "bob"}

    def test_delete_test_users_keeps_real_accounts(self, database):
        for name in ("locust_1", "test_user_2", "bench_3", "user_real", "alice"):
            database.create_user(name, "pw")
        database.record_game("locust_1", "alice", "alice", "[]")
        assert database.delete_test_users() == 3
        remaining = {p['username'] for p in database.get_top_players(limit=10)}
        assert remaining == {"user_real", "alice"}


class TestUnavailableDatabase:
    def test_functions_return_safe_defaults(self, no_database):
        db = no_database
        assert not db.is_available()
        assert db.init_db() is False
        assert db.create_user("a", "b") is None
        assert db.verify_user("a", "b") is None
        assert db.get_user_by_username("a") is None
        assert db.get_top_players() == []
        assert db.get_user_games("a") == []
        assert db.update_elo_by_username("a", "b") == {'winner_change': 0, 'loser_change': 0}
        assert db.record_game("a", "b", "a", "[]") is False


class TestStaleConnections:
    """Sunucu tarafinda kapatilan bosta baglanti ilk sorguyu basarisiz kilmamali."""

    def _kill_pooled_backends(self, database):
        import psycopg2
        from conftest import TEST_DATABASE_URL
        admin = psycopg2.connect(TEST_DATABASE_URL)
        admin.autocommit = True
        with admin.cursor() as c:
            c.execute("SELECT count(pg_terminate_backend(pid)) FROM pg_stat_activity "
                      "WHERE datname = current_database() AND pid <> pg_backend_pid()")
            killed = c.fetchone()[0]
        admin.close()
        return killed

    def test_dead_idle_connection_is_replaced(self, database, monkeypatch):
        uid = database.create_user("alice", "pw123456")
        assert self._kill_pooled_backends(database) >= 1
        monkeypatch.setattr(database.config, "DB_PING_AFTER_SECONDS", -1)   # her zaman yokla
        for _ in range(database.config.DB_POOL_SIZE + 1):                  # havuzdaki her baglanti
            assert database.get_user_by_username("alice")['user_id'] == uid
        assert database.verify_user("alice", "pw123456")

    def test_without_ping_the_first_query_fails(self, database, monkeypatch):
        """Yoklamanin gercekten gerekli oldugunu gosterir (regresyon kaniti)."""
        database.create_user("alice", "pw123456")
        assert self._kill_pooled_backends(database) >= 1
        monkeypatch.setattr(database.config, "DB_PING_AFTER_SECONDS", 10 ** 9)   # hic yoklama
        assert database.get_user_by_username("alice") is None



class TestPoolSwitchDuringQuery:
    def test_switch_waits_for_a_running_query_and_keeps_every_slot(self, database):
        """
        Fixture'larin havuz degisimi (conftest._switch_db), baska thread'in suren sorgusunu
        (or. onceki testten kalan canli sunucu istegi) bekler. Beklemeden yapilan configure()
        o sorgunun semafor slotunu sizdirir; DB_POOL_SIZE sizintidan sonra her veritabani cagrisi
        DB_POOL_TIMEOUT bekler ve test kosusu takilir.
        """
        import threading

        from conftest import TEST_DATABASE_URL, _switch_db
        started, errors = threading.Event(), []

        def work():
            try:
                with database.get_db_cursor() as c:
                    started.set()
                    c.execute("SELECT pg_sleep(0.5)")
            except Exception as e:
                errors.append(e)
        worker = threading.Thread(target=work, daemon=True)
        worker.start()
        assert started.wait(5)
        _switch_db(TEST_DATABASE_URL)
        worker.join(5)
        assert not worker.is_alive() and errors == []
        assert database._pool_slots._value == database.config.DB_POOL_SIZE
        assert database.get_user_count() == 0       # yeni havuz calisiyor
