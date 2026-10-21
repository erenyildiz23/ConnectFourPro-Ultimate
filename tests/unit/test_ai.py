"""AI motoru v2 birim testleri (FR-06: uc zorluk seviyesinde AI rakip)."""

import math
import random
import threading
import time

import pytest

import ai_vs_human as ai_mod
from ai_vs_human import (BOARD_MASK, BOTTOM_MASK, DIFFICULTY_DEPTHS, OPENING_BOOK, WIN_SCORE, AIEngine, has_four,
                         winning_cells)
from conftest import DRAW_SEQUENCE
from game_core import COLS, PLAYER1_PIECE, PLAYER2_PIECE, ROWS, ConnectFourGame


# =============================================================================
# Yardimcilar
# =============================================================================

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


def live_position(rng, n_moves):
    """Tam n_moves hamlelik, bitmemis ve en az iki gecerli hamlesi olan pozisyon."""
    while True:
        g = random_position(rng, n_moves)
        if not g.game_over and g.move_count == n_moves and len(g.get_valid_locations()) >= 2:
            return g


def to_bits(game):
    mask = game.bitboards[PLAYER1_PIECE] | game.bitboards[PLAYER2_PIECE]
    return game.bitboards[game.current_player], mask


def reference_negamax(engine, cur, mask, depth, ply):
    """
    Budamasiz, transpozisyon tablosuz, siralamasiz tam genislikte negamax.
    Dugum kurallari motorla ayni; motorun alpha-beta + TT sonucu bununla AYNI olmali.
    """
    possible = (mask + BOTTOM_MASK) & BOARD_MASK
    if not possible:
        return 0
    if winning_cells(cur, mask) & possible:
        return WIN_SCORE - ply - 1
    opp_wins = winning_cells(cur ^ mask, mask)
    forced = possible & opp_wins
    if forced & (forced - 1):
        return -(WIN_SCORE - ply - 2)
    if forced:
        possible = forced
    candidates = possible & ~(opp_wins >> 1)
    if not candidates:
        return -(WIN_SCORE - ply - 2)
    if bin(mask).count('1') >= ROWS * COLS - 1:
        return 0
    if depth <= 0:
        return engine.evaluate(cur, mask)
    best = -math.inf
    for col in range(COLS):
        bit = candidates & (((1 << ROWS) - 1) << (col * 7))
        if bit:
            best = max(best, -reference_negamax(engine, cur ^ mask, mask | bit, depth - 1, ply + 1))
    return best


def exact_value(game):
    """Oyunun sonuna kadar kaba kuvvet: sirasi gelen icin +1 kazanir, 0 berabere, -1 kaybeder."""
    if game.winner is not None:
        return -1          # Son hamleyi yapan kazandi -> sirasi gelen kaybetti
    moves = game.get_valid_locations()
    if not moves:
        return 0
    best = -1
    for col in moves:
        child = game.clone()
        child.make_move(col)
        best = max(best, 1 if child.winner is not None else -exact_value(child))
        if best == 1:
            break
    return best


def shortest_win(game):
    """Sirasi gelen oyuncunun zorla kazanabildigi en kisa yari-hamle sayisi (kazanc yoksa None)."""
    def search(g, limit):
        # limit yari-hamle icinde zorla kazanc var mi (sirasi gelen icin)
        if limit <= 0:
            return False
        for col in g.get_valid_locations():
            child = g.clone()
            child.make_move(col)
            if child.winner is not None:
                return True
            if limit >= 3 and all(_opponent_reply_loses(child, reply, limit - 2, search)
                                  for reply in child.get_valid_locations()):
                return True
        return False
    for plies in range(1, 43, 2):
        if search(game, plies):
            return plies
    return None


def _opponent_reply_loses(game, reply, limit, search):
    g = game.clone()
    g.make_move(reply)
    return g.winner is None and g.get_valid_locations() and search(g, limit)


# =============================================================================
# Temel davranis
# =============================================================================

class TestBasics:
    def test_difficulty_levels(self):
        assert DIFFICULTY_DEPTHS == {'Kolay': 2, 'Orta': 4, 'Zor': 8}

    def test_invalid_depth_rejected(self):
        with pytest.raises(ValueError):
            AIEngine(PLAYER2_PIECE, depth=0)

    @pytest.mark.parametrize("depth", [1, 2, 4, 8])
    def test_always_returns_a_valid_move(self, depth):
        rng = random.Random(depth)
        for n in (0, 5, 15, 30, 38):
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
        AIEngine(PLAYER2_PIECE, depth=6).find_best_move(g)
        assert g.to_dict() == before

    def test_is_deterministic_without_seed(self):
        g = ConnectFourGame.from_moves([3, 2, 4, 4, 1])
        moves = {AIEngine(PLAYER2_PIECE, depth=6).find_best_move(g) for _ in range(3)}
        assert len(moves) == 1

    def test_seeded_tie_breaking_is_reproducible(self):
        g = ConnectFourGame.from_moves([0, 6, 1])
        a = AIEngine(PLAYER2_PIECE, depth=4, seed=7).find_best_move(g)
        b = AIEngine(PLAYER2_PIECE, depth=4, seed=7).find_best_move(g)
        assert a == b


