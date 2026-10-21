# =============================================================================
# MODULE: ai_vs_human.py
# Connect Four Pro - AI motoru v2 (negamax + alpha-beta, oyun teorisi sezgileri)
# =============================================================================
"""
Arama
-----
Negamax + alpha-beta budama, transpozisyon tablosu ve yinelemeli derinlestirme.
Konum iki tam sayiyla tutulur: ``cur`` (sirasi gelen oyuncunun taslari) ve
``mask`` (dolu hucreler); hamle basina nesne kopyalanmaz.

Her dugumde taktik kurallar uygulanir:
  * Sirasi gelen tek hamlede kazanabiliyorsa -> kazanc.
  * Rakibin oynanabilir kazanma hucresi varsa oraya oynamak zorunludur;
    iki tane varsa pozisyon kayiptir.
  * Rakibin kazanma hucresinin hemen altina oynanmaz (rakibe kapiyi acar).

Degerlendirme (oyun teorisi)
----------------------------
Connect Four cozulmus bir oyundur (Allen 1988, Allis 1988): kusursuz oyunda ilk
oyuncu ortadan baslarsa kazanir. Allis'in "zugzwang" analizine gore oyun sonunda
tehditlerin satir paritesi belirleyicidir: ilk oyuncu icin TEK satirlardaki
(1, 3, 5), ikinci oyuncu icin CIFT satirlardaki (2, 4, 6) tehditler degerlidir.
Degerlendirme bu nedenle:
  * Tehdit hucrelerini (tamamlaninca dortlu olan bos hucreler) satir paritesine
    gore agirliklandirir,
  * Her hucreden gecen olasi dortlu hat sayisina gore konumsal deger ekler,
  * Simetriktir ve sirasi gelen oyuncunun bakis acisindandir (negamax).

Oyun sonu: ``exact_endgame`` acikken kalan bos hucre sayisi esigin altina
dustugunde arama oyunun sonuna kadar yapilir (kesin cozum).

Ilk surum (v1) karsilastirma icin benchmarks/legacy_ai_v1.py dosyasindadir.
"""

import random
from typing import Dict, List, Optional, Tuple

from config import get_logger
from game_core import COLS, PLAYER1_PIECE, PLAYER2_PIECE, ROWS, ConnectFourGame, other_player

log = get_logger("ai")

MAX_DEPTH_DEFAULT = 7
DIFFICULTY_DEPTHS = {'Kolay': 2, 'Orta': 4, 'Zor': 8}

# --- Skorlar ---
WIN_SCORE = 1_000_000          # Kazanc skoru; erken kazanc daha yuksek (WIN_SCORE - ply)
WIN_THRESHOLD = WIN_SCORE - 1000
THREAT_GOOD = 8                # Lehine pariteli tehdit (oyun teorisi); egitim kumesinde ayarlandi
THREAT_OTHER = 4               # Diger tehditler
EXACT_ENDGAME_PLIES = 12       # exact_endgame acikken: kalan hamle <= esik ise sona kadar ara

