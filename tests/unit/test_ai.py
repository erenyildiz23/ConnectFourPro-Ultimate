"""AI motoru birim testleri (FR-06: uc zorluk seviyesinde AI rakip)."""

import math
import random
import threading
import time

import pytest

from ai_vs_human import (DIFFICULTY_DEPTHS, OPENING_BOOK, SCORE_2_OPEN, SCORE_3_OPEN, SCORE_BLOCK, SCORE_TERMINAL,
                         SCORE_WIN, AIEngine)
from conftest import DRAW_SEQUENCE
from game_core import COLS, EMPTY, PLAYER1_PIECE, PLAYER2_PIECE, ConnectFourGame


def winning_moves(game, player):
    """Oyuncunun tek hamlede kazanabildigi sutunlar (sira kimde olursa olsun)."""
    result = []
    for col in game.get_valid_locations():
        g = game.clone()
        g.current_player = player
        g.make_move(col)
        if g.winner == player:
            result.append(col)
    return result


def plain_minimax(ai, game, depth, maximizing):
    """Budamasiz referans minimax: alpha-beta ayni degeri vermeli."""
    if game.check_win(ai.player_id):
        return SCORE_TERMINAL + depth
    if game.check_win(ai.opp_player_id):
        return -(SCORE_TERMINAL + depth)
    moves = game.get_valid_locations()
    if not moves:
        return 0
    if depth == 0:
        return ai.score_position(game, ai.player_id)
    values = []
    for col in moves:
        child = game.clone()
        child.make_move(col)
        values.append(plain_minimax(ai, child, depth - 1, not maximizing))
    return max(values) if maximizing else min(values)


def make_position(p1_cells, p2_cells, to_move):
    """(sutun, satir) listelerinden pozisyon kurar (yercekimi kuralina uygun olmali)."""
    g = ConnectFourGame()
    for piece, cells in ((PLAYER1_PIECE, p1_cells), (PLAYER2_PIECE, p2_cells)):
        for col, row in cells:
            g.bitboards[piece] |= 1 << (col * 7 + row)
    for col in range(COLS):
        height = sum(1 for c, _ in list(p1_cells) + list(p2_cells) if c == col)
        g.heights[col] = col * 7 + height
    g.move_count = len(p1_cells) + len(p2_cells)
    g.current_player = to_move
    assert not g.check_win(PLAYER1_PIECE) and not g.check_win(PLAYER2_PIECE)
    return g


def random_position(rng, n_moves):
    g = ConnectFourGame()
    for _ in range(n_moves):
        moves = g.get_valid_locations()
        if g.game_over or not moves:
            break
        g.make_move(rng.choice(moves))
    return g


class TestBasics:
    def test_difficulty_levels(self):
        assert DIFFICULTY_DEPTHS == {'Kolay': 2, 'Orta': 4, 'Zor': 6}

    def test_invalid_depth_rejected(self):
        with pytest.raises(ValueError):
            AIEngine(PLAYER2_PIECE, depth=0)

    @pytest.mark.parametrize("depth", [1, 2, 4])
    def test_always_returns_a_valid_move(self, depth):
        rng = random.Random(depth)
        for n in (0, 5, 15, 30):
            g = random_position(rng, n)
            if g.game_over:
                continue
            move = AIEngine(g.current_player, depth=depth).find_best_move(g)
            assert move in g.get_valid_locations()

    def test_full_board_returns_none(self):
        g = ConnectFourGame.from_moves(DRAW_SEQUENCE)
        assert AIEngine(PLAYER1_PIECE, depth=3).find_best_move(g) is None

    def test_does_not_modify_input_game(self):
        g = ConnectFourGame.from_moves([3, 3, 2])
        before = g.to_dict()
        AIEngine(PLAYER2_PIECE, depth=4).find_best_move(g)
        assert g.to_dict() == before

    def test_cancelled_search_returns_none_immediately(self):
        cancel = threading.Event()
        cancel.set()
        ai = AIEngine(PLAYER2_PIECE, depth=7)
        assert ai.find_best_move(ConnectFourGame.from_moves([3, 3, 2]), cancel_event=cancel) is None
        assert ai.nodes_evaluated == 1

    def test_cancel_stops_running_search(self):
        cancel = threading.Event()
        ai = AIEngine(PLAYER2_PIECE, depth=9, use_opening_book=False)
        result = {}
        worker = threading.Thread(target=lambda: result.update(move=ai.find_best_move(ConnectFourGame(), cancel)))
        worker.start()
        time.sleep(0.05)
        cancel.set()
        worker.join(timeout=2)
        assert not worker.is_alive() and result['move'] is None

    def test_engine_is_reusable_after_cancel(self):
        cancel = threading.Event()
        cancel.set()
        ai = AIEngine(PLAYER2_PIECE, depth=2)
        g = ConnectFourGame.from_moves([3, 3, 2])
        assert ai.find_best_move(g, cancel_event=cancel) is None
        assert ai.find_best_move(g) in g.get_valid_locations()

    def test_is_deterministic(self):
        g = ConnectFourGame.from_moves([3, 2, 4, 4, 1])
        moves = {AIEngine(PLAYER2_PIECE, depth=4).find_best_move(g) for _ in range(3)}
        assert len(moves) == 1


