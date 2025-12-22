#!/usr/bin/env python3
# =============================================================================
# AI PERFORMANCE TEST SUITE v3.0 - Bug Fixed Edition
# Connect Four Bitirme Projesi - Tez Veri Toplama
# =============================================================================

import sys
import os
import math
import random
import time
import json
import statistics
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, asdict

# =============================================================================
# GAME CORE - Embedded (Standalone için)
# =============================================================================

ROWS = 6
COLS = 7
WINDOW_LENGTH = 4
EMPTY = 0
PLAYER1_PIECE = 1
PLAYER2_PIECE = 2
STATE_PLAYING = 0
STATE_WIN = 1
STATE_DRAW = 2

class ConnectFourGame:
    """Bitboard tabanlı Connect Four oyun motoru."""
    
    def __init__(self, starting_player=PLAYER1_PIECE):
        self.reset(starting_player)

    def reset(self, starting_player=PLAYER1_PIECE):
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
        if self.game_over or not self.is_valid_location(col):
            return False

        move_bit = 1 << self.heights[col]
        self.bitboards[self.current_player] ^= move_bit
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
            self.current_player = PLAYER1_PIECE if self.current_player == PLAYER2_PIECE else PLAYER2_PIECE
            
        return True

    def is_valid_location(self, col):
        if not (0 <= col < COLS): return False
        top_index = (col * (ROWS + 1)) + ROWS - 1
        return self.heights[col] <= top_index

    def get_valid_locations(self):
        return [c for c in range(COLS) if self.is_valid_location(c)]

    def check_win(self, player):
        bb = self.bitboards[player]
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


# =============================================================================
# AI ENGINE - Embedded (Standalone için)
# =============================================================================

SCORE_WIN = 10000000000
SCORE_BLOCK = -6000000 
SCORE_3_OPEN = 5000     
SCORE_2_OPEN = 300      
SCORE_CENTER = 10       

OPENING_BOOK = {
    (): 3,
    (3,): 3,
    (3, 3): 3,
    (3, 2): 3, (3, 4): 3,
    (3, 3, 3): 2,
    (0,): 3, (1,): 3, (2,): 3, (4,): 3, (5,): 3, (6,): 3,
}

class AIEngine:
    """Minimax + Alpha-Beta AI Engine."""
    
    def __init__(self, player_id, depth=4):
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
        """Pozisyon değerlendirmesi - Heuristik fonksiyon."""
        score = 0
        
        # Center Control
        center_idx = COLS // 2
        center_col = [(game.bitboards[piece] >> (center_idx * (ROWS+1) + r)) & 1 for r in range(ROWS)]
        score += sum(center_col) * SCORE_CENTER

        # Board Reconstruction
        board = [[EMPTY]*COLS for _ in range(ROWS)]
        for c in range(COLS):
            for r in range(ROWS):
                idx = c * (ROWS + 1) + r
                if (game.bitboards[PLAYER1_PIECE] >> idx) & 1: board[r][c] = PLAYER1_PIECE
                elif (game.bitboards[PLAYER2_PIECE] >> idx) & 1: board[r][c] = PLAYER2_PIECE

        # Window Scanning
        for r in range(ROWS):
            for c in range(COLS - 3):
                window = board[r][c:c+4]
                score += self.evaluate_window(window, piece)
        for c in range(COLS):
            for r in range(ROWS - 3):
                window = [board[r+i][c] for i in range(4)]
                score += self.evaluate_window(window, piece)
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
        if game.check_win(self.player_id) or game.check_win(self.opp_player_id):
            return True
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
                else: return (None, 0)
            else: return (None, self.score_position(game, self.player_id))

        if not valid_locations:
            return (None, 0)

        valid_locations.sort(key=lambda x: abs(x - COLS//2))

        if maximizingPlayer:
            value = -math.inf
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
        valid_moves = game.get_valid_locations()
        if not valid_moves:
            return None

        history = tuple(game.move_history)
        if history in OPENING_BOOK:
            move = OPENING_BOOK[history]
            if game.is_valid_location(move): return move
        
        game_copy = game.clone()
        try:
            col, score = self.minimax(game_copy, self.depth, -math.inf, math.inf, True)
        except Exception as e:
            print(f"[AI ERROR] Minimax crashed: {e}")
            col = None

        if col is None:
            return random.choice(valid_moves)
        
        return col


# =============================================================================
# INSTRUMENTED AI ENGINE - Node Counting & Metrics
# =============================================================================

class InstrumentedAIEngine(AIEngine):
    """Performans metrikleri toplayan AI Engine."""
    
    def __init__(self, player_id, depth=4):
        super().__init__(player_id, depth)
        self.reset_counters()
    
    def reset_counters(self):
        self.nodes_evaluated = 0
        self.alpha_cutoffs = 0
        self.beta_cutoffs = 0
        self.max_depth_reached = 0
        self.terminal_nodes = 0
        self.leaf_evaluations = 0
    
    def minimax(self, game, depth, alpha, beta, maximizingPlayer):
        """Instrumented minimax - node counting ekli."""
        self.nodes_evaluated += 1
        self.max_depth_reached = max(self.max_depth_reached, self.depth - depth)
        
        valid_locations = game.get_valid_locations()
        is_terminal = self.is_terminal_node(game)
        
        if depth == 0 or is_terminal:
            if is_terminal:
                self.terminal_nodes += 1
                if game.check_win(self.player_id): return (None, 100000000000)
                elif game.check_win(self.opp_player_id): return (None, -100000000000)
                else: return (None, 0)
            else: 
                self.leaf_evaluations += 1
                # BUG FIX: score_position kullan, evaluate_position değil!
                return (None, self.score_position(game, self.player_id))

        if not valid_locations:
            return (None, 0)

        valid_locations.sort(key=lambda x: abs(x - COLS//2))

        if maximizingPlayer:
            value = -math.inf
            best_col = random.choice(valid_locations) if valid_locations else None
            for col in valid_locations:
                temp_game = game.clone()
                temp_game.make_move(col)
                new_score = self.minimax(temp_game, depth-1, alpha, beta, False)[1]
                if new_score > value: 
                    value = new_score
                    best_col = col
                alpha = max(alpha, value)
                if alpha >= beta:
                    self.alpha_cutoffs += 1
                    break
            return best_col, value
        else:
            value = math.inf
            best_col = random.choice(valid_locations) if valid_locations else None
            for col in valid_locations:
                temp_game = game.clone()
                temp_game.make_move(col)
                new_score = self.minimax(temp_game, depth-1, alpha, beta, True)[1]
                if new_score < value: 
                    value = new_score
                    best_col = col
                beta = min(beta, value)
                if alpha >= beta:
                    self.beta_cutoffs += 1
                    break
            return best_col, value
    
    def get_metrics(self) -> Dict:
        return {
            'nodes_evaluated': self.nodes_evaluated,
            'alpha_cutoffs': self.alpha_cutoffs,
            'beta_cutoffs': self.beta_cutoffs,
            'total_cutoffs': self.alpha_cutoffs + self.beta_cutoffs,
            'terminal_nodes': self.terminal_nodes,
            'leaf_evaluations': self.leaf_evaluations,
            'max_depth_reached': self.max_depth_reached
        }


# =============================================================================
# DATA CLASSES - Test Results
# =============================================================================

@dataclass
class LatencyResult:
    depth: int
    iteration: int
    latency_ms: float
    nodes_evaluated: int
    cutoffs: int
    move_chosen: int

@dataclass
class TournamentGame:
    depth1: int
    depth2: int
    game_number: int
    winner_depth: Optional[int]
    total_moves: int
    duration_ms: float

@dataclass  
class ScenarioResult:
    scenario_name: str
    depth: int
    latency_ms: float
    move_chosen: int
    nodes_evaluated: int
    expected_optimal: Optional[int]
    is_optimal: bool


# =============================================================================
# TEST SCENARIOS
# =============================================================================

def create_test_scenarios() -> List[Tuple[str, List[int], Optional[int]]]:
    """Test senaryoları: (isim, hamle_listesi, optimal_hamle)"""
    return [
        # Boş tahta
        ("empty_board", [], 3),  # Center optimal
        
        # Erken oyun
        ("early_game_1", [3], 3),
        ("early_game_2", [3, 3], 3),
        ("early_game_3", [3, 2, 3], 3),
        
        # Orta oyun
        ("mid_game_1", [3, 3, 4, 4, 2, 2], None),
        ("mid_game_2", [3, 2, 3, 4, 3, 5], None),
        
        # Kazanma fırsatı (3 taş dizili, 4. hamle açık)
        ("win_opportunity_horizontal", [0, 6, 1, 6, 2, 6], 3),  # Player 1 wins with col 3
        ("win_opportunity_vertical", [3, 0, 3, 1, 3, 2], 3),    # Player 1 wins with col 3
        
        # Bloklama gereken durum
        ("must_block_horizontal", [3, 0, 4, 1, 5, 2], None),  # Must block opponent at 3
        ("must_block_vertical", [0, 3, 1, 3, 2, 3], None),
        
        # Kompleks pozisyonlar
        ("complex_1", [3, 3, 4, 2, 5, 4, 2, 5, 1, 6], None),
        ("complex_2", [3, 2, 4, 4, 2, 3, 5, 5, 1, 1, 6, 0], None),
    ]


# =============================================================================
# PERFORMANCE TEST SUITE
# =============================================================================

class AIPerformanceSuite:
    """Kapsamlı AI Performans Test Paketi."""
    
    def __init__(self, output_dir: str = "./test_results"):
        self.output_dir = output_dir
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.latency_results: List[LatencyResult] = []
        self.tournament_results: List[TournamentGame] = []
        self.scenario_results: List[ScenarioResult] = []
        
        os.makedirs(output_dir, exist_ok=True)
    
    # -------------------------------------------------------------------------
    # TEST 1: Latency Tests
    # -------------------------------------------------------------------------
    def run_latency_tests(self, depths: List[int] = [1, 2, 3, 4, 5, 6], 
                          iterations: int = 10,
                          verbose: bool = True) -> Dict:
        """Her derinlik için latency ölçümü."""
        
        print("\n" + "="*60)
        print("TEST 1: LATENCY ANALYSIS")
        print("="*60)
        
        results_by_depth = {}
        
        for depth in depths:
            if verbose:
                print(f"\n[Depth {depth}] Running {iterations} iterations...")
            
            latencies = []
            nodes_list = []
            
            for i in range(iterations):
                game = ConnectFourGame()
                ai = InstrumentedAIEngine(PLAYER1_PIECE, depth=depth)
                ai.reset_counters()
                
                # Rastgele 3-5 hamle yap (farklı pozisyonlar test et)
                num_random_moves = random.randint(3, 5)
                for _ in range(num_random_moves):
                    valid = game.get_valid_locations()
                    if valid and not game.game_over:
                        game.make_move(random.choice(valid))
                
                if game.game_over:
                    game = ConnectFourGame()  # Reset if game ended
                
                # Latency ölç
                start = time.perf_counter()
                move = ai.find_best_move(game)
                elapsed = (time.perf_counter() - start) * 1000  # ms
                
                metrics = ai.get_metrics()
                
                result = LatencyResult(
                    depth=depth,
                    iteration=i+1,
                    latency_ms=elapsed,
                    nodes_evaluated=metrics['nodes_evaluated'],
                    cutoffs=metrics['total_cutoffs'],
                    move_chosen=move if move is not None else -1
                )
                self.latency_results.append(result)
                latencies.append(elapsed)
                nodes_list.append(metrics['nodes_evaluated'])
            
            # İstatistikler
            results_by_depth[depth] = {
                'mean_ms': statistics.mean(latencies),
                'median_ms': statistics.median(latencies),
                'stdev_ms': statistics.stdev(latencies) if len(latencies) > 1 else 0,
                'min_ms': min(latencies),
                'max_ms': max(latencies),
                'p95_ms': sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) >= 20 else max(latencies),
                'mean_nodes': statistics.mean(nodes_list),
                'total_nodes': sum(nodes_list)
            }
            
            if verbose:
                stats = results_by_depth[depth]
                print(f"    Mean: {stats['mean_ms']:.2f}ms | "
                      f"Median: {stats['median_ms']:.2f}ms | "
                      f"Nodes: {stats['mean_nodes']:.0f}")
        
        return results_by_depth
    
    # -------------------------------------------------------------------------
    # TEST 2: Scenario Tests
    # -------------------------------------------------------------------------
    def run_scenario_tests(self, depths: List[int] = [3, 4, 5],
                           verbose: bool = True) -> List[Dict]:
        """Belirli senaryolarda AI davranış testi."""
        
        print("\n" + "="*60)
        print("TEST 2: SCENARIO ANALYSIS")
        print("="*60)
        
        scenarios = create_test_scenarios()
        results = []
        
        for scenario_name, moves, optimal_move in scenarios:
            for depth in depths:
                # Oyunu hazırla
                game = ConnectFourGame()
                for m in moves:
                    game.make_move(m)
                
                if game.game_over:
                    continue
                
                # AI hamle seçimi
                ai = InstrumentedAIEngine(game.current_player, depth=depth)
                ai.reset_counters()
                
                start = time.perf_counter()
                chosen_move = ai.find_best_move(game)
                elapsed = (time.perf_counter() - start) * 1000
                
                metrics = ai.get_metrics()
                is_optimal = (optimal_move is None) or (chosen_move == optimal_move)
                
                result = ScenarioResult(
                    scenario_name=scenario_name,
                    depth=depth,
                    latency_ms=elapsed,
                    move_chosen=chosen_move if chosen_move is not None else -1,
                    nodes_evaluated=metrics['nodes_evaluated'],
                    expected_optimal=optimal_move,
                    is_optimal=is_optimal
                )
                self.scenario_results.append(result)
                results.append(asdict(result))
                
                if verbose:
                    status = "✓" if is_optimal else "✗"
                    print(f"  [{status}] {scenario_name} (d={depth}): "
                          f"chose={chosen_move}, optimal={optimal_move}, "
                          f"{elapsed:.2f}ms")
        
        return results
    
    # -------------------------------------------------------------------------
    # TEST 3: Round-Robin Tournament
    # -------------------------------------------------------------------------
    def run_tournament(self, depths: List[int] = [2, 3, 4, 5, 6],
                       games_per_matchup: int = 100,
                       verbose: bool = True) -> Dict:
        """Round-robin tournament: each depth pair plays 100 matches."""

        print("\n" + "="*60)
        print("TEST 3: ROUND-ROBIN TOURNAMENT (100 games per matchup)")
        print("="*60)

        win_matrix = {d: {d2: 0 for d2 in depths} for d in depths}
        draw_count = {d: {d2: 0 for d2 in depths} for d in depths}

        total_matchups = len(depths) * (len(depths) - 1) // 2
        matchup_num = 0

        for i, d1 in enumerate(depths):
            for d2 in depths[i+1:]:
                matchup_num += 1

                if verbose:
                    print(f"\n[Matchup {matchup_num}/{total_matchups}] "
                          f"Depth {d1} vs Depth {d2} - Playing 100 games")

                d1_wins = 0
                d2_wins = 0
                draws = 0

                for game_num in range(games_per_matchup):
                    # Alternating colors for fairness (50 games each color)
                    if game_num % 2 == 0:
                        ai1 = AIEngine(PLAYER1_PIECE, depth=d1)
                        ai2 = AIEngine(PLAYER2_PIECE, depth=d2)
                        ai1_player = PLAYER1_PIECE
                    else:
                        ai1 = AIEngine(PLAYER2_PIECE, depth=d1)
                        ai2 = AIEngine(PLAYER1_PIECE, depth=d2)
                        ai1_player = PLAYER2_PIECE

                    game = ConnectFourGame()
                    start_time = time.perf_counter()
                    move_count = 0
                    max_moves = 50  # Safety limit

                    while not game.game_over and move_count < max_moves:
                        if game.current_player == ai1_player:
                            move = ai1.find_best_move(game)
                        else:
                            move = ai2.find_best_move(game)

                        if move is not None:
                            game.make_move(move)
                        else:
                            break
                        move_count += 1

                    duration = (time.perf_counter() - start_time) * 1000

                    # Determine winner
                    winner_depth = None
                    if game.winner == ai1_player:
                        d1_wins += 1
                        winner_depth = d1
                    elif game.winner is not None:
                        d2_wins += 1
                        winner_depth = d2
                    else:
                        draws += 1

                    self.tournament_results.append(TournamentGame(
                        depth1=d1,
                        depth2=d2,
                        game_number=game_num + 1,
                        winner_depth=winner_depth,
                        total_moves=move_count,
                        duration_ms=duration
                    ))

                    if verbose and (game_num + 1) % 10 == 0:
                        print(f"    Progress: {game_num+1}/{games_per_matchup} - "
                              f"D{d1}={d1_wins} | D{d2}={d2_wins} | Draw={draws}",
                              end='\r')

                win_matrix[d1][d2] = d1_wins
                win_matrix[d2][d1] = d2_wins
                draw_count[d1][d2] = draws
                draw_count[d2][d1] = draws

                if verbose:
                    print(f"    Final: D{d1}={d1_wins} | D{d2}={d2_wins} | "
                          f"Draws={draws}                    ")
        
        # Calculate total wins
        total_wins = {d: sum(win_matrix[d].values()) for d in depths}
        
        if verbose:
            print("\n--- TOURNAMENT STANDINGS ---")
            sorted_depths = sorted(total_wins.keys(), key=lambda x: total_wins[x], reverse=True)
            for rank, d in enumerate(sorted_depths, 1):
                print(f"  {rank}. Depth {d}: {total_wins[d]} wins")
        
        return {
            'win_matrix': win_matrix,
            'draw_count': draw_count,
            'total_wins': total_wins,
            'ranking': sorted(total_wins.keys(), key=lambda x: total_wins[x], reverse=True)
        }
    
    # -------------------------------------------------------------------------
    # Export Functions
    # -------------------------------------------------------------------------
    def export_results(self):
        """Tüm sonuçları dosyalara kaydet."""
        
        print("\n" + "="*60)
        print("EXPORTING RESULTS")
        print("="*60)
        
        # 1. Latency CSV
        latency_file = os.path.join(self.output_dir, f"latency_{self.timestamp}.csv")
        with open(latency_file, 'w') as f:
            f.write("depth,iteration,latency_ms,nodes_evaluated,cutoffs,move_chosen\n")
            for r in self.latency_results:
                f.write(f"{r.depth},{r.iteration},{r.latency_ms:.4f},"
                        f"{r.nodes_evaluated},{r.cutoffs},{r.move_chosen}\n")
        print(f"  [✓] Latency data: {latency_file}")
        
        # 2. Tournament CSV
        tournament_file = os.path.join(self.output_dir, f"tournament_{self.timestamp}.csv")
        with open(tournament_file, 'w') as f:
            f.write("depth1,depth2,game_number,winner_depth,total_moves,duration_ms\n")
            for r in self.tournament_results:
                winner = r.winner_depth if r.winner_depth else "draw"
                f.write(f"{r.depth1},{r.depth2},{r.game_number},"
                        f"{winner},{r.total_moves},{r.duration_ms:.2f}\n")
        print(f"  [✓] Tournament data: {tournament_file}")
        
        # 3. Scenario CSV
        scenario_file = os.path.join(self.output_dir, f"scenarios_{self.timestamp}.csv")
        with open(scenario_file, 'w') as f:
            f.write("scenario_name,depth,latency_ms,move_chosen,nodes_evaluated,"
                    "expected_optimal,is_optimal\n")
            for r in self.scenario_results:
                f.write(f"{r.scenario_name},{r.depth},{r.latency_ms:.4f},"
                        f"{r.move_chosen},{r.nodes_evaluated},"
                        f"{r.expected_optimal},{r.is_optimal}\n")
        print(f"  [✓] Scenario data: {scenario_file}")
        
        # 4. JSON Summary
        summary = {
            'timestamp': self.timestamp,
            'test_count': {
                'latency_tests': len(self.latency_results),
                'tournament_games': len(self.tournament_results),
                'scenario_tests': len(self.scenario_results)
            },
            'latency_results': [asdict(r) for r in self.latency_results],
            'tournament_results': [asdict(r) for r in self.tournament_results],
            'scenario_results': [asdict(r) for r in self.scenario_results]
        }
        
        json_file = os.path.join(self.output_dir, f"full_results_{self.timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"  [✓] Full JSON: {json_file}")
        
        return {
            'latency_csv': latency_file,
            'tournament_csv': tournament_file,
            'scenario_csv': scenario_file,
            'json_summary': json_file
        }
    
    # -------------------------------------------------------------------------
    # Full Test Run
    # -------------------------------------------------------------------------
    def run_all_tests(self, 
                      latency_depths: List[int] = [1, 2, 3, 4, 5, 6],
                      latency_iterations: int = 10,
                      tournament_depths: List[int] = [2, 3, 4, 5, 6],
                      tournament_games: int = 10,
                      scenario_depths: List[int] = [3, 4, 5]) -> Dict:
        """Tüm testleri çalıştır."""
        
        print("\n" + "="*60)
        print("AI PERFORMANCE TEST SUITE v3.0")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        start_time = time.time()
        
        # Run tests
        latency_stats = self.run_latency_tests(latency_depths, latency_iterations)
        scenario_results = self.run_scenario_tests(scenario_depths)
        tournament_results = self.run_tournament(tournament_depths, tournament_games)
        
        # Export
        exported_files = self.export_results()
        
        total_time = time.time() - start_time
        
        print("\n" + "="*60)
        print("TEST SUITE COMPLETED")
        print(f"Total time: {total_time:.1f} seconds")
        print("="*60)
        
        return {
            'latency_stats': latency_stats,
            'tournament': tournament_results,
            'exported_files': exported_files,
            'total_time_seconds': total_time
        }


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    # Test suite'i çalıştır
    suite = AIPerformanceSuite(output_dir="./ai_test_results")

    results = suite.run_all_tests(
        latency_depths=[1, 2, 3, 4, 5, 6],
        latency_iterations=10,
        tournament_depths=[2, 3, 4, 5, 6],
        tournament_games=100,  # 100 games per matchup in round-robin
        scenario_depths=[3, 4, 5]
    )
    
    print("\n" + "="*60)
    print("LATENCY SUMMARY BY DEPTH")
    print("="*60)
    for depth, stats in results['latency_stats'].items():
        print(f"Depth {depth}: Mean={stats['mean_ms']:.2f}ms, "
              f"Nodes={stats['mean_nodes']:.0f}")
    
    print("\n" + "="*60)
    print("TOURNAMENT RANKING")
    print("="*60)
    for rank, depth in enumerate(results['tournament']['ranking'], 1):
        wins = results['tournament']['total_wins'][depth]
        print(f"  {rank}. Depth {depth}: {wins} total wins")