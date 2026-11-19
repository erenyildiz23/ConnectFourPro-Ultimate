"""Arena turnuvasi veritabani katmani testleri (PostgreSQL)."""

from datetime import datetime, timedelta, timezone

import pytest

pytestmark = pytest.mark.db

T0 = datetime(2026, 11, 19, 12, 0, tzinfo=timezone.utc)


def _setup(database):
    database.create_user("alice", "pw")
    database.create_user("bob", "pw")
    return database.create_tournament("alice", 30, T0)


def test_create_and_get_tournament(database):
    tid = _setup(database)
    assert isinstance(tid, int)
    t = database.get_tournament(tid)
    assert t['creator'] == "alice"
    assert t['duration_minutes'] == 30
    assert t['starts_at'] == T0
    assert t['ends_at'] == T0 + timedelta(minutes=30)
    assert t['status'] == 'scheduled'
    assert t['started_at'] is None and t['cheat_checked_at'] is None
    assert database.get_tournament(9999) is None
    assert database.create_tournament("ghost", 30, T0) is None


def test_list_hides_cancelled_and_old_finished(database):
    now = T0
    database.create_user("alice", "pw")
    ids = {name: database.create_tournament("alice", 30, now - timedelta(days=d))
           for name, d in (("sched", 0), ("old", 8), ("recent", 6), ("cancel", 1))}
    database.set_tournament_status(ids["old"], 'finished')
    database.set_tournament_status(ids["recent"], 'finished')
    database.set_tournament_status(ids["cancel"], 'cancelled')
    listed = {t['id'] for t in database.list_tournaments(now)}
    assert listed == {ids["sched"], ids["recent"]}


def test_active_tournament_of_creator(database):
    tid = _setup(database)
    assert database.active_tournament_of_creator("alice") == tid
    assert database.active_tournament_of_creator("bob") is None
    database.set_tournament_status(tid, 'running', started_at=T0)
    assert database.active_tournament_of_creator("alice") == tid
    database.set_tournament_status(tid, 'finished')
    assert database.active_tournament_of_creator("alice") is None


def test_join_is_idempotent_and_unpauses(database):
    tid = _setup(database)
    assert database.join_tournament(tid, "bob")
    assert database.set_player_paused(tid, "bob", True)
    assert database.get_standings_rows(tid)[0]['paused'] is True
    assert database.join_tournament(tid, "bob")
    rows = database.get_standings_rows(tid)
    assert len(rows) == 1 and rows[0]['paused'] is False
    assert rows[0]['username'] == "bob" and rows[0]['rating'] == 1200
    assert not database.join_tournament(tid, "ghost")
    assert not database.set_player_paused(tid, "alice", True)   # uye degil


def test_apply_result_updates_score_streak_recent(database):
    tid = _setup(database)
    database.join_tournament(tid, "bob")
    for i, outcome in enumerate("WWDLWW", start=1):
        assert database.apply_tournament_result(tid, "bob", 2, i, outcome)
    row = database.get_standings_rows(tid)[0]
    assert (row['score'], row['games_played'], row['streak']) == (12, 6, 6)
    assert row['recent'] == "WDLWW" and len(row['recent']) == 5
    assert not database.apply_tournament_result(tid, "alice", 2, 1, 'W')   # uye degil


def test_record_game_with_tournament_id_and_tournament_games(database):
    tid = _setup(database)
    assert database.record_game("alice", "bob", "alice", "[3, 3, 4]", tournament_id=tid)
    assert database.record_game("alice", "bob", None, "[1]")   # turnuva disi
    games = database.tournament_games(tid)
    assert len(games) == 1
    g = games[0]
    assert (g['player1'], g['player2'], g['winner']) == ("alice", "bob", "alice")
    assert g['moves'] == [3, 3, 4] and g['end_reason'] == 'normal'


def test_mark_cheat_checked_removes_from_unchecked(database):
    tid = _setup(database)
    assert database.finished_unchecked_tournaments() == []   # henuz bitmedi
    database.set_tournament_status(tid, 'finished')
    assert database.finished_unchecked_tournaments() == [tid]
    assert database.mark_cheat_checked(tid)
    assert database.finished_unchecked_tournaments() == []
    assert database.get_tournament(tid)['cheat_checked_at'] is not None


def test_delete_test_users_removes_tournament_rows(database):
    database.create_user("locust_1", "pw")
    database.create_user("alice", "pw")
    tid = database.create_tournament("locust_1", 30, T0)
    database.join_tournament(tid, "alice")
    database.record_game("locust_1", "alice", "alice", "[]", tournament_id=tid)
    assert database.delete_test_users() == 1
    assert database.get_tournament(tid) is None
    assert database.get_user_by_username("alice") is not None
