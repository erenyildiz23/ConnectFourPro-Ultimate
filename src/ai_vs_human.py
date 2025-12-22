# =============================================================================
# MODULE: ai_vs_human.py
# =============================================================================

import math
import random
import time
from game_core import ROWS, COLS, WINDOW_LENGTH, EMPTY, PLAYER1_PIECE, PLAYER2_PIECE

# --- TUNED HEURISTICS ---
SCORE_WIN = 10000000000
SCORE_BLOCK = -6000000 
SCORE_3_OPEN = 5000     
SCORE_2_OPEN = 300      
SCORE_CENTER = 10       

MAX_DEPTH_DEFAULT = 7

# --- OPENING BOOK ---
OPENING_BOOK = {
    (): 3,
    (3,): 3,
    (3, 3): 3,
    (3, 2): 3, (3, 4): 3,
    (3, 3, 3): 2,
    (0,): 3, (1,): 3, (2,): 3, (4,): 3, (5,): 3, (6,): 3,
}

class AIEngine:
    def __init__(self, player_id, depth=MAX_DEPTH_DEFAULT):
        self.player_id = player_id
        self.opp_player_id = PLAYER1_PIECE if player_id == PLAYER2_PIECE else PLAYER2_PIECE
        self.depth = depth

    def evaluate_window(self, window, piece):
        score = 0
        opp_piece = self.opp_player_id

        if window.count(piece) == 4:
            score += SCORE_WIN
        elif window.count(piece) == 3 and window.count(EMPTY) == 1:
            score += SCORE_3_OPEN
        elif window.count(piece) == 2 and window.count(EMPTY) == 2:
            score += SCORE_2_OPEN

        if window.count(opp_piece) == 3 and window.count(EMPTY) == 1:
            score += SCORE_BLOCK

        return score

    def score_position(self, game, piece):
        score = 0
        
        # 1. Center Control
        center_idx = COLS // 2
        center_col = [(game.bitboards[piece] >> (center_idx * (ROWS+1) + r)) & 1 for r in range(ROWS)]
        score += sum(center_col) * SCORE_CENTER

        # 2. Board Reconstruction
        board = [[EMPTY]*COLS for _ in range(ROWS)]
        for c in range(COLS):
            for r in range(ROWS):
                idx = c * (ROWS + 1) + r
                if (game.bitboards[PLAYER1_PIECE] >> idx) & 1: board[r][c] = PLAYER1_PIECE
                elif (game.bitboards[PLAYER2_PIECE] >> idx) & 1: board[r][c] = PLAYER2_PIECE

        # 3. Window Scanning
        # Horizontal
        for r in range(ROWS):
            for c in range(COLS - 3):
                window = board[r][c:c+4]
                score += self.evaluate_window(window, piece)
        # Vertical
        for c in range(COLS):
            for r in range(ROWS - 3):
                window = [board[r+i][c] for i in range(4)]
                score += self.evaluate_window(window, piece)
        # Diagonals
        for r in range(ROWS - 3):
            for c in range(COLS - 3):
                window = [board[r+i][c+i] for i in range(4)]
                score += self.evaluate_window(window, piece)
        for r in range(3, ROWS):
            for c in range(COLS - 3):
                window = [board[r-i][c+i] for i in range(4)]
                score += self.evaluate_window(window, piece)
        return score

    def is_terminal_node(self, game):
        # Check win conditions first
        if game.check_win(self.player_id) or game.check_win(self.opp_player_id):
            return True
        # Check if board is full (Draw)
        if len(game.get_valid_locations()) == 0:
            return True
        return False

    def minimax(self, game, depth, alpha, beta, maximizingPlayer):
        valid_locations = game.get_valid_locations()
        is_terminal = self.is_terminal_node(game)
        
        if depth == 0 or is_terminal:
            if is_terminal:
                if game.check_win(self.player_id): return (None, 100000000000)
                elif game.check_win(self.opp_player_id): return (None, -100000000000)
                else: return (None, 0) # Game is over, no more valid moves
            else: return (None, self.score_position(game, self.player_id))

        if not valid_locations:
             return (None, 0)

        # Heuristic sort for pruning 
        valid_locations.sort(key=lambda x: abs(x - COLS//2))

        if maximizingPlayer:
            value = -math.inf
            # Default to a random valid move if no move improves -inf
            best_col = random.choice(valid_locations)
            for col in valid_locations:
                temp_game = game.clone()
                temp_game.make_move(col)
                new_score = self.minimax(temp_game, depth-1, alpha, beta, False)[1]
                
                if new_score > value: 
                    value = new_score
                    best_col = col
                alpha = max(alpha, value)
                if alpha >= beta: break
            return best_col, value
        else:
            value = math.inf
            # Default to a random valid move if no move improves +inf
            best_col = random.choice(valid_locations)
            for col in valid_locations:
                temp_game = game.clone()
                temp_game.make_move(col)
                new_score = self.minimax(temp_game, depth-1, alpha, beta, True)[1]
                
                if new_score < value: 
                    value = new_score
                    best_col = col
                beta = min(beta, value)
                if alpha >= beta: break
            return best_col, value

    def find_best_move(self, game):
        # 0. Early Exit for Full Board
        valid_moves = game.get_valid_locations()
        if not valid_moves:
            return None # Board is full, no move possible

        # 1. Opening Book
        history = tuple(game.move_history)
        if history in OPENING_BOOK:
             move = OPENING_BOOK[history]
             if game.is_valid_location(move): return move
        
        # 2. Minimax
        game_copy = game.clone()
        try:
            col, score = self.minimax(game_copy, self.depth, -math.inf, math.inf, True)
        except Exception as e:
            print(f"[AI ERROR] Minimax crashed: {e}")
            col = None

        # 3. Fallback (Safety Net)
        if col is None:
            return random.choice(valid_moves)
        
        return col