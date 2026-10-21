#!/usr/bin/env python3
# =============================================================================
# AI PERFORMANCE SUITE v4.0
# Connect Four Pro - AI performans analizi (src/ai_vs_human.py'deki gercek motor)
# =============================================================================
"""
Olculenler:
  1. Gecikme ve hesaplama karmasikligi (derinlik 1-7): ms, ziyaret edilen dugum,
     alpha-beta budama sayisi, dugum basina sure. Acilis kitabi KAPALI (saf arama).
  2. Taktik senaryolar: dogru cevap kumesi kisa bir kesin arama (zorla kazanc/kayip
     cozucu) ile hesaplanir; AI'nin secimi bu kumeyle karsilastirilir.
  3. Turnuva: her eslesme farkli rastgele acilislardan oynanir; her acilis renkler
     degistirilerek iki kez oynanir (AI deterministik oldugu icin gerekli).

Kullanim:
    python ai_performance_suite.py                 # tam calistirma
    python ai_performance_suite.py --quick         # hizli kontrol
    python ai_performance_suite.py --seed 7 --iterations 45
"""

import argparse
import random
import time
from typing import Dict, List, Optional, Tuple

import bench_common as bc
from ai_vs_human import BOARD_MASK, BOTTOM_MASK, AIEngine, winning_cells
from game_core import PLAYER1_PIECE, PLAYER2_PIECE, ConnectFourGame

PHASES = {'early': (2, 8), 'mid': (9, 20), 'late': (21, 30)}


# =============================================================================
# KESIN ARAMA (senaryo dogrulama)
# =============================================================================

def forced_outcome(game: ConnectFourGame, plies: int) -> int:
    """Sirasi gelen icin `plies` yari-hamle icinde: +1 zorla kazanc, -1 zorla kayip, 0 belirsiz."""
    moves = game.get_valid_locations()
    if plies == 0 or not moves:
        return 0
    best = -1
    for col in moves:
        child = game.clone()
        child.make_move(col)
        value = 1 if child.winner is not None else -forced_outcome(child, plies - 1)
        best = max(best, value)
        if best == 1:
            break
    return best


def acceptable_moves(game: ConnectFourGame, plies: int = 4) -> Tuple[List[int], Dict[int, int]]:
    """Kesin aramaya gore en iyi sonucu veren hamleler ve her hamlenin degeri."""
    values = {}
    for col in game.get_valid_locations():
        child = game.clone()
        child.make_move(col)
        values[col] = 1 if child.winner is not None else -forced_outcome(child, plies - 1)
    best = max(values.values())
    return sorted(c for c, v in values.items() if v == best), values


# Taktik senaryolar (hamle dizileri dogrulanmis; cevaplar calisma aninda hesaplanir)
SCENARIOS = [
    {'name': 'Win in 1 (vertical)', 'moves': [3, 0, 3, 1, 3, 2]},
    {'name': 'Win in 1 (horizontal)', 'moves': [0, 0, 1, 1, 2, 2]},
    {'name': 'Win in 1 (diagonal)', 'moves': [0, 1, 1, 2, 2, 3, 2, 3, 3, 6]},
    {'name': 'Block (vertical)', 'moves': [0, 3, 1, 3, 6, 3]},
    {'name': 'Block (horizontal)', 'moves': [6, 0, 6, 1, 5, 2]},
    {'name': 'Block (diagonal)', 'moves': [4, 0, 2, 3, 6, 5, 1, 2, 3, 4, 1, 5, 2, 2, 5, 4]},
    {'name': 'Win before block', 'moves': [0, 6, 0, 6, 0, 6]},
    {'name': 'Avoid trap square', 'moves': [3, 5, 1, 4, 5, 0, 0, 5, 3, 0, 6]},
    {'name': 'Double threat (win in 3)', 'moves': [4, 0, 3, 1, 1, 6, 3, 1, 4, 6]},
]


# =============================================================================
# SUITE
# =============================================================================

class AIPerformanceSuite:
    def __init__(self, seed: int = 2024):
        self.seed = seed
        self.latency_samples: List[dict] = []
        self.scenario_results: List[dict] = []
        self.tournament_games: List[dict] = []

    # ------------------------------------------------------------------
    @staticmethod
    def random_position(rng: random.Random, n_moves: int) -> Optional[ConnectFourGame]:
        """
        Rastgele hamlelerle SAKIN pozisyon: oyun bitmemis ve iki tarafin da oynanabilir
        kazanma hucresi yok. (Tehdit olan pozisyonlarda motor aramadan cevap verir;
        bunlar dahil edilirse olcum arama maliyetini degil kisayolu olcer.)
        """
        for _ in range(1000):
            g = ConnectFourGame()
            for _ in range(n_moves):
                g.make_move(rng.choice(g.get_valid_locations()))
                if g.game_over:
                    break
            if g.game_over:
                continue
            mask = g.bitboards[1] | g.bitboards[2]
            playable = (mask + BOTTOM_MASK) & BOARD_MASK
            if not any(winning_cells(g.bitboards[p], mask) & playable for p in (1, 2)):
                return g
        return None

    def run_latency(self, depths: List[int], iterations: int) -> Dict[str, dict]:
        bc.progress("\n[1/3] Gecikme ve karmasiklik (acilis kitabi kapali)")
        rng = random.Random(self.seed)
        per_phase = max(1, iterations // len(PHASES))
        # Tum derinlikler AYNI pozisyonlarda olculur (karsilastirilabilirlik)
        positions = []
        for phase, (lo, hi) in PHASES.items():
            for _ in range(per_phase):
                g = self.random_position(rng, rng.randint(lo, hi))
                if g:
                    positions.append((phase, g))

        summary = {}
        for depth in depths:
            times, nodes, cutoffs = [], [], []
            for i, (phase, game) in enumerate(positions):
                ai = AIEngine(game.current_player, depth=depth, use_opening_book=False)
                t0 = time.perf_counter()
                move = ai.find_best_move(game)
                ms = (time.perf_counter() - t0) * 1000
                assert move in game.get_valid_locations()
                times.append(ms)
                nodes.append(ai.nodes_evaluated)
                cutoffs.append(ai.cutoffs)
                self.latency_samples.append({'depth': depth, 'position': i, 'phase': phase,
                                             'moves_played': len(game.move_history), 'latency_ms': ms,
                                             'nodes': ai.nodes_evaluated, 'cutoffs': ai.cutoffs})
            stats = bc.summarize(times)
            stats.update(
                mean_nodes=sum(nodes) / len(nodes),
                max_nodes=max(nodes),
                mean_cutoffs=sum(cutoffs) / len(cutoffs),
                us_per_node=sum(times) * 1000 / max(sum(nodes), 1),
                by_phase={p: bc.summarize([t for t, (ph, _) in zip(times, positions, strict=True) if ph == p])['mean']
                          for p in PHASES},
            )
            summary[str(depth)] = stats
            bc.progress(f"  D{depth}: ort {stats['mean']:8.2f} ms | p95 {stats['p95']:8.2f} ms | "
                        f"dugum {stats['mean_nodes']:9.0f} | {stats['us_per_node']:.1f} us/dugum")
        return summary

    # ------------------------------------------------------------------
    def run_scenarios(self, depths: List[int]) -> None:
        bc.progress("\n[2/3] Taktik senaryolar (cevaplar kesin aramayla dogrulanir)")
        for sc in SCENARIOS:
            game = ConnectFourGame.from_moves(sc['moves'])
            accept, values = acceptable_moves(game)
            assert len(accept) < len(values), f"{sc['name']}: ayirt edici degil"
            row = []
            for depth in depths:
                ai = AIEngine(game.current_player, depth=depth, use_opening_book=False)
                t0 = time.perf_counter()
                move = ai.find_best_move(game)
                ms = (time.perf_counter() - t0) * 1000
                ok = move in accept
                self.scenario_results.append({'scenario': sc['name'], 'depth': depth, 'move': move,
                                              'acceptable': accept, 'correct': ok, 'latency_ms': ms,
                                              'nodes': ai.nodes_evaluated})
                row.append(f"D{depth}:{'OK' if ok else 'X'}({move})")
            bc.progress(f"  {sc['name']:<26} dogru={accept}  " + "  ".join(row))

    # ------------------------------------------------------------------
    def run_tournament(self, depths: List[int], openings: int, opening_plies: int) -> dict:
        bc.progress(f"\n[3/3] Turnuva: {openings} acilis x 2 renk, acilis uzunlugu {opening_plies} yari-hamle")
        rng = random.Random(self.seed + 1)
        opening_list = []
        while len(opening_list) < openings:
            g = self.random_position(rng, opening_plies)
            # Tekrarsiz ve siradaki oyuncunun tek hamlede kazanamadigi acilislar
            if (g and g.move_history not in opening_list
                    and not any(v == 1 for v in acceptable_moves(g, plies=1)[1].values())):
                opening_list.append(g.move_history[:])

        results = {}
        for i, d1 in enumerate(depths):
            for d2 in depths[i:]:
                score = {'d1_wins': 0, 'd2_wins': 0, 'draws': 0}
                for opening in opening_list:
                    for d1_piece in (PLAYER1_PIECE, PLAYER2_PIECE):
                        engines = {d1_piece: AIEngine(d1_piece, d1, use_opening_book=False),
                                   3 - d1_piece: AIEngine(3 - d1_piece, d2, use_opening_book=False)}
                        game = ConnectFourGame.from_moves(opening)
                        t0 = time.perf_counter()
                        while not game.game_over:
                            game.make_move(engines[game.current_player].find_best_move(game))
                        winner = ('draw' if game.winner is None else
                                  'd1' if game.winner == d1_piece else 'd2')
                        score['draws' if winner == 'draw' else f'{winner}_wins'] += 1
                        self.tournament_games.append({
                            'depth1': d1, 'depth2': d2, 'opening': opening, 'depth1_piece': d1_piece,
                            'winner': winner, 'first_player_won': game.winner == PLAYER1_PIECE,
                            'moves': len(game.move_history), 'duration_ms': (time.perf_counter() - t0) * 1000})
                results[f'{d1}-{d2}'] = score
                bc.progress(f"  D{d1} vs D{d2}: {score['d1_wins']:2d}-{score['d2_wins']:2d} "
                            f"(berabere {score['draws']})")

        # Kazanma orani matrisi: satir derinligin, sutun derinlige karsi puani (%) (beraberlik = 0.5)
        matrix = {}
        for d1 in depths:
            matrix[str(d1)] = {}
            for d2 in depths:
                key, flip = (f'{d1}-{d2}', False) if d1 <= d2 else (f'{d2}-{d1}', True)
                s = results[key]
                wins, losses = (s['d2_wins'], s['d1_wins']) if flip else (s['d1_wins'], s['d2_wins'])
                total = wins + losses + s['draws']
                matrix[str(d1)][str(d2)] = 100 * (wins + 0.5 * s['draws']) / total
        first = [g['first_player_won'] for g in self.tournament_games if g['winner'] != 'draw']
        return {'openings': opening_list, 'results': results, 'score_matrix_percent': matrix,
                'first_player_win_rate_percent': 100 * sum(first) / max(len(first), 1),
                'games': len(self.tournament_games)}


def main():
    parser = argparse.ArgumentParser(description='AI Performance Suite v4.0')
    parser.add_argument('--seed', type=int, default=2024)
    parser.add_argument('--iterations', type=int, default=30, help='Derinlik basina pozisyon sayisi')
    parser.add_argument('--max-depth', type=int, default=8)
    parser.add_argument('--openings', type=int, default=10, help='Turnuva eslesmesi basina acilis')
    parser.add_argument('--quick', action='store_true', help='Hizli kontrol (kucuk parametreler)')
    args = parser.parse_args()

    latency_depths = list(range(1, args.max_depth + 1))
    tournament_depths = [2, 3, 4, 5, 6, 8]
    scenario_depths = [1, 2, 3, 4, 6, 8]
    if args.quick:
        args.iterations, args.openings = 6, 2
        latency_depths, tournament_depths, scenario_depths = [1, 2, 3, 4], [2, 4], [2, 4]

    env = bc.environment_info()
    bc.progress(f"AI PERFORMANCE SUITE v4.0 | {env['cpu']} | Python {env['python']} | seed {args.seed}")
    suite = AIPerformanceSuite(seed=args.seed)
    t0 = time.time()
    latency = suite.run_latency(latency_depths, args.iterations)
    suite.run_scenarios(scenario_depths)
    tournament = suite.run_tournament(tournament_depths, args.openings, opening_plies=4)

    scenario_accuracy = {}
    for d in scenario_depths:
        rows = [r for r in suite.scenario_results if r['depth'] == d]
        scenario_accuracy[str(d)] = 100 * sum(r['correct'] for r in rows) / len(rows)

    report = {
        'suite': 'ai_performance', 'version': '4.0', 'environment': env,
        'parameters': {'seed': args.seed, 'iterations_per_depth': args.iterations, 'opening_book': False,
                       'latency_depths': latency_depths, 'tournament_depths': tournament_depths,
                       'scenario_depths': scenario_depths, 'openings_per_matchup': args.openings,
                       'quick': args.quick},
        'duration_seconds': time.time() - t0,
        'latency_summary': latency,
        'scenario_accuracy_percent': scenario_accuracy,
        'scenario_results': suite.scenario_results,
        'tournament': tournament,
        'latency_samples': suite.latency_samples,
        'tournament_games': suite.tournament_games,
    }
    path = bc.save_json('ai_results.json', bc.rounded(report))
    bc.progress(f"\nSure: {report['duration_seconds']:.0f} sn | Sonuc: {path}")


if __name__ == '__main__':
    main()
