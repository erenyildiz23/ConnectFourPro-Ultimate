# =============================================================================
# MODULE: game_core.py
# =============================================================================

import copy

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

class ConnectFourGame:
    """
    Represents the Connect Four game state using efficient bitboards.
    """

    def __init__(self, starting_player=PLAYER1_PIECE):
        self.reset(starting_player)

    def reset(self, starting_player=PLAYER1_PIECE):
        """Resets the game state."""
        self.bitboards = {PLAYER1_PIECE: 0, PLAYER2_PIECE: 0}
        
        self.heights = [c * (ROWS + 1) for c in range(COLS)]
        
        self.move_history = []
        self.move_count = 0
        self.current_player = starting_player
        self.game_state = STATE_PLAYING
        self.game_over = False 
        self.winner = None
        self.winning_mask = 0 

    def make_move(self, col):
        """Executes a move. Returns True if successful."""
        if self.game_over:
            return False
            
        if not self.is_valid_location(col):
            return False

        # 1. Update Bitboard
        move_bit = 1 << self.heights[col]
        self.bitboards[self.current_player] ^= move_bit #XOR for setting bit
        
        # 2. Update State
        self.heights[col] += 1
        self.move_history.append(col)
        self.move_count += 1

        # 3. Check Win/Draw
        if self.check_win(self.current_player):
            self.game_state = STATE_WIN
            self.game_over = True
            self.winner = self.current_player
            # winning_mask is set inside check_win
        elif self.move_count >= ROWS * COLS:
            self.game_state = STATE_DRAW
            self.game_over = True
            self.winner = None
        else:
            self.switch_player()
            
        return True

    def switch_player(self):
        self.current_player = PLAYER1_PIECE if self.current_player == PLAYER2_PIECE else PLAYER2_PIECE

    def is_valid_location(self, col):
        """Checks if column is valid and not full."""
        if not (0 <= col < COLS): return False
        top_index = (col * (ROWS + 1)) + ROWS - 1
        return self.heights[col] <= top_index

    def get_valid_locations(self):
        """Returns a list of valid column indices."""
        return [c for c in range(COLS) if self.is_valid_location(c)]

    def check_win(self, player):
        """
        win conditions using bitboard operations.
        """
        bb = self.bitboards[player]
        
        # Directions: Vertical, Horizontal, Diagonal /, Diagonal \
        directions = [1, ROWS + 1, ROWS + 2, ROWS] 
        
        for d in directions:
            m = bb & (bb >> d)
            if m & (m >> (2 * d)):
                temp_mask = (bb & (bb >> d) & (bb >> (2 * d)) & (bb >> (3 * d)))
                if temp_mask:
                    self.winning_mask = (temp_mask | (temp_mask << d) | (temp_mask << (2 * d)) | (temp_mask << (3 * d)))
                    return True
        return False

    def clone(self):
        """Creates a deep copy of the game state for AI simulations."""
        new_game = ConnectFourGame(self.current_player)
        new_game.bitboards = self.bitboards.copy()
        new_game.heights = self.heights[:]
        new_game.move_history = self.move_history[:]
        new_game.move_count = self.move_count
        new_game.game_state = self.game_state
        new_game.game_over = self.game_over
        new_game.winner = self.winner
        new_game.winning_mask = self.winning_mask
        return new_game

    def to_dict(self):
        """Serializes state for network transmission."""
        return {
            'bitboards': self.bitboards,
            'heights': self.heights,
            'history': self.move_history,
            'current': self.current_player,
            'state': self.game_state,
            'game_over': self.game_over,
            'winner': self.winner,
            'winning_mask': self.winning_mask
        }

    def from_dict(self, data):
        """Restores state from network data."""
        self.bitboards = {int(k): v for k, v in data['bitboards'].items()}
        self.heights = data['heights']
        self.move_history = data['history']
        self.current_player = data['current']
        self.game_state = data['state']
        self.game_over = data['game_over']
        self.winner = data['winner']
        self.winning_mask = data.get('winning_mask', 0)

    def print_board(self):
        """Debug print."""
        print("\n--- Connect Four Tahtası ---")
        for r in range(ROWS - 1, -1, -1):
            row_str = "|"
            for c in range(COLS):
                mask = 1 << (c * (ROWS + 1) + r)
                if self.bitboards[PLAYER1_PIECE] & mask: row_str += " X |"
                elif self.bitboards[PLAYER2_PIECE] & mask: row_str += " O |"
                else: row_str += " . |"
            print(row_str)
        print("-----------------------------")
        print("| 0 | 1 | 2 | 3 | 4 | 5 | 6 |")