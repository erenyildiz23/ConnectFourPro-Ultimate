"""scripts/arena_cheat_check.py: gece hile kontrolu (sahte oracle, sahte HTTP ve gh)."""

import importlib.util
import os

import pytest

import config

_spec = importlib.util.spec_from_file_location(
    "arena_cheat_check", os.path.join(config.PROJECT_ROOT, "scripts", "arena_cheat_check.py"))
cc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cc)

MIXED = [3, 1, -2, 0, 0, 0, 0]      # isaretler karisik -> kritik
FORCED = [1, 2, 3, 1, 2, 3, 1]      # hepsi ayni isaret -> zorunlu


class FakeOracle:
    """tuple(moves) -> skor listesi; tanimsiz pozisyon karisik (kritik) sayilir."""

    def __init__(self, table=None, default=None):
        self.table = table or {}
        self.default = default if default is not None else MIXED

    def scores(self, moves):
        return self.table.get(tuple(moves), self.default)

    def close(self):
        pass


def test_critical_moves_skips_book_and_forced():
    moves = [3, 3, 3, 3, 3, 3, 3, 3]            # 8 yarim hamle
    table = {tuple(moves[:i]): FORCED for i in (5, 6)}  # 5 ve 6. pozisyon zorunlu
    # ilk 4 ply kritik olsa da sayilmaz
    res = cc.critical_moves(FakeOracle(table, MIXED), moves)
    assert [p for p, _ in res] == [4, 7]
    assert all(p >= cc.BOOK_PLIES for p, _ in res)


def test_correct_is_sign_preserving():
    # en iyi isaret +1; sutun 0 (+3) dogru, sutun 1 (+1) dogru, sutun 2 (-2) yanlis, sutun 3 (0) yanlis
    moves = [0, 0, 0, 0]
    for col, expected in ((0, True), (1, True), (2, False), (3, False)):
        res = cc.critical_moves(FakeOracle(), moves + [col])
        assert res == [(4, expected)]
    # tum seceneklerin en iyisi beraberlik (0): sutun 3 (0) dogru, sutun 2 (-2) yanlis
    draw = FakeOracle(default=[None, 0, -2, 0, None, None, None])
    assert cc.critical_moves(draw, moves + [3]) == [(4, True)]
    assert cc.critical_moves(draw, moves + [2]) == [(4, False)]


def _games(user, n_games, plies_each):
    """user player1; her oyunda plies_each yarim hamle; hepsi MIXED varsayilan."""
    return [{'game_id': i, 'player1': user, 'player2': 'rakip', 'winner': user,
             'moves': [0] * plies_each, 'end_reason': 'connect4'} for i in range(n_games)]


def test_flag_requires_thresholds():
    # oyuncu player1: ply 4,6,8,... ; plies_each=N -> kritik ply sayisi
    ev = cc.evaluate_player
    # 2 oyun, 25 kritik (oyun basina 12-13): yetersiz oyun
    games = _games('a', 2, 4 + 2 * 13)   # ply 4..28 even: 13 kritik
    r = ev(FakeOracle(), games, 'a')
    assert r['games'] == 2 and r['critical'] == 26 and r['flagged'] is False
    # 3 oyun, 19 kritik
    g = _games('a', 2, 4 + 2 * 6)          # 6 kritik her biri
    g += _games('a', 1, 4 + 2 * 7 - 1)     # 7 ply... 6 kritik? hesaplayalim
    # ply 4..(4+2*7-2)=16 -> even plies 4,6,..,16 = 7 ; son oyun 4+13=17 yarim hamle -> plies 0..16 -> 7 kritik
    r = ev(FakeOracle(), g, 'a')
    assert r['games'] == 3 and r['critical'] == 19 and r['flagged'] is False
    # 3 oyun, 20 kritik, hepsi dogru
    g = _games('a', 2, 4 + 2 * 7) + _games('a', 1, 4 + 2 * 6)   # 7+7+6 = 20
    r = ev(FakeOracle(), g, 'a')
    assert r['games'] == 3 and r['critical'] == 20 and r['correct'] == 20 and r['flagged'] is True
    # 3 oyun, 20 kritik, biri yanlis (sutun 0 skoru -1 olan tek pozisyon)
    table = {tuple([0] * 4): [-1, 1, 1, 1, 1, 1, 1]}
    r = ev(FakeOracle(table), g, 'a')
    assert r['critical'] == 20 and r['correct'] < 20 and r['flagged'] is False