# --- Bitboard sabitleri (game_core ile ayni yerlesim: bit = sutun * 7 + satir) ---
_H1 = ROWS + 1
_SIZE = ROWS * COLS
BOTTOM_MASK = sum(1 << (c * _H1) for c in range(COLS))
BOARD_MASK = BOTTOM_MASK * ((1 << ROWS) - 1)
_COLUMN_MASK = [((1 << ROWS) - 1) << (c * _H1) for c in range(COLS)]
_ORDER = sorted(range(COLS), key=lambda c: abs(c - COLS // 2))      # 3, 2, 4, 1, 5, 0, 6
# Satir paritesi (satir 0 = alt = 1. satir)
ROWS_ODD = sum(1 << (c * _H1 + r) for c in range(COLS) for r in range(0, ROWS, 2))   # 1., 3., 5. satirlar
ROWS_EVEN = sum(1 << (c * _H1 + r) for c in range(COLS) for r in range(1, ROWS, 2))  # 2., 4., 6. satirlar


def _lines_through(col: int, row: int) -> int:
    """(sutun, satir) hucresinden gecen olasi 4'lu hat sayisi."""
    count = 0
    for dc, dr in ((1, 0), (0, 1), (1, 1), (1, -1)):
        for start in range(-3, 1):
            cells = [(col + (start + i) * dc, row + (start + i) * dr) for i in range(4)]
            if all(0 <= c < COLS and 0 <= r < ROWS for c, r in cells):
                count += 1
    return count


# Ayni agirliktaki hucreler tek maskede: popcount ile hizli konumsal skor
_WEIGHT_MASKS: List[Tuple[int, int]] = []
for _w in sorted({_lines_through(c, r) for c in range(COLS) for r in range(ROWS)}):
    _WEIGHT_MASKS.append((_w, sum(1 << (c * _H1 + r) for c in range(COLS) for r in range(ROWS)
                                  if _lines_through(c, r) == _w)))

# --- Acilis kitabi: ilk iki yari-hamlenin tum pozisyonlari (57), kusursuz cozucuyle
# (Pons, connect4.gamesolver.org) hesaplanan en iyi hamleler (0 tabanli sutun).
# Birden fazla en iyi hamle varsa merkeze en yakin olani secildi.
OPENING_BOOK = {
    (): 3,
    (0,): 3, (1,): 2, (2,): 3, (3,): 3, (4,): 3, (5,): 4, (6,): 3,
    (0, 0): 3, (0, 1): 3, (0, 2): 2, (0, 3): 3, (0, 4): 3, (0, 5): 5, (0, 6): 3,
    (1, 0): 4, (1, 1): 4, (1, 2): 2, (1, 3): 3, (1, 4): 3, (1, 5): 3, (1, 6): 3,
    (2, 0): 3, (2, 1): 5, (2, 2): 3, (2, 3): 3, (2, 4): 2, (2, 5): 3, (2, 6): 3,
    (3, 0): 3, (3, 1): 1, (3, 2): 5, (3, 3): 3, (3, 4): 1, (3, 5): 1, (3, 6): 3,
    (4, 0): 3, (4, 1): 3, (4, 2): 2, (4, 3): 3, (4, 4): 3, (4, 5): 1, (4, 6): 3,
    (5, 0): 3, (5, 1): 3, (5, 2): 3, (5, 3): 3, (5, 4): 4, (5, 5): 2, (5, 6): 2,
    (6, 0): 3, (6, 1): 1, (6, 2): 3, (6, 3): 3, (6, 4): 4, (6, 5): 3, (6, 6): 3,
}


def winning_cells(position: int, mask: int) -> int:
    """`position` taslarinin tamamlarsa dortlu yapacagi BOS hucrelerin maskesi."""
    # Dikey: alttaki uc tas
    r = (position << 1) & (position << 2) & (position << 3)
    # Yatay ve iki capraz: dort konumdan herhangisi eksik olabilir
    for d in (_H1, _H1 - 1, _H1 + 1):
        p = (position << d) & (position << 2 * d)
        r |= p & (position << 3 * d)
        r |= p & (position >> d)
        p = (position >> d) & (position >> 2 * d)
        r |= p & (position << d)
        r |= p & (position >> 3 * d)
    return r & (BOARD_MASK ^ mask)


def has_four(position: int) -> bool:
    for d in (1, _H1, _H1 - 1, _H1 + 1):
        m = position & (position >> d)
        if m & (m >> 2 * d):
            return True
    return False


class SearchCancelled(Exception):
    """Arama disaridan iptal edildi (orn. oyuncu menuye dondu)."""


class AIEngine:
    """
    Args:
        player_id: AI'nin oynadigi tas (PLAYER1_PIECE / PLAYER2_PIECE)
        depth: Arama derinligi (yari-hamle)
        use_opening_book: Dogrulanmis acilis kitabini kullan
        exact_endgame: Kalan hamle EXACT_ENDGAME_PLIES altina dusunce sona kadar ara.
            None: derinlik >= 6 ise acik (Zor seviye)
        seed: Esit skorlu hamleler arasinda secim icin rastgelelik tohumu
              (None: deterministik, ilk en iyi hamle)
    """

    def __init__(self, player_id: int, depth: int = MAX_DEPTH_DEFAULT, use_opening_book: bool = True,
                 exact_endgame: Optional[bool] = None, seed: Optional[int] = None):
        if depth < 1:
            raise ValueError("depth en az 1 olmali")
        self.player_id = player_id
        self.opp_player_id = other_player(player_id)
        self.depth = depth
        self.use_opening_book = use_opening_book
        self.exact_endgame = depth >= 6 if exact_endgame is None else exact_endgame
        self._rng = random.Random(seed) if seed is not None else None
        # Metrikler (benchmark'lar kullanir)
        self.nodes_evaluated = 0
        self.cutoffs = 0
        self.last_move_from_book = False
        self.last_score: Optional[int] = None
        self.last_depth_reached = 0
        self._cancel = None
        self._tt: Dict[int, Tuple[int, int, int, int]] = {}

    def reset_metrics(self) -> None:
        self.nodes_evaluated = 0
        self.cutoffs = 0
        self.last_move_from_book = False
        self.last_score = None
        self.last_depth_reached = 0

    # ------------------------------------------------------------------
    # Degerlendirme
    # ------------------------------------------------------------------

    @staticmethod
    def evaluate(cur: int, mask: int) -> int:
        """Terminal olmayan pozisyon; sirasi gelen oyuncunun bakis acisindan."""
        opp = cur ^ mask
        side_is_first = bin(mask).count('1') % 2 == 0   # ilk oyuncu cift sayida tas varken oynar
        my_good, opp_good = (ROWS_ODD, ROWS_EVEN) if side_is_first else (ROWS_EVEN, ROWS_ODD)

        my_threats = winning_cells(cur, mask)
        opp_threats = winning_cells(opp, mask)
        score = (THREAT_GOOD * (bin(my_threats & my_good).count('1') - bin(opp_threats & opp_good).count('1'))
                 + THREAT_OTHER * (bin(my_threats & ~my_good).count('1') - bin(opp_threats & ~opp_good).count('1')))
        for weight, cells in _WEIGHT_MASKS:
            score += weight * (bin(cur & cells).count('1') - bin(opp & cells).count('1'))
        return score

    # ------------------------------------------------------------------
    # Arama
    # ------------------------------------------------------------------

    def _ordered_moves(self, cur: int, mask: int, candidates: int, first: Optional[int]) -> List[int]:
        """Adaylari sirala: TT hamlesi, sonra yeni tehdit sayisi, sonra merkeze yakinlik."""
        moves = []
        for col in _ORDER:
            bit = candidates & _COLUMN_MASK[col]
            if bit:
                threats = 0 if bit == first else bin(winning_cells(cur | bit, mask | bit)).count('1')
                moves.append((bit != first, -threats, len(moves), bit))
        moves.sort()
        return [m[3] for m in moves]

    def negamax(self, cur: int, mask: int, depth: int, alpha: int, beta: int, ply: int) -> int:
        self.nodes_evaluated += 1
        if self._cancel is not None and self._cancel.is_set():
            raise SearchCancelled

        possible = (mask + BOTTOM_MASK) & BOARD_MASK
        if not possible:
            return 0                                            # Tahta dolu: beraberlik
        if winning_cells(cur, mask) & possible:
            return WIN_SCORE - ply - 1                          # Bir sonraki hamlede kazanir
        opp_wins = winning_cells(cur ^ mask, mask)
        forced = possible & opp_wins
        if forced:
            if forced & (forced - 1):
                return -(WIN_SCORE - ply - 2)                   # Iki tehdit: engellenemez
            possible = forced
        candidates = possible & ~(opp_wins >> 1)
        if not candidates:
            return -(WIN_SCORE - ply - 2)                       # Her hamle rakibe kazanc verir
        if bin(mask).count('1') >= _SIZE - 1:
            return 0                                            # Son hamle: kimse kazanamaz
        if depth <= 0:
            return self.evaluate(cur, mask)

        # TT her aramada temizlenir; bir pozisyon ayni aramada hep ayni ply'da
        # gorulur (tas sayisi sabit), bu yuzden kazanc skorlari dogrudan saklanir.
        key = cur + mask
        tt_move = None
        entry = self._tt.get(key)
        if entry is not None:
            e_depth, e_flag, e_value, tt_move = entry
            if e_depth >= depth:
                if e_flag == 0:
                    return e_value
                if e_flag > 0 and e_value >= beta:
                    return e_value
                if e_flag < 0 and e_value <= alpha:
                    return e_value

        alpha_orig = alpha
        best_value, best_move = -WIN_SCORE * 2, 0
        for bit in self._ordered_moves(cur, mask, candidates, tt_move):
            value = -self.negamax(cur ^ mask, mask | bit, depth - 1, -beta, -alpha, ply + 1)
            if value > best_value:
                best_value, best_move = value, bit
            if value > alpha:
                alpha = value
            if alpha >= beta:
                self.cutoffs += 1
                break

        flag = 1 if best_value >= beta else (-1 if best_value <= alpha_orig else 0)
        self._tt[key] = (depth, flag, best_value, best_move)
        return best_value

    def _search_root(self, cur: int, mask: int, depth: int, order: List[int]) -> Tuple[List[Tuple[int, int]], int]:
        """Kok hamlelerini tam pencereyle degil, alpha-beta ile tarar. (sutun, skor) listesi."""
        results = []
        alpha, beta = -WIN_SCORE * 2, WIN_SCORE * 2
        for col in order:
            bit = ((mask + BOTTOM_MASK) & BOARD_MASK) & _COLUMN_MASK[col]
            # Esit skorlu hamleleri ayirt etmek icin pencere alpha-1'den baslar
            value = -self.negamax(cur ^ mask, mask | bit, depth - 1, -beta, -(alpha - 1), 1)
            results.append((col, value))
            alpha = max(alpha, value)
        return results, alpha

    def find_best_move(self, game: ConnectFourGame, cancel_event=None) -> Optional[int]:
        """
        Mevcut pozisyon icin en iyi sutun; tahta doluysa None.

        Args:
            cancel_event: threading.Event; set edilirse arama durur ve None doner.
        """
        self.reset_metrics()
        valid = game.get_valid_locations()
        if not valid or (cancel_event is not None and cancel_event.is_set()):
            return None

        if self.use_opening_book:
            move = OPENING_BOOK.get(tuple(game.move_history))
            if move is not None and game.is_valid_location(move):
                self.last_move_from_book = True
                return move

        cur = game.bitboards[game.current_player]
        mask = game.bitboards[PLAYER1_PIECE] | game.bitboards[PLAYER2_PIECE]
        possible = (mask + BOTTOM_MASK) & BOARD_MASK

        # Taktik kisayollar (aramaya gerek yok)
        wins = winning_cells(cur, mask) & possible
        if wins:
            return next(c for c in _ORDER if wins & _COLUMN_MASK[c])
        forced = possible & winning_cells(cur ^ mask, mask)
        if forced and not forced & (forced - 1):
            return next(c for c in _ORDER if forced & _COLUMN_MASK[c])

        remaining = _SIZE - bin(mask).count('1')
        target = remaining if self.exact_endgame and remaining <= EXACT_ENDGAME_PLIES else self.depth
        target = min(target, remaining)

        self._cancel = cancel_event
        self._tt = {}
        order = [c for c in _ORDER if c in valid]
        best_col = order[0]
        try:
            for depth in range(1, target + 1):                 # Yinelemeli derinlestirme
                results, best = self._search_root(cur, mask, depth, order)
                best_moves = [c for c, v in results if v == best]
                best_col = self._rng.choice(best_moves) if self._rng else best_moves[0]
                self.last_score, self.last_depth_reached = best, depth
                # Sonraki tur icin kok siralamasi: iyi hamleler once
                order = [c for c, _ in sorted(results, key=lambda cv: -cv[1])]
                if abs(best) > WIN_THRESHOLD:
                    break                                       # Zorla kazanc/kayip bulundu
        except SearchCancelled:
            return None
        except Exception:
            log.exception("Arama hatasi")
        finally:
            self._cancel = None
            self._tt = {}
        return best_col


__all__ = ['AIEngine', 'SearchCancelled', 'DIFFICULTY_DEPTHS', 'OPENING_BOOK', 'MAX_DEPTH_DEFAULT',
           'winning_cells', 'has_four', 'WIN_SCORE', 'PLAYER1_PIECE', 'PLAYER2_PIECE']