class TestCancellation:
    def test_cancelled_search_returns_none_immediately(self):
        cancel = threading.Event()
        cancel.set()
        ai = AIEngine(PLAYER2_PIECE, depth=8, use_opening_book=False)
        assert ai.find_best_move(ConnectFourGame.from_moves([3, 3, 2, 4, 1]), cancel_event=cancel) is None
        assert ai.nodes_evaluated <= 1

    def test_cancel_stops_running_search(self):
        cancel = threading.Event()
        ai = AIEngine(PLAYER2_PIECE, depth=16, use_opening_book=False, exact_endgame=False)
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
        ai = AIEngine(PLAYER2_PIECE, depth=4, use_opening_book=False)
        g = ConnectFourGame.from_moves([3, 3, 2, 4, 1])
        assert ai.find_best_move(g, cancel_event=cancel) is None
        assert ai.find_best_move(g) in g.get_valid_locations()


class TestOpeningBook:
    def test_book_covers_first_two_plies(self):
        assert len(OPENING_BOOK) == 1 + 7 + 49
        for history, move in OPENING_BOOK.items():
            assert ConnectFourGame.from_moves(list(history)).is_valid_location(move)

    def test_book_move_on_empty_board_is_center(self):
        """Allis/Allen (1988): kusursuz oyunda ilk oyuncu ortadan baslayarak kazanir."""
        ai = AIEngine(PLAYER1_PIECE, depth=8)
        assert ai.find_best_move(ConnectFourGame()) == 3
        assert ai.last_move_from_book and ai.nodes_evaluated == 0

    def test_book_can_be_disabled(self):
        ai = AIEngine(PLAYER1_PIECE, depth=2, use_opening_book=False)
        ai.find_best_move(ConnectFourGame())
        assert not ai.last_move_from_book and ai.nodes_evaluated > 0


# =============================================================================
# Taktik
# =============================================================================

class TestTactics:
    @pytest.mark.parametrize("moves, expected", [
        ([3, 0, 3, 1, 3, 2], 3),                 # Dikey
        ([0, 0, 1, 1, 2, 2], 3),                 # Yatay (sag uc)
        ([1, 1, 2, 2, 3, 3], None),              # Yatay iki ucu acik: 0 veya 4
        ([0, 1, 1, 2, 2, 3, 2, 3, 3, 6], 3),     # Capraz /
    ], ids=["vertical", "horizontal_edge", "horizontal_open", "diagonal"])
    @pytest.mark.parametrize("depth", [1, 2, 4, 8])
    def test_takes_immediate_win(self, moves, expected, depth):
        g = ConnectFourGame.from_moves(moves)
        wins = winning_moves(g, g.current_player)
        assert wins and (expected is None or expected in wins)
        assert AIEngine(g.current_player, depth=depth, use_opening_book=False).find_best_move(g) in wins

    @pytest.mark.parametrize("depth", [1, 2, 4, 8])
    @pytest.mark.parametrize("moves, threat", [
        ([0, 3, 1, 3, 6, 3], 3),    # P2 sutun 3'te dikey uclu
        ([6, 0, 6, 1, 5, 2], 3),    # P2 alt satirda 0-1-2
        ([4, 0, 2, 3, 6, 5, 1, 2, 3, 4, 1, 5, 2, 2, 5, 4], 3),   # capraz tehdit
    ], ids=["block_vertical", "block_horizontal", "block_diagonal"])
    def test_blocks_single_opponent_threat(self, moves, threat, depth):
        g = ConnectFourGame.from_moves(moves)
        me = g.current_player
        assert winning_moves(g, 3 - me) == [threat] and not winning_moves(g, me)  # on kosul
        assert AIEngine(me, depth=depth, use_opening_book=False).find_best_move(g) == threat

    @pytest.mark.parametrize("depth", [1, 2, 4])
    def test_prefers_own_win_over_blocking(self, depth):
        g = ConnectFourGame.from_moves([0, 6, 0, 6, 0, 6])
        assert AIEngine(PLAYER1_PIECE, depth=depth, use_opening_book=False).find_best_move(g) == 0

    @pytest.mark.parametrize("depth", [1, 2, 4, 8])
    def test_does_not_play_under_opponent_winning_square(self, depth):
        # P2'nin (1,1)-(2,1)-(3,1) uclusu (4,1) ile tamamlanir; (4,0) bos.
        g = make_position(p1_cells=[(1, 0), (2, 0), (0, 1)],
                          p2_cells=[(0, 0), (3, 0), (1, 1), (2, 1), (3, 1)],
                          to_move=PLAYER1_PIECE)
        child = g.clone()
        child.make_move(4)
        assert winning_moves(child, PLAYER2_PIECE) == [4]  # on kosul: sutun 4 tuzak
        assert AIEngine(PLAYER1_PIECE, depth=depth, use_opening_book=False).find_best_move(g) != 4

    @pytest.mark.parametrize("depth", [3, 4, 8])
    def test_creates_double_threat(self, depth):
        """Kesin aramayla dogrulanmis pozisyon: 2 veya 5, 3 yari-hamlede zorla kazanir."""
        g = ConnectFourGame.from_moves([4, 0, 3, 1, 1, 6, 3, 1, 4, 6])
        assert AIEngine(g.current_player, depth=depth, use_opening_book=False).find_best_move(g) in (2, 5)

    def test_reports_forced_win_score(self):
        g = ConnectFourGame.from_moves([4, 0, 3, 1, 1, 6, 3, 1, 4, 6])
        ai = AIEngine(g.current_player, depth=6, use_opening_book=False)
        ai.find_best_move(g)
        assert ai.last_score > WIN_SCORE - 10


