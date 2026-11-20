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
Q = [2, 2, 2, 2, 2, 2, -2]          # sutun 6 yanlis, digerleri dogru


class FakeOracle:
    """tuple(moves) -> skor listesi; tanimsiz pozisyon varsayilan (karisik) sayilir."""

    def __init__(self, table=None, default=None):
        self.table = table or {}
        self.default = default if default is not None else MIXED

    def scores(self, moves):
        return self.table.get(tuple(moves), self.default)

    def close(self):
        pass


def _quiet(n):
    """Hicbir oneki aninda kazanma/engelleme icermeyen, yalnizca 0..5 sutunlu yasal hamle dizisi."""
    heights = [0] * 7
    seq = []

    def dfs():
        if len(seq) == n:
            return True
        for c in (0, 1, 2, 3, 4, 5):
            if heights[c] >= 6:
                continue
            seq.append(c)
            heights[c] += 1
            if not cc.is_tactical_position(seq, len(seq) % 2) and dfs():
                return True
            seq.pop()
            heights[c] -= 1
        return False

    assert dfs(), n
    return list(seq)


def test_critical_moves_skips_book_and_forced():
    moves = _quiet(8)
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
    """user player1; her oyunda plies_each yarim hamle (sessiz hamleler)."""
    mv = _quiet(plies_each)
    return [{'game_id': i, 'player1': user, 'player2': 'rakip', 'winner': user,
             'moves': list(mv), 'end_reason': 'connect4'} for i in range(n_games)]


def test_flag_requires_thresholds():
    ev = cc.evaluate_player
    # 2 oyun, 20 kritik: yetersiz oyun (24 hamle -> ply 4..22 cift = 10 kritik/oyun)
    r = ev(FakeOracle(default=Q), _games('a', 2, 24), 'a')
    assert r['games'] == 2 and r['critical'] == 20 and r['flagged'] is False
    # 3 oyun, 19 kritik (6+6+7)
    g = _games('a', 2, 16) + _games('a', 1, 17)
    r = ev(FakeOracle(default=Q), g, 'a')
    assert r['games'] == 3 and r['critical'] == 19 and r['flagged'] is False
    # 3 oyun, 20 kritik, hepsi dogru (7+7+6)
    g = _games('a', 2, 18) + _games('a', 1, 16)
    r = ev(FakeOracle(default=Q), g, 'a')
    assert r['games'] == 3 and r['critical'] == 20 and r['correct'] == 20 and r['flagged'] is True
    # 3 oyun, 20 kritik, bir pozisyonda secilen sutun yanlis
    mv = g[0]['moves']
    wrong = [2] * 7
    wrong[mv[4]] = -2
    r = ev(FakeOracle({tuple(mv[:4]): wrong}, Q), g, 'a')
    assert r['critical'] == 20 and r['correct'] < 20 and r['flagged'] is False


def test_honest_short_games_not_flagged():
    games = _games('a', 5, 4)   # sadece kitap hamleleri
    r = cc.evaluate_player(FakeOracle(), games, 'a')
    assert r == {'games': 5, 'critical': 0, 'correct': 0, 'flagged': False}


def test_player2_plies_attributed_to_player2():
    g = [{'game_id': 1, 'player1': 'x', 'player2': 'b', 'winner': 'b',
          'moves': _quiet(7), 'end_reason': 'connect4'}]
    # ply 4,6 player1 ; ply 5 player2
    assert cc.evaluate_player(FakeOracle(default=Q), g, 'x')['critical'] == 2
    assert cc.evaluate_player(FakeOracle(default=Q), g, 'b')['critical'] == 1


# ---- Adil rapor: tek hamlelik taktikler kritik sayilmaz ----

def test_immediate_win_position_excluded():
    # p1: 0,1,2 alt satirda -> sirasi gelen p1'in 3. sutunda aninda galibiyeti var
    moves = [0, 5, 1, 5, 2, 4]
    plies = [p for p, _ in cc.critical_moves(FakeOracle(), moves + [3])]
    assert plies == [4]    # ply 5 (engelleme zorunlu) ve ply 6 (aninda galibiyet) disarida


def test_must_block_position_excluded():
    # p2 6. sutunda uc tas dizdi; p1 engellemek zorunda
    moves = [0, 6, 2, 6, 4, 6]
    plies = [p for p, _ in cc.critical_moves(FakeOracle(), moves + [6])]
    assert 6 not in plies and plies == [4, 5]


def test_normal_critical_position_still_counted():
    moves = _quiet(5)
    assert cc.critical_moves(FakeOracle(default=Q), moves) == [(4, True)]


# ---- Adil rapor: "tehdidin altina oynama" kararlari kritik sayilmaz ----

def _hands_win(prefix, col):
    """prefix'te sirasi gelen 'col'a oynarsa rakibin aninda galibiyeti olur mu?"""
    return cc.has_immediate_win(cc._grid(prefix + [col]), 1 - len(prefix) % 2)


def _under_threat_position():
    """Sessiz (taktik olmayan) bir pozisyon: en az bir sutun rakibe aninda galibiyet verir,
    en az iki yasal sutun vermez. (hamleler, veren sutunlar, vermeyen sutunlar)."""
    heights = [0] * 7
    seq = []
    found = []

    def dfs(depth):
        if len(seq) >= cc.BOOK_PLIES + 1 and not cc.is_tactical_position(seq, len(seq) % 2):
            legal = [c for c in range(7) if heights[c] < 6]
            hand = [c for c in legal if _hands_win(seq, c)]
            safe = [c for c in legal if c not in hand]
            if hand and len(safe) >= 2:
                found.append((list(seq), hand, safe))
                return True
        if depth == 0:
            return False
        for c in range(7):
            if heights[c] >= 6:
                continue
            seq.append(c)
            heights[c] += 1
            if not cc.is_tactical_position(seq, len(seq) % 2) and dfs(depth - 1):
                return True
            seq.pop()
            heights[c] -= 1
        return False

    assert dfs(12)
    return found[0]


def test_losing_only_by_handing_immediate_win_not_critical():
    prefix, hand, safe = _under_threat_position()
    scores = [None] * 7
    for c in range(7):
        if c in hand:
            scores[c] = -2          # tek kaybettiren: tehdidin altina oynamak
        elif c in safe:
            scores[c] = 2
    oracle = FakeOracle({tuple(prefix): scores}, FORCED)
    res = cc.critical_moves(oracle, prefix + [safe[0]])
    assert len(prefix) not in [p for p, _ in res]


def test_losing_move_without_immediate_reply_still_critical():
    prefix, hand, safe = _under_threat_position()
    scores = [None] * 7
    for c in range(7):
        if c in hand:
            scores[c] = -2
        elif c in safe:
            scores[c] = 2
    scores[safe[1]] = -4            # derin kayip: aninda cevap yok, karar gercekten kritik
    oracle = FakeOracle({tuple(prefix): scores}, FORCED)
    assert cc.critical_moves(oracle, prefix + [safe[0]]) == [(len(prefix), True)]
    assert cc.critical_moves(oracle, prefix + [safe[1]]) == [(len(prefix), False)]


# ---- Hamle dogrulama ----

@pytest.mark.parametrize('bad', [[0] * 8, [0, 1, 2, 3, 9], [0, 1, 2, 3, -1], [0, 1, 2, 3, '4'], [0, 1, 2, 3, 1.5]])
def test_invalid_moves_game_skipped(bad, capsys):
    good = _games('a', 1, 10)[0]
    broken = dict(good, game_id=99, moves=bad)
    r = cc.evaluate_player(FakeOracle(default=Q), [broken, good], 'a')
    assert r['games'] == 1
    assert '99' in capsys.readouterr().err


def test_valid_moves_helper():
    assert cc.valid_moves([0, 1, 2]) is True
    assert cc.valid_moves([0] * 6) is True
    assert cc.valid_moves([0] * 7) is False
    assert cc.valid_moves([7]) is False


# ---- Cozucu saglamligi ----

class _FakeProc:
    def __init__(self, line):
        self.line = line
        self.written = []
        self.stdin = self
        self.stdout = self

    def write(self, s):
        self.written.append(s)

    def flush(self):
        pass

    def readline(self):
        return self.line


def _oracle_with(line):
    o = cc.Oracle.__new__(cc.Oracle)
    o.proc = _FakeProc(line)
    o.cache = {}
    return o


@pytest.mark.parametrize('line', ['', '\n', '1 1 2 3', '1 1 2 3 4 5 6 7 8'])
def test_oracle_bad_output_raises_and_not_cached(line):
    o = _oracle_with(line)
    with pytest.raises(RuntimeError):
        o.scores([0])
    assert o.cache == {}


def test_oracle_good_output_parsed():
    o = _oracle_with('1 1 2 -1000 4 5 6 7\n')
    assert o.scores([0]) == [1, 2, None, 4, 5, 6, 7]
    o2 = _oracle_with('1 2 3 4 5 6 7\n')
    assert o2.scores([]) == [1, 2, 3, 4, 5, 6, 7]


def test_oracle_started_with_minimal_env(monkeypatch):
    seen = {}

    def fake_popen(cmd, **kw):
        seen.update(kw)
        return _FakeProc('')

    monkeypatch.setenv('ARENA_CHECK_SECRET', 'zzz')
    monkeypatch.setattr(cc.os.path, 'exists', lambda p: True)
    monkeypatch.setattr(cc.subprocess, 'Popen', fake_popen)
    cc.Oracle('d')
    assert set(seen['env']) <= {'PATH'}
    assert 'zzz' not in str(seen['env'])


# ---- main akisi ----

@pytest.fixture
def env(monkeypatch):
    calls = {'gh': [], 'post': [], 'get': []}
    flagged_games = _games('cheater', 3, 17)   # cheater 7 kritik/oyun, rakip 6 (< 20)

    def fake_get(url, timeout=60):
        calls['get'].append((url, timeout))
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
    monkeypatch.setattr(cc, 'Oracle', lambda solver_dir: FakeOracle(default=Q))
    monkeypatch.setattr(cc.time, 'sleep', lambda s: None)
    monkeypatch.setenv('ARENA_CHECK_SECRET', 's3cret')
    return calls


TITLE = "Arena #7: cheater kritik hamlelerin %100'ü"


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
    assert creates[0][creates[0].index('--title') + 1] == TITLE
    assert env['post'] == ['http://x/tournaments/7/checked']


def test_dedup_search_quotes_title(env):
    cc.main(['--server', 'http://x', '--solver-dir', 'd'])
    lst = [a for a in env['gh'] if a[:2] == ['issue', 'list']][0]
    assert lst[lst.index('--search') + 1] == '"%s" in:title' % TITLE


def test_existing_issue_deduped(env, monkeypatch):
    def fake_gh(args):
        env['gh'].append(list(args))
        return '[{"title": "%s"}]' % TITLE if args[:2] == ['issue', 'list'] else ''

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


def test_solver_failure_leaves_unchecked(env, monkeypatch):
    class Dead(FakeOracle):
        def scores(self, moves):
            raise RuntimeError('cozucu cevap vermedi')

    monkeypatch.setattr(cc, 'Oracle', lambda solver_dir: Dead())
    assert cc.main(['--server', 'http://x', '--solver-dir', 'd']) != 0
    assert env['post'] == []


def test_warmup_retries_first_call(env, monkeypatch):
    attempts = []
    sleeps = []

    def flaky(url, timeout=60):
        env['get'].append((url, timeout))
        if url.endswith('/tournaments/unchecked'):
            attempts.append(timeout)
            if len(attempts) < 3:
                raise TimeoutError('uyuyor')
            return {'tournament_ids': [7]}
        return {'games': _games('cheater', 3, 17)}

    monkeypatch.setattr(cc, 'http_get_json', flaky)
    monkeypatch.setattr(cc.time, 'sleep', lambda s: sleeps.append(s))
    assert cc.main(['--server', 'http://x', '--solver-dir', 'd', '--dry-run']) == 0
    assert attempts == [90, 90, 90]
    assert len(sleeps) == 2
    games_call = [t for u, t in env['get'] if u.endswith('/games')]
    assert games_call == [60]


def test_warmup_gives_up_after_four_tries(env, monkeypatch):
    attempts = []

    def dead(url, timeout=60):
        attempts.append(url)
        raise TimeoutError('uyuyor')

    monkeypatch.setattr(cc, 'http_get_json', dead)
    assert cc.main(['--server', 'http://x', '--solver-dir', 'd']) != 0
    assert len(attempts) == 4
    assert env['post'] == []
