#!/usr/bin/env python3
# =============================================================================
# AI PERFORMANCE TEST SUITE v3.1 - THESIS EDITION
# Connect Four Bitirme Projesi - AI Performans Analizi
# =============================================================================
#
# Bu test suite aşağıdaki metrikleri ölçer:
# 1. Minimax + Alpha-Beta Latency (Depth 1-7)
# 2. Node Evaluation Count & Alpha-Beta Cutoff Efficiency
# 3. AI vs AI Tournament (Round-Robin)
# 4. Critical Position Scenario Tests
#
# Kullanım: python ai_performance_suite.py
# Çıktılar: ./test_results/ dizinine kaydedilir
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
# GAME CORE + AI ENGINE - src/ klasorundeki asil koddan import edilir
# (Boylece olcumler oyunda kullanilan motorun kendisi uzerinde yapilir)
# =============================================================================

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src'))

from game_core import ConnectFourGame, ROWS, COLS, PLAYER1_PIECE, PLAYER2_PIECE  # noqa: E402
from ai_vs_human import AIEngine  # noqa: E402


class AIEngineWithMetrics(AIEngine):
    """Asil AIEngine; nodes_evaluated ve cutoffs metrikleri motorun icinde tutulur."""

    def __init__(self, player_id, depth=4):
        super().__init__(player_id, depth=depth)


# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LatencyResult:
    depth: int
    iteration: int
    latency_ms: float
    nodes_evaluated: int
    cutoffs: int
    move_chosen: int
    game_phase: str  # 'early', 'mid', 'late'

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
    expected_optimal: int
    is_optimal: bool


# =============================================================================
# TEST SUITE
# =============================================================================

class AIPerformanceSuite:
    """Comprehensive AI Performance Test Suite."""
    
    def __init__(self, output_dir: str = "./test_results"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Results storage
        self.latency_results: List[LatencyResult] = []
        self.tournament_results: List[TournamentGame] = []
        self.scenario_results: List[ScenarioResult] = []
    
    # -------------------------------------------------------------------------
    # Test 1: Latency Tests
    # -------------------------------------------------------------------------
    def run_latency_tests(self, depths: List[int] = [1, 2, 3, 4, 5, 6, 7], 
                          iterations: int = 20,
                          verbose: bool = True) -> Dict:
        """Measure AI response time for different depths."""
        
        if verbose:
            print("\n" + "="*60)
            print("TEST 1: AI LATENCY ANALYSIS")
            print("="*60)
        
        stats = {}
        
        for depth in depths:
            if verbose:
                print(f"\n  Testing Depth {depth}...")
            
            latencies = []
            nodes_list = []
            cutoffs_list = []
            
            for i in range(iterations):
                # Create game with random early/mid/late phase
                game = ConnectFourGame()
                
                # Determine game phase
                if i < iterations // 3:
                    # Early game (0-8 moves)
                    num_random_moves = random.randint(0, 8)
                    phase = 'early'
                elif i < 2 * iterations // 3:
                    # Mid game (9-20 moves)
                    num_random_moves = random.randint(9, 20)
                    phase = 'mid'
                else:
                    # Late game (21-30 moves)
                    num_random_moves = random.randint(21, 30)
                    phase = 'late'
                
                # Make random moves
                for _ in range(num_random_moves):
                    valid = game.get_valid_locations()
                    if not valid or game.game_over:
                        break
                    game.make_move(random.choice(valid))
                
                if game.game_over:
                    continue
                
                # Test AI
                ai = AIEngineWithMetrics(game.current_player, depth=depth)
                
                start_time = time.perf_counter()
                move = ai.find_best_move(game)
                end_time = time.perf_counter()
                
                latency_ms = (end_time - start_time) * 1000
                
                if move is not None:
                    latencies.append(latency_ms)
                    nodes_list.append(ai.nodes_evaluated)
                    cutoffs_list.append(ai.cutoffs)
                    
                    self.latency_results.append(LatencyResult(
                        depth=depth,
                        iteration=i,
                        latency_ms=latency_ms,
                        nodes_evaluated=ai.nodes_evaluated,
                        cutoffs=ai.cutoffs,
                        move_chosen=move,
                        game_phase=phase
                    ))
                
                if verbose and (i + 1) % 5 == 0:
                    print(f"    Progress: {i+1}/{iterations}", end='\r')
            
            if latencies:
                stats[depth] = {
                    'mean_ms': statistics.mean(latencies),
                    'median_ms': statistics.median(latencies),
                    'min_ms': min(latencies),
                    'max_ms': max(latencies),
                    'stdev_ms': statistics.stdev(latencies) if len(latencies) > 1 else 0,
                    'p95_ms': sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
                    'p99_ms': sorted(latencies)[int(len(latencies) * 0.99)] if latencies else 0,
                    'mean_nodes': statistics.mean(nodes_list),
                    'mean_cutoffs': statistics.mean(cutoffs_list),
                    'samples': len(latencies)
                }
                
                if verbose:
                    print(f"    Depth {depth}: Mean={stats[depth]['mean_ms']:.2f}ms, "
                          f"P95={stats[depth]['p95_ms']:.2f}ms, "
                          f"Nodes={stats[depth]['mean_nodes']:.0f}")
        
        return stats
    
    # -------------------------------------------------------------------------
    # Test 2: Scenario Tests
    # -------------------------------------------------------------------------
    def run_scenario_tests(self, depths: List[int] = [3, 4, 5, 6],
                           verbose: bool = True) -> List[Dict]:
        """Test AI on critical game scenarios."""
        
        if verbose:
            print("\n" + "="*60)
            print("TEST 2: CRITICAL SCENARIO TESTS")
            print("="*60)
        
        # Define test scenarios
        scenarios = [
            {
                'name': 'Win in 1',
                'moves': [3, 0, 3, 1, 3, 2],  # P1 has 3 in column 3
                'expected': 3,  # P1 should complete 4
                'player': PLAYER1_PIECE
            },
            {
                'name': 'Block Opponent Win',
                'moves': [3, 0, 4, 0, 5],  # P2 has 3 in column 0
                'expected': 0,  # P1 should block at column 0
                'player': PLAYER1_PIECE
            },
            {
                'name': 'Center Control',
                'moves': [],  # Empty board
                'expected': 3,  # Should play center
                'player': PLAYER1_PIECE
            },
            {
                'name': 'Fork Creation',
                'moves': [3, 0, 2, 1, 4, 6],  # Setup for fork
                'expected': 3,  # Build toward double threat
                'player': PLAYER1_PIECE
            },
            {
                'name': 'Diagonal Defense',
                'moves': [3, 2, 3, 2, 3],  # P2 threatens diagonal
                'expected': 2,  # Block diagonal
                'player': PLAYER2_PIECE
            }
        ]
        
        results = []
        
        for scenario in scenarios:
            if verbose:
                print(f"\n  Scenario: {scenario['name']}")
            
            for depth in depths:
                game = ConnectFourGame()
                
                # Apply moves
                for move in scenario['moves']:
                    game.make_move(move)
                
                if game.game_over:
                    continue
                
                # Test AI
                ai = AIEngineWithMetrics(scenario['player'], depth=depth)
                
                start_time = time.perf_counter()
                chosen_move = ai.find_best_move(game)
                end_time = time.perf_counter()
                
                latency_ms = (end_time - start_time) * 1000
                is_optimal = (chosen_move == scenario['expected'])
                
                result = ScenarioResult(
                    scenario_name=scenario['name'],
                    depth=depth,
                    latency_ms=latency_ms,
                    move_chosen=chosen_move if chosen_move else -1,
                    nodes_evaluated=ai.nodes_evaluated,
                    expected_optimal=scenario['expected'],
                    is_optimal=is_optimal
                )
                self.scenario_results.append(result)
                results.append(asdict(result))
                
                status = "✓" if is_optimal else "✗"
                if verbose:
                    print(f"    Depth {depth}: {status} Chose={chosen_move}, "
                          f"Expected={scenario['expected']}, {latency_ms:.2f}ms")
        
        return results
    
    # -------------------------------------------------------------------------
    # Test 3: AI Tournament
    # -------------------------------------------------------------------------
    def run_tournament(self, depths: List[int] = [2, 3, 4, 5, 6],
                       games_per_matchup: int = 20,
                       verbose: bool = True) -> Dict:
        """Round-robin tournament between AI of different depths."""
        
        if verbose:
            print("\n" + "="*60)
            print("TEST 3: AI vs AI TOURNAMENT")
            print("="*60)
        
        win_matrix = {d: {d2: 0 for d2 in depths} for d in depths}
        draw_count = {d: {d2: 0 for d2 in depths} for d in depths}
        
        total_matchups = len(depths) * (len(depths) - 1) // 2
        current_matchup = 0
        
        for i, d1 in enumerate(depths):
            for d2 in depths[i+1:]:
                current_matchup += 1
                if verbose:
                    print(f"\n  Matchup {current_matchup}/{total_matchups}: Depth {d1} vs Depth {d2}")
                
                d1_wins = 0
                d2_wins = 0
                draws = 0
                
                for game_num in range(games_per_matchup):
                    # Alternate who goes first
                    if game_num % 2 == 0:
                        ai1 = AIEngineWithMetrics(PLAYER1_PIECE, depth=d1)
                        ai2 = AIEngineWithMetrics(PLAYER2_PIECE, depth=d2)
                        ai1_player = PLAYER1_PIECE
                    else:
                        ai1 = AIEngineWithMetrics(PLAYER2_PIECE, depth=d1)
                        ai2 = AIEngineWithMetrics(PLAYER1_PIECE, depth=d2)
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

                    if verbose and (game_num + 1) % 5 == 0:
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
        """Export all results to files."""
        
        print("\n" + "="*60)
        print("EXPORTING RESULTS")
        print("="*60)
        
        # 1. Latency CSV
        latency_file = os.path.join(self.output_dir, f"ai_latency_{self.timestamp}.csv")
        with open(latency_file, 'w') as f:
            f.write("depth,iteration,latency_ms,nodes_evaluated,cutoffs,move_chosen,game_phase\n")
            for r in self.latency_results:
                f.write(f"{r.depth},{r.iteration},{r.latency_ms:.4f},"
                        f"{r.nodes_evaluated},{r.cutoffs},{r.move_chosen},{r.game_phase}\n")
        print(f"  [OK] Latency data: {latency_file}")
        
        # 2. Tournament CSV
        tournament_file = os.path.join(self.output_dir, f"ai_tournament_{self.timestamp}.csv")
        with open(tournament_file, 'w') as f:
            f.write("depth1,depth2,game_number,winner_depth,total_moves,duration_ms\n")
            for r in self.tournament_results:
                winner = r.winner_depth if r.winner_depth else "draw"
                f.write(f"{r.depth1},{r.depth2},{r.game_number},"
                        f"{winner},{r.total_moves},{r.duration_ms:.2f}\n")
        print(f"  [OK] Tournament data: {tournament_file}")
        
        # 3. Scenario CSV
        scenario_file = os.path.join(self.output_dir, f"ai_scenarios_{self.timestamp}.csv")
        with open(scenario_file, 'w') as f:
            f.write("scenario_name,depth,latency_ms,move_chosen,nodes_evaluated,"
                    "expected_optimal,is_optimal\n")
            for r in self.scenario_results:
                f.write(f"{r.scenario_name},{r.depth},{r.latency_ms:.4f},"
                        f"{r.move_chosen},{r.nodes_evaluated},"
                        f"{r.expected_optimal},{r.is_optimal}\n")
        print(f"  [OK] Scenario data: {scenario_file}")
        
        # 4. JSON Summary
        summary = {
            'timestamp': self.timestamp,
            'test_count': {
                'latency_tests': len(self.latency_results),
                'tournament_games': len(self.tournament_results),
                'scenario_tests': len(self.scenario_results)
            },
            'latency_summary': self._calculate_latency_summary(),
            'latency_results': [asdict(r) for r in self.latency_results],
            'tournament_results': [asdict(r) for r in self.tournament_results],
            'scenario_results': [asdict(r) for r in self.scenario_results]
        }
        
        json_file = os.path.join(self.output_dir, f"ai_results_{self.timestamp}.json")
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, indent=2, ensure_ascii=False)
        print(f"  [OK] Full JSON: {json_file}")
        
        return {
            'latency_csv': latency_file,
            'tournament_csv': tournament_file,
            'scenario_csv': scenario_file,
            'json_summary': json_file
        }
    
    def _calculate_latency_summary(self) -> Dict:
        """Calculate summary statistics for latency results."""
        summary = {}
        depths = set(r.depth for r in self.latency_results)
        
        for depth in sorted(depths):
            depth_results = [r.latency_ms for r in self.latency_results if r.depth == depth]
            if depth_results:
                sorted_latencies = sorted(depth_results)
                summary[str(depth)] = {
                    'mean_ms': round(statistics.mean(depth_results), 2),
                    'median_ms': round(statistics.median(depth_results), 2),
                    'min_ms': round(min(depth_results), 2),
                    'max_ms': round(max(depth_results), 2),
                    'stdev_ms': round(statistics.stdev(depth_results), 2) if len(depth_results) > 1 else 0,
                    'p95_ms': round(sorted_latencies[int(len(sorted_latencies) * 0.95)], 2),
                    'p99_ms': round(sorted_latencies[min(int(len(sorted_latencies) * 0.99), len(sorted_latencies)-1)], 2),
                    'samples': len(depth_results)
                }
        return summary
    
    # -------------------------------------------------------------------------
    # Full Test Run
    # -------------------------------------------------------------------------
    def run_all_tests(self, 
                      latency_depths: List[int] = [1, 2, 3, 4, 5, 6, 7],
                      latency_iterations: int = 20,
                      tournament_depths: List[int] = [2, 3, 4, 5, 6],
                      tournament_games: int = 20,
                      scenario_depths: List[int] = [3, 4, 5, 6]) -> Dict:
        """Run all tests."""
        
        print("\n" + "="*60)
        print("AI PERFORMANCE TEST SUITE v3.1")
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
    print("="*60)
    print("  CONNECT FOUR - AI PERFORMANCE TEST SUITE")
    print("="*60)
    
    suite = AIPerformanceSuite(output_dir="./test_results")

    results = suite.run_all_tests(
        latency_depths=[1, 2, 3, 4, 5, 6, 7],  # Including depth 7
        latency_iterations=20,
        tournament_depths=[2, 3, 4, 5, 6],
        tournament_games=20,
        scenario_depths=[3, 4, 5, 6]
    )
    
    print("\n" + "="*60)
    print("LATENCY SUMMARY BY DEPTH")
    print("="*60)
    for depth, stats in results['latency_stats'].items():
        print(f"  Depth {depth}: Mean={stats['mean_ms']:.2f}ms, "
              f"P95={stats['p95_ms']:.2f}ms, Nodes={stats['mean_nodes']:.0f}")
    
    print("\n" + "="*60)
    print("TOURNAMENT RANKING")
    print("="*60)
    for rank, depth in enumerate(results['tournament']['ranking'], 1):
        wins = results['tournament']['total_wins'][depth]
        print(f"  {rank}. Depth {depth}: {wins} total wins")
    
    print("\n" + "="*60)
    print(f"Results saved to: ./test_results/")
    print("="*60)