# =============================================================================
# Arama dogrulugu
# =============================================================================

class TestSearchCorrectness:
    @pytest.mark.parametrize("seed", range(4))
    def test_winning_cells_match_brute_force(self, seed):
        rng = random.Random(seed)
        for n in range(4, 36, 4):
            g = random_position(rng, n)
            if g.game_over:
                continue
            cur, mask = to_bits(g)
            expected = 0
            for col in range(COLS):
                for row in range(ROWS):
                    bit = 1 << (col * 7 + row)
                    if not mask & bit and has_four(cur | bit):
                        expected |= bit
            assert winning_cells(cur, mask) == expected

    @pytest.mark.parametrize("seed", range(8))
    def test_alpha_beta_with_tt_matches_full_width_negamax(self, seed):
        """TT, budama ve siralama aramanin sonucunu degistirmemeli."""
        rng = random.Random(100 + seed)
        g = live_position(rng, rng.randint(2, 24))
        cur, mask = to_bits(g)
        engine = AIEngine(g.current_player, depth=4, use_opening_book=False, exact_endgame=False)
        expected = reference_negamax(engine, cur, mask, 4, 0)
        engine._tt = {}
        assert engine.negamax(cur, mask, 4, -WIN_SCORE * 2, WIN_SCORE * 2, 0) == expected

    @pytest.mark.parametrize("seed", range(6))
    def test_window_semantics_with_shared_transposition_table(self, seed):
        """
        Alpha-beta sozlesmesi, TT korunarak dar / sifir genislikli pencerelerde:
        v <= alpha ise sonuc <= alpha; v >= beta ise sonuc >= beta; aksi halde sonuc == v.
        """
        rng = random.Random(400 + seed)
        g = live_position(rng, rng.randint(2, 10))     # sakin pozisyon: genis agac, cok TT isabeti
        cur, mask = to_bits(g)
        engine = AIEngine(g.current_player, depth=5, use_opening_book=False, exact_endgame=False)
        truth = reference_negamax(engine, cur, mask, 5, 0)
        engine._tt = {}
        windows = [(truth - 1, truth), (truth, truth + 1), (truth - 1, truth + 1), (truth + 1, truth + 2),
                   (truth - 2, truth - 1), (-WIN_SCORE * 2, truth - 5), (truth + 5, WIN_SCORE * 2),
                   (truth - 50, truth + 50)]
        for _ in range(3):                         # tekrarlar TT girdilerini yeniden kullanir
            for alpha, beta in windows:
                result = engine.negamax(cur, mask, 5, alpha, beta, 0)
                if truth <= alpha:
                    assert result <= alpha, (alpha, beta, truth, result)
                elif truth >= beta:
                    assert result >= beta, (alpha, beta, truth, result)
                else:
                    assert result == truth, (alpha, beta, truth, result)

    @pytest.mark.parametrize("seed", range(8))
    def test_win_distance_matches_brute_force(self, seed):
        """Oyun sonunda bildirilen skor, en kisa zorunlu kazanc mesafesiyle birebir ayni olmali."""
        rng = random.Random(600 + seed)
        while True:   # en az 5 yari-hamlelik zorla kazanc: "bir sonraki hamlede kazanir" kurali derinde calisir
            g = live_position(rng, 30)
            if exact_value(g) == 1 and shortest_win(g) >= 5:
                break
        engine = AIEngine(g.current_player, depth=2, use_opening_book=False)
        cur, mask = to_bits(g)
        remaining = ROWS * COLS - g.move_count
        value = engine.negamax(cur, mask, remaining, -WIN_SCORE * 2, WIN_SCORE * 2, 0)
        assert value == WIN_SCORE - shortest_win(g)

    def test_last_empty_cell_is_a_draw_at_search_horizon(self):
        g = ConnectFourGame.from_moves(DRAW_SEQUENCE[:-1])
        engine = AIEngine(g.current_player, depth=1, use_opening_book=False)
        assert engine.negamax(*to_bits(g), 0, -WIN_SCORE * 2, WIN_SCORE * 2, 0) == 0

    def test_forced_win_distance_is_exact(self):
        """3 yari-hamlede kazanc: kok skoru tam olarak WIN_SCORE - 3 (en hizli kazanc tercih edilir)."""
        g = ConnectFourGame.from_moves([4, 0, 3, 1, 1, 6, 3, 1, 4, 6])
        ai = AIEngine(g.current_player, depth=8, use_opening_book=False)
        ai.find_best_move(g)
        assert ai.last_score == WIN_SCORE - 3

    @pytest.mark.parametrize("seed", range(8))
    def test_chosen_move_is_optimal_for_its_depth(self, seed):
        rng = random.Random(200 + seed)
        g = live_position(rng, rng.randint(6, 26))
        engine = AIEngine(g.current_player, depth=4, use_opening_book=False, exact_endgame=False)
        move = engine.find_best_move(g)
        cur, mask = to_bits(g)
        values = {}
        for col in g.get_valid_locations():
            bit = 1 << (col * 7 + g.next_row(col))
            if has_four(cur | bit):
                values[col] = WIN_SCORE
            else:
                values[col] = -reference_negamax(engine, cur ^ mask, mask | bit, 3, 1)
        assert values[move] == max(values.values())

    @pytest.mark.parametrize("seed", range(10))
    def test_exact_endgame_matches_brute_force(self, seed):
        rng = random.Random(300 + seed)
        g = live_position(rng, 32)
        truth = exact_value(g)
        ai = AIEngine(g.current_player, depth=2, use_opening_book=False, exact_endgame=True)
        move = ai.find_best_move(g)
        child = g.clone()
        child.make_move(move)
        achieved = 1 if child.winner is not None else -exact_value(child)
        assert achieved == truth, "oyun sonunda optimal olmayan hamle"

    def test_metrics_are_collected_and_reset(self):
        g = ConnectFourGame.from_moves([3, 3, 2, 4])
        ai = AIEngine(PLAYER1_PIECE, depth=6, use_opening_book=False)
        ai.find_best_move(g)
        assert ai.nodes_evaluated > 1 and ai.cutoffs > 0 and ai.last_depth_reached == 6
        ai.use_opening_book = True
        ai.find_best_move(ConnectFourGame())
        assert ai.nodes_evaluated == 0 and ai.cutoffs == 0

    def test_ai_vs_ai_produces_legal_complete_game(self):
        g = ConnectFourGame()
        players = {PLAYER1_PIECE: AIEngine(PLAYER1_PIECE, depth=4), PLAYER2_PIECE: AIEngine(PLAYER2_PIECE, depth=2)}
        while not g.game_over:
            assert g.make_move(players[g.current_player].find_best_move(g))
        assert g.game_over and g.move_count <= 42

    def test_deeper_search_beats_shallow(self):
        """D6, D1'e karsi iki renkte de kaybetmemeli."""
        for first in (PLAYER1_PIECE, PLAYER2_PIECE):
            deep, shallow = AIEngine(first, depth=6), AIEngine(3 - first, depth=1)
            g = ConnectFourGame()
            while not g.game_over:
                g.make_move((deep if g.current_player == first else shallow).find_best_move(g))
            assert g.winner in (first, None)


class TestEvaluation:
    def test_center_is_preferred(self):
        center = ConnectFourGame.from_moves([3])
        edge = ConnectFourGame.from_moves([0])
        # Hamleyi yapan (P1) acisindan: sirasi gelen P2 icin skorun negatifi
        assert -AIEngine.evaluate(*to_bits(center)) > -AIEngine.evaluate(*to_bits(edge))

    def test_threat_parity_follows_game_theory(self):
        """Ilk oyuncu icin tek satirdaki (1,3,5) tehdit, cift satirdakinden degerlidir."""
        assert ai_mod.THREAT_GOOD > ai_mod.THREAT_OTHER
        assert ai_mod.ROWS_ODD & 1 and not ai_mod.ROWS_EVEN & 1            # satir 0 = 1. satir = tek
        assert ai_mod.ROWS_ODD | ai_mod.ROWS_EVEN == BOARD_MASK and not ai_mod.ROWS_ODD & ai_mod.ROWS_EVEN
