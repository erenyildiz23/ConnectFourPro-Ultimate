# =============================================================================
# MODULE: game_core.py
# Connect Four Pro - Bitboard tabanli oyun motoru
# =============================================================================
"""
Tahta temsili (bitboard)
------------------------
Her oyuncunun taslari tek bir tam sayida tutulur. Sutun c, satir r (0 = alt)
icin bit indeksi ``c * (ROWS + 1) + r`` dir. Her sutunun ustunde bos birakilan
bir "nobetci" bit, yatay/capraz kaydirmalarin sutunlar arasinda tasmasini
engeller::

     6 13 20 27 34 41 48   <- nobetci satir (her zaman 0)
     5 12 19 26 33 40 47
     4 11 18 25 32 39 46
     3 10 17 24 31 38 45
     2  9 16 23 30 37 44
     1  8 15 22 29 36 43
     0  7 14 21 28 35 42

Kazanma kontrolu dort yonde (dikey=1, yatay=7, capraz /=8, capraz \\=6)
sabit sayida bit islemiyle yapilir: O(1).
"""

from typing import Dict, List, Optional, Tuple

# --- GLOBAL CONSTANTS ---
ROWS = 6
COLS = 7
WINDOW_LENGTH = 4
EMPTY = 0
PLAYER1_PIECE = 1
PLAYER2_PIECE = 2

# Game States
STATE_PLAYING = 0
STATE_WIN = 1
STATE_DRAW = 2

_COL_STRIDE = ROWS + 1
# Kazanma yonleri: dikey, yatay, capraz /, capraz \
_DIRECTIONS = (1, _COL_STRIDE, _COL_STRIDE + 1, _COL_STRIDE - 1)


def other_player(piece: int) -> int:
    """Rakip oyuncunun tas numarasini dondurur."""
    return PLAYER1_PIECE if piece == PLAYER2_PIECE else PLAYER2_PIECE


def bit_index(col: int, row: int) -> int:
    """(sutun, satir) koordinatinin bitboard indeksini dondurur."""
    return col * _COL_STRIDE + row