class TestOpeningBook:
    def test_book_move_on_empty_board(self):
        ai = AIEngine(PLAYER1_PIECE, depth=6)
        assert ai.find_best_move(ConnectFourGame()) == OPENING_BOOK[()]
        assert ai.last_move_from_book and ai.nodes_evaluated == 0

    def test_book_can_be_disabled(self):
        ai = AIEngine(PLAYER1_PIECE, depth=2, use_opening_book=False)
        ai.find_best_move(ConnectFourGame())
        assert not ai.last_move_from_book and ai.nodes_evaluated > 0


class TestTactics:
    @pytest.mark.parametrize("moves, expected", [
        ([3, 0, 3, 1, 3, 2], 3),                 # Dikey
        ([0, 0, 1, 1, 2, 2], 3),                 # Yatay (sag uc)
        ([1, 1, 2, 2, 3, 3], None),              # Yatay iki ucu acik: 0 veya 4
        ([0, 1, 1, 2, 2, 3, 2, 3, 3, 6], 3),     # Capraz /
    ], ids=["vertical", "horizontal_edge", "horizontal_open", "diagonal"])
    @pytest.mark.parametrize("depth", [1, 2, 4, 6])
    def test_takes_immediate_win(self, moves, expected, depth):
        g = ConnectFourGame.from_moves(moves)
        wins = winning_moves(g, g.current_player)
        assert wins and (expected is None or expected in wins)
        move = AIEngine(g.current_player, depth=depth).find_best_move(g)
        assert move in wins

    @pytest.mark.parametrize("depth", [2, 4, 6])
    @pytest.mark.parametrize("moves, threat", [
        ([0, 3, 1, 3, 6, 3], 3),    # P2 sutun 3'te dikey uclu -> P1 sutun 3'u kapatmali
        ([6, 0, 6, 1, 5, 2], 3),    # P2 alt satirda 0-1-2 -> P1 sutun 3'u kapatmali
    ], ids=["block_vertical", "block_horizontal"])
    def test_blocks_single_opponent_threat(self, moves, threat, depth):
        g = ConnectFourGame.from_moves(moves)
        me = g.current_player
        assert winning_moves(g, 3 - me) == [threat] and not winning_moves(g, me)  # on kosul
        assert AIEngine(me, depth=depth).find_best_move(g) == threat

    @pytest.mark.parametrize("depth", [1, 2, 4])
    def test_prefers_own_win_over_blocking(self, depth):
        # P1 sutun 0'da uclu, P2 sutun 6'da uclu; sira P1'de -> kazanmali
        g = ConnectFourGame.from_moves([0, 6, 0, 6, 0, 6])
        assert AIEngine(PLAYER1_PIECE, depth=depth).find_best_move(g) == 0

    @pytest.mark.parametrize("depth", [2, 4, 6])
    def test_does_not_play_under_opponent_winning_square(self, depth):
        # P2'nin (1,1)-(2,1)-(3,1) uclusu (4,1) ile tamamlanir; (4,0) bos.
        # P1 sutun 4'e oynarsa P2 hemen ustune oynayip kazanir.
        g = make_position(p1_cells=[(1, 0), (2, 0), (0, 1)],
                          p2_cells=[(0, 0), (3, 0), (1, 1), (2, 1), (3, 1)],
                          to_move=PLAYER1_PIECE)
        assert not winning_moves(g, PLAYER1_PIECE) and not winning_moves(g, PLAYER2_PIECE)
        child = g.clone()
        child.make_move(4)
        assert winning_moves(child, PLAYER2_PIECE) == [4]  # on kosul: sutun 4 tuzak
        assert AIEngine(PLAYER1_PIECE, depth=depth).find_best_move(g) != 4

    def test_wins_as_fast_as_possible(self):
        """Terminal skor derinlige gore agirlikli: hemen kazanmak ertelemekten iyi."""
        g = ConnectFourGame.from_moves([3, 0, 3, 1, 3, 6])
        ai = AIEngine(PLAYER1_PIECE, depth=6)
        assert ai.find_best_move(g) == 3


class TestSearch:
    @pytest.mark.parametrize("seed", range(6))
    def test_alpha_beta_matches_plain_minimax(self, seed):
        rng = random.Random(seed)
        g = random_position(rng, rng.randint(4, 16))
        if g.game_over:
            pytest.skip("oyun bitmis")
        ai = AIEngine(g.current_player, depth=3, use_opening_book=False)
        _, value = ai.minimax(g.clone(), 3, -math.inf, math.inf, True)
        assert value == plain_minimax(ai, g, 3, True)

    def test_metrics_are_collected_and_reset(self):
        g = ConnectFourGame.from_moves([3, 3, 2, 4])
        ai = AIEngine(PLAYER1_PIECE, depth=5)
        ai.find_best_move(g)
        first = ai.nodes_evaluated
        assert first > 1 and ai.cutoffs > 0
        ai.find_best_move(ConnectFourGame())   # kitap hamlesi
        assert ai.nodes_evaluated == 0 and ai.cutoffs == 0

    @pytest.mark.parametrize("moves", [[3, 2, 4], [3, 3, 2, 4, 1], [0, 6, 1, 5, 3], [3, 4, 2, 2, 5]])
    def test_node_and_cutoff_counts_match_reference_alpha_beta(self, moves):
        """
        Bagimsiz referans alpha-beta (ayni merkez-oncelikli siralama, fail-hard budama)
        ile birebir ayni dugum/budama sayisi ve deger beklenir. Budamanin kismen
        bozulmasi da yakalanir.
        """
        g = ConnectFourGame.from_moves(moves)
        ai = AIEngine(g.current_player, depth=4, use_opening_book=False)
        _, value = ai.minimax(g.clone(), 4, -math.inf, math.inf, True)
        counts = {'nodes': 0, 'cutoffs': 0}

        def reference(game, depth, alpha, beta, maximizing):
            counts['nodes'] += 1
            if game.check_win(ai.player_id):
                return SCORE_TERMINAL + depth
            if game.check_win(ai.opp_player_id):
                return -(SCORE_TERMINAL + depth)
            cols = sorted(game.get_valid_locations(), key=lambda c: abs(c - COLS // 2))
            if not cols:
                return 0
            if depth == 0:
                return ai.score_position(game, ai.player_id)
            best = -math.inf if maximizing else math.inf
            for col in cols:
                child = game.clone()
                child.make_move(col)
                v = reference(child, depth - 1, alpha, beta, not maximizing)
                if maximizing:
                    best = max(best, v)
                    alpha = max(alpha, best)
                else:
                    best = min(best, v)
                    beta = min(beta, best)
                if alpha >= beta:
                    counts['cutoffs'] += 1
                    break
            return best

        expected = reference(g, 4, -math.inf, math.inf, True)
        assert value == expected
        assert (ai.nodes_evaluated, ai.cutoffs) == (counts['nodes'], counts['cutoffs'])
        assert ai.cutoffs > 0

    def test_ai_vs_ai_produces_legal_complete_game(self):
        g = ConnectFourGame()
        players = {PLAYER1_PIECE: AIEngine(PLAYER1_PIECE, depth=3), PLAYER2_PIECE: AIEngine(PLAYER2_PIECE, depth=2)}
        while not g.game_over:
            col = players[g.current_player].find_best_move(g)
            assert g.make_move(col)
        assert g.game_over and g.move_count <= 42

    def test_deeper_search_beats_shallow(self):
        """D4, D1'e karsi iki renkte de kaybetmemeli."""
        for first in (PLAYER1_PIECE, PLAYER2_PIECE):
            deep = AIEngine(first, depth=4)
            shallow = AIEngine(3 - first, depth=1)
            g = ConnectFourGame()
            while not g.game_over:
                ai = deep if g.current_player == first else shallow
                g.make_move(ai.find_best_move(g))
            assert g.winner in (first, None)


class TestEvaluation:
    def setup_method(self):
        self.ai = AIEngine(PLAYER1_PIECE, depth=1)

    @pytest.mark.parametrize("window, score", [
        ([1, 1, 1, 1], SCORE_WIN),
        ([1, 1, 1, EMPTY], SCORE_3_OPEN),
        ([1, EMPTY, 1, EMPTY], SCORE_2_OPEN),
        ([2, 2, 2, EMPTY], SCORE_BLOCK),
        ([1, 2, EMPTY, EMPTY], 0),
    ])
    def test_window_scores(self, window, score):
        assert self.ai.evaluate_window(window, PLAYER1_PIECE) == score

    def test_center_is_preferred(self):
        center = ConnectFourGame.from_moves([3])
        edge = ConnectFourGame.from_moves([0])
        assert self.ai.score_position(center, PLAYER1_PIECE) > self.ai.score_position(edge, PLAYER1_PIECE)
