"""Arena turnuvasi saf mantik testleri."""

from datetime import datetime, timedelta

from arena import (DURATIONS, FINISH_GRACE, START_WAIT, lifecycle_action, pick_pair, score_result, sort_standings,
                   validate_create)

T0 = datetime(2026, 1, 1, 12, 0, 0)


def test_score_win_streak():
    assert score_result('W', 0) == (2, 1)
    assert score_result('W', 1) == (2, 2)
    assert score_result('W', 2) == (4, 3)


def test_score_draw_and_loss():
    assert score_result('D', 0) == (1, 0)
    assert score_result('D', 1) == (1, 0)
    assert score_result('D', 2) == (2, 0)
    assert score_result('L', 5) == (0, 0)


def test_score_unknown_outcome():
    import pytest
    with pytest.raises(ValueError):
        score_result('X', 0)


def _row(name, score, games, rating, streak=0):
    return {'username': name, 'rating': rating, 'score': score, 'games_played': games,
            'streak': streak, 'paused': False, 'recent': []}


def test_sort_standings_tiebreaks():
    rows = [
        _row('low_rating', 6, 4, 1000),
        _row('top', 8, 3, 900, streak=2),
        _row('more_games', 6, 5, 800),
        _row('high_rating', 6, 4, 1200),
    ]
    snapshot = [dict(r) for r in rows]
    out = sort_standings(rows)
    assert [r['username'] for r in out] == ['top', 'more_games', 'high_rating', 'low_rating']
    assert [r['rank'] for r in out] == [1, 2, 3, 4]
    assert [r['on_fire'] for r in out] == [True, False, False, False]
    assert rows == snapshot  # girdi degismez


def test_pick_pair_avoids_last_opponent():
    assert pick_pair(['a', 'b', 'c'], {'a': 'b', 'b': 'a'}) == ('a', 'c')


def test_pick_pair_falls_back_to_last_opponent():
    assert pick_pair(['a', 'b'], {'a': 'b', 'b': 'a'}) == ('a', 'b')


def test_pick_pair_needs_two():
    assert pick_pair(['a'], {}) is None
    assert pick_pair([], {}) is None


def test_lifecycle():
    starts = T0
    ends = T0 + timedelta(minutes=30)
    started = T0
    # scheduled
    assert lifecycle_action('scheduled', T0 - timedelta(seconds=1), starts, ends, None, 0, 0) is None
    assert lifecycle_action('scheduled', T0, starts, ends, None, 0, 0) == 'start'
    # running, az oyuncu
    assert lifecycle_action('running', T0 + START_WAIT, starts, ends, started, 1, 0) == 'cancel'
    assert lifecycle_action('running', T0 + START_WAIT - timedelta(seconds=1), starts, ends, started, 1, 0) is None
    assert lifecycle_action('running', T0 + START_WAIT, starts, ends, started, 2, 0) is None
    # sure doldu
    assert lifecycle_action('running', ends, starts, ends, started, 2, 1) == 'stop_pairing'
    assert lifecycle_action('running', ends, starts, ends, started, 2, 0) == 'finish'
    assert lifecycle_action('running', ends + FINISH_GRACE, starts, ends, started, 2, 3) == 'finish'
    # diger durumlar
    assert lifecycle_action('finished', ends, starts, ends, started, 2, 0) is None


def test_validate_create():
    for d in DURATIONS:
        assert validate_create(d, 5, T0) == (T0 + timedelta(minutes=5), None)
    assert validate_create(20, 0, T0) == (None, 'bad_duration')
    assert validate_create(True, 0, T0) == (None, 'bad_duration')
    assert validate_create(15, 0, T0) == (T0, None)
    assert validate_create(15, 1440, T0) == (T0 + timedelta(minutes=1440), None)
    assert validate_create(15, 1441, T0) == (None, 'bad_start')
    assert validate_create(15, -5, T0) == (None, 'bad_start')
    assert validate_create(15, True, T0) == (None, 'bad_start')
    assert validate_create(15, '5', T0) == (None, 'bad_start')
