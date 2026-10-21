# =============================================================================
# MODULE: ai_vs_human.py
# Connect Four Pro - Minimax + Alpha-Beta AI motoru
# =============================================================================
"""
Arama: Minimax + Alpha-Beta budama, merkez-oncelikli hamle siralamasi.
Degerlendirme: 4'luk pencere taramasi (acik 2'li / 3'lu, rakip tehdidi) +
merkez sutun kontrolu. Bilinen acilislar icin kucuk bir acilis kitabi.

Terminal skorlar kalan derinlikle agirliklandirilir: AI kazanci olabildigince
erken, kaybi olabildigince gec tercih eder (kazanabilecekken oyunu uzatmaz).
"""

import math
import random
from typing import Optional, Sequence, Tuple

from config import get_logger
from game_core import COLS, EMPTY, ROWS, ConnectFourGame, other_player

log = get_logger("ai")

# --- TUNED HEURISTICS ---
SCORE_WIN = 10000000000
SCORE_BLOCK = -6000000
SCORE_3_OPEN = 5000
SCORE_2_OPEN = 300
SCORE_CENTER = 10

# Terminal pozisyon skoru (heuristik skorlarin her zaman ustunde)
SCORE_TERMINAL = 100000000000

MAX_DEPTH_DEFAULT = 7

# Arayuzdeki zorluk seviyeleri
DIFFICULTY_DEPTHS = {'Kolay': 2, 'Orta': 4, 'Zor': 6}

# --- OPENING BOOK ---
OPENING_BOOK = {
    (): 3,
    (3,): 3,
    (3, 3): 3,
    (3, 2): 3, (3, 4): 3,
    (3, 3, 3): 2,
    (0,): 3, (1,): 3, (2,): 3, (4,): 3, (5,): 3, (6,): 3,
}

_CENTER = COLS // 2


class SearchCancelled(Exception):
    """Arama disaridan iptal edildi (orn. oyuncu menuye dondu)."""