class ConnectFourGame:
    """
    Connect Four oyun durumu.

    Attributes:
        bitboards: {PLAYER1_PIECE: int, PLAYER2_PIECE: int}
        heights: Her sutunda bir sonraki tasin gidecegi bit indeksi
        move_history: Oynanan sutunlarin sirali listesi
        current_player: Sirasi gelen oyuncu
        game_state: STATE_PLAYING / STATE_WIN / STATE_DRAW
        winner: Kazanan oyuncu veya None
        winning_mask: Kazanan dortlunun bit maskesi (yoksa 0)
    """

    def __init__(self, starting_player: int = PLAYER1_PIECE):
        self.reset(starting_player)

    def reset(self, starting_player: int = PLAYER1_PIECE) -> None:
        """Oyunu baslangic durumuna getirir."""
        self.bitboards: Dict[int, int] = {PLAYER1_PIECE: 0, PLAYER2_PIECE: 0}
        self.heights: List[int] = [c * _COL_STRIDE for c in range(COLS)]
        self.move_history: List[int] = []
        self.move_count = 0
        self.current_player = starting_player
        self.game_state = STATE_PLAYING
        self.game_over = False
        self.winner: Optional[int] = None
        self.winning_mask = 0

    # ------------------------------------------------------------------
    # Hamleler
    # ------------------------------------------------------------------

    def make_move(self, col: int) -> bool:
        """Sirasi gelen oyuncu icin hamle yapar. Gecersizse False dondurur."""
        if self.game_over or not self.is_valid_location(col):
            return False

        self.bitboards[self.current_player] |= 1 << self.heights[col]
        self.heights[col] += 1
        self.move_history.append(col)
        self.move_count += 1

        if self.check_win(self.current_player):
            self.game_state = STATE_WIN
            self.game_over = True
            self.winner = self.current_player
        elif self.move_count >= ROWS * COLS:
            self.game_state = STATE_DRAW
            self.game_over = True
            self.winner = None
        else:
            self.switch_player()
        return True

    def switch_player(self) -> None:
        self.current_player = other_player(self.current_player)

    def is_valid_location(self, col: int) -> bool:
        """Sutun tahta icinde ve dolu degilse True."""
        if not isinstance(col, int) or not 0 <= col < COLS:
            return False
        return self.heights[col] < bit_index(col, ROWS)

    def get_valid_locations(self) -> List[int]:
        """Oynanabilir sutunlarin listesi."""
        return [c for c in range(COLS) if self.is_valid_location(c)]

    def next_row(self, col: int) -> int:
        """Sutuna atilacak tasin dusecegi satir (0 = alt)."""
        return self.heights[col] - col * _COL_STRIDE

    # ------------------------------------------------------------------
    # Kazanma kontrolu
    # ------------------------------------------------------------------

    def check_win(self, player: int) -> bool:
        """
        Oyuncunun dortlu yapip yapmadigini kontrol eder (O(1)).
        Kazanma varsa ``winning_mask`` guncellenir.
        """
        bb = self.bitboards[player]
        for d in _DIRECTIONS:
            m = bb & (bb >> d)
            if m & (m >> (2 * d)):
                start = bb & (bb >> d) & (bb >> (2 * d)) & (bb >> (3 * d))
                self.winning_mask = start | (start << d) | (start << (2 * d)) | (start << (3 * d))
                return True
        return False

    def get_cell(self, col: int, row: int) -> int:
        """Hucredeki tas: EMPTY, PLAYER1_PIECE veya PLAYER2_PIECE."""
        mask = 1 << bit_index(col, row)
        if self.bitboards[PLAYER1_PIECE] & mask:
            return PLAYER1_PIECE
        if self.bitboards[PLAYER2_PIECE] & mask:
            return PLAYER2_PIECE
        return EMPTY

    def get_board(self) -> List[List[int]]:
        """Tahtayi board[satir][sutun] matrisi olarak dondurur (satir 0 = alt)."""
        return [[self.get_cell(c, r) for c in range(COLS)] for r in range(ROWS)]

    def get_winning_positions(self) -> List[Tuple[int, int]]:
        """Kazanan taslarin (sutun, satir) listesi; oyun kazanilmadiysa bos."""
        if self.game_state != STATE_WIN or not self.winning_mask:
            return []
        return [(c, r) for c in range(COLS) for r in range(ROWS)
                if (self.winning_mask >> bit_index(c, r)) & 1]

    # ------------------------------------------------------------------
    # Kopyalama ve serilestirme
    # ------------------------------------------------------------------

    def clone(self) -> "ConnectFourGame":
        """AI simulasyonlari icin bagimsiz kopya."""
        new_game = ConnectFourGame.__new__(ConnectFourGame)
        new_game.bitboards = self.bitboards.copy()
        new_game.heights = self.heights[:]
        new_game.move_history = self.move_history[:]
        new_game.move_count = self.move_count
        new_game.current_player = self.current_player
        new_game.game_state = self.game_state
        new_game.game_over = self.game_over
        new_game.winner = self.winner
        new_game.winning_mask = self.winning_mask
        return new_game

    def to_dict(self) -> dict:
        """Ag uzerinden gondermek icin durumu sozluge cevirir."""
        return {
            'bitboards': self.bitboards,
            'heights': self.heights,
            'history': self.move_history,
            'current': self.current_player,
            'state': self.game_state,
            'game_over': self.game_over,
            'winner': self.winner,
            'winning_mask': self.winning_mask,
        }

    def from_dict(self, data: dict) -> None:
        """to_dict() ciktisindan durumu geri yukler (JSON'da anahtarlar str olur)."""
        self.bitboards = {int(k): v for k, v in data['bitboards'].items()}
        self.heights = list(data['heights'])
        self.move_history = list(data['history'])
        self.move_count = len(self.move_history)
        self.current_player = data['current']
        self.game_state = data['state']
        self.game_over = data['game_over']
        self.winner = data['winner']
        self.winning_mask = data.get('winning_mask', 0)

    @classmethod
    def from_moves(cls, moves: List[int], starting_player: int = PLAYER1_PIECE) -> "ConnectFourGame":
        """Hamle listesinden oyun olusturur. Gecersiz hamlede ValueError."""
        game = cls(starting_player)
        for i, col in enumerate(moves):
            if not game.make_move(col):
                raise ValueError(f"Gecersiz hamle #{i + 1}: sutun {col}")
        return game

    def __str__(self) -> str:
        symbols = {EMPTY: '.', PLAYER1_PIECE: 'X', PLAYER2_PIECE: 'O'}
        lines = ['|' + '|'.join(f' {symbols[self.get_cell(c, r)]} ' for c in range(COLS)) + '|'
                 for r in range(ROWS - 1, -1, -1)]
        lines.append('| ' + ' | '.join(str(c) for c in range(COLS)) + ' |')
        return '\n'.join(lines)

    def print_board(self) -> None:
        """Debug ciktisi."""
        print(self)