def test_honest_short_games_not_flagged():
    games = _games('a', 5, 4)   # sadece kitap hamleleri
    r = cc.evaluate_player(FakeOracle(), games, 'a')
    assert r == {'games': 5, 'critical': 0, 'correct': 0, 'flagged': False}


def test_player2_plies_attributed_to_player2():
    g = [{'game_id': 1, 'player1': 'x', 'player2': 'b', 'winner': 'b',
          'moves': [0] * 7, 'end_reason': 'connect4'}]
    # ply 4,6 player1 ; ply 5 player2
    assert cc.evaluate_player(FakeOracle(), g, 'x')['critical'] == 2
    assert cc.evaluate_player(FakeOracle(), g, 'b')['critical'] == 1


@pytest.fixture
def env(monkeypatch):
    calls = {'gh': [], 'post': []}
    flagged_games = _games('cheater', 3, 17)   # cheater 7 kritik/oyun, rakip 6 (< 20)

    def fake_get(url):
        if url.endswith('/tournaments/unchecked'):
            return {'tournament_ids': [7]}
        if url.endswith('/tournaments/7/games'):
            return {'games': flagged_games}
        raise AssertionError(url)

    def fake_gh(args):
        calls['gh'].append(list(args))
        return '[]'

    def fake_post(url, secret):
        calls['post'].append(url)

    monkeypatch.setattr(cc, 'http_get_json', fake_get)
    monkeypatch.setattr(cc, 'run_gh', fake_gh)
    monkeypatch.setattr(cc, 'http_post_checked', fake_post)
    monkeypatch.setattr(cc, 'Oracle', lambda solver_dir: FakeOracle())
    monkeypatch.setenv('ARENA_CHECK_SECRET', 's3cret')
    return calls


def test_dry_run_creates_no_issue(env, capsys):
    rc = cc.main(['--server', 'http://x', '--solver-dir', 'd', '--dry-run'])
    assert rc == 0
    assert not any(a[:2] == ['issue', 'create'] for a in env['gh'])
    assert env['post'] == []
    out = capsys.readouterr().out
    assert 'cheater' in out and 's3cret' not in out


def test_issue_created_then_marked(env):
    rc = cc.main(['--server', 'http://x', '--solver-dir', 'd'])
    assert rc == 0
    creates = [a for a in env['gh'] if a[:2] == ['issue', 'create']]
    assert len(creates) == 1
    title = creates[0][creates[0].index('--title') + 1]
    assert title == "Arena #7: cheater kritik hamlelerin %100'\u00fc"
    assert env['post'] == ['http://x/tournaments/7/checked']


def test_existing_issue_deduped(env, monkeypatch):
    title = "Arena #7: cheater kritik hamlelerin %100'\u00fc"

    def fake_gh(args):
        env['gh'].append(list(args))
        return '[{"title": "%s"}]' % title if args[:2] == ['issue', 'list'] else ''

    monkeypatch.setattr(cc, 'run_gh', fake_gh)
    assert cc.main(['--server', 'http://x', '--solver-dir', 'd']) == 0
    assert not any(a[:2] == ['issue', 'create'] for a in env['gh'])
    assert env['post'] == ['http://x/tournaments/7/checked']


def test_gh_failure_leaves_unchecked(env, monkeypatch):
    def boom(args):
        if args[:2] == ['issue', 'create']:
            raise RuntimeError('gh failed')
        return '[]'

    monkeypatch.setattr(cc, 'run_gh', boom)
    assert cc.main(['--server', 'http://x', '--solver-dir', 'd']) != 0
    assert env['post'] == []