class AIEngine:
    """
    Args:
        player_id: AI'nin oynadigi tas (PLAYER1_PIECE / PLAYER2_PIECE)
        depth: Arama derinligi (hamle sayisi)
        use_opening_book: False ise her hamlede arama yapilir (benchmark icin)
        seed: Tekrarlanabilir sonuclar icin rastgelelik tohumu
    """

    def __init__(self, player_id: int, depth: int = MAX_DEPTH_DEFAULT,
                 use_opening_book: bool = True, seed: Optional[int] = None):
        if depth < 1:
            raise ValueError("depth en az 1 olmali")
        self.player_id = player_id
        self.opp_player_id = other_player(player_id)
        self.depth = depth
        self.use_opening_book = use_opening_book
        self._rng = random.Random(seed)
        # Performans metrikleri (benchmarks/ai_performance_suite.py kullanir)
        self.nodes_evaluated = 0
        self.cutoffs = 0
        self.last_move_from_book = False
        self._cancel = None

    def reset_metrics(self) -> None:
        self.nodes_evaluated = 0
        self.cutoffs = 0
        self.last_move_from_book = False

    # ------------------------------------------------------------------
    # Degerlendirme
    # ------------------------------------------------------------------

    def evaluate_window(self, window: Sequence[int], piece: int) -> int:
        """4 hucrelik bir pencereyi `piece` acisindan puanlar."""
        own = window.count(piece)
        empty = window.count(EMPTY)
        opp = window.count(other_player(piece))

        score = 0
        if own == 4:
            score += SCORE_WIN
        elif own == 3 and empty == 1:
            score += SCORE_3_OPEN
        elif own == 2 and empty == 2:
            score += SCORE_2_OPEN

        if opp == 3 and empty == 1:
            score += SCORE_BLOCK
        return score

    def score_position(self, game: ConnectFourGame, piece: int) -> int:
        """Terminal olmayan pozisyonun `piece` acisindan heuristik degeri."""
        board = game.get_board()

        # 1. Merkez kontrolu
        score = sum(1 for r in range(ROWS) if board[r][_CENTER] == piece) * SCORE_CENTER

        # 2. Pencere taramasi
        for r in range(ROWS):                                   # Yatay
            for c in range(COLS - 3):
                score += self.evaluate_window(board[r][c:c + 4], piece)
        for c in range(COLS):                                   # Dikey
            for r in range(ROWS - 3):
                score += self.evaluate_window([board[r + i][c] for i in range(4)], piece)
        for r in range(ROWS - 3):                               # Capraz /
            for c in range(COLS - 3):
                score += self.evaluate_window([board[r + i][c + i] for i in range(4)], piece)
        for r in range(3, ROWS):                                # Capraz \
            for c in range(COLS - 3):
                score += self.evaluate_window([board[r - i][c + i] for i in range(4)], piece)
        return score

    # ------------------------------------------------------------------
    # Arama
    # ------------------------------------------------------------------

    def is_terminal_node(self, game: ConnectFourGame) -> bool:
        return (game.check_win(self.player_id) or game.check_win(self.opp_player_id)
                or not game.get_valid_locations())

    def minimax(self, game: ConnectFourGame, depth: int, alpha: float, beta: float,
                maximizingPlayer: bool) -> Tuple[Optional[int], float]:
        """(en iyi sutun, deger) dondurur. Deger AI (player_id) acisindandir."""
        self.nodes_evaluated += 1
        if self._cancel is not None and self._cancel.is_set():
            raise SearchCancelled

        if game.check_win(self.player_id):
            return None, SCORE_TERMINAL + depth         # Erken kazanc daha degerli
        if game.check_win(self.opp_player_id):
            return None, -(SCORE_TERMINAL + depth)      # Gec kayip daha az kotu
        valid_locations = game.get_valid_locations()
        if not valid_locations:
            return None, 0                              # Beraberlik
        if depth == 0:
            return None, self.score_position(game, self.player_id)

        # Merkeze yakin sutunlar once: budamayi iyilestirir
        valid_locations.sort(key=lambda x: abs(x - _CENTER))
        best_col = valid_locations[0]

        if maximizingPlayer:
            value = -math.inf
            for col in valid_locations:
                child = game.clone()
                child.make_move(col)
                new_score = self.minimax(child, depth - 1, alpha, beta, False)[1]
                if new_score > value:
                    value, best_col = new_score, col
                alpha = max(alpha, value)
                if alpha >= beta:
                    self.cutoffs += 1
                    break
        else:
            value = math.inf
            for col in valid_locations:
                child = game.clone()
                child.make_move(col)
                new_score = self.minimax(child, depth - 1, alpha, beta, True)[1]
                if new_score < value:
                    value, best_col = new_score, col
                beta = min(beta, value)
                if alpha >= beta:
                    self.cutoffs += 1
                    break
        return best_col, value

    def find_best_move(self, game: ConnectFourGame, cancel_event=None) -> Optional[int]:
        """
        Mevcut pozisyon icin en iyi sutun; tahta doluysa None.

        Args:
            cancel_event: threading.Event; set edilirse arama durur ve None doner.
        """
        self.reset_metrics()
        self._cancel = cancel_event

        valid_moves = game.get_valid_locations()
        if not valid_moves:
            return None

        if self.use_opening_book:
            move = OPENING_BOOK.get(tuple(game.move_history))
            if move is not None and game.is_valid_location(move):
                self.last_move_from_book = True
                return move

        try:
            col, _ = self.minimax(game.clone(), self.depth, -math.inf, math.inf, True)
        except SearchCancelled:
            return None
        except Exception:
            log.exception("Minimax hatasi")
            col = None
        finally:
            self._cancel = None

        # Guvenlik agi: arama sonuc vermezse rastgele gecerli hamle
        return col if col is not None else self._rng.choice(valid_moves)
