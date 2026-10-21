#!/usr/bin/env python3
# =============================================================================
# AI QUALITY BENCHMARK v1.0
# Connect Four Pro - AI hamle kalitesinin kusursuz cozucuyle olculmesi
# =============================================================================
"""
Connect Four cozulmus bir oyundur; her pozisyonun kesin degeri bir "kusursuz
cozucu" ile hesaplanabilir. Bu benchmark AI'nin hamlelerini o degerlerle
karsilastirir:

  * Optimal hamle orani      : secilen hamle en iyi skoru mu veriyor?
  * Sonucu koruma orani      : kazanilan oyun kazanilmis, berabere oyun berabere kaliyor mu?
  * Hata (blunder) orani     : hamle oyunun teorik sonucunu kotulestiriyor mu?
Sadece KRITIK pozisyonlar sayilir (hamle secimi sonucu degistirebiliyorsa).

Ayrica: acilis kitabi dogrulamasi, kusursuz rakibe karsi berabere acilislardan
beraberligi koruma, v2 - v1 karsilasmalari.

Gereken cozucu (repoya DAHIL DEGIL, AGPL-3.0): Pascal Pons, connect4.gamesolver.org
    git clone https://github.com/PascalPons/connect4 && cd connect4 && make
    curl -LO https://github.com/PascalPons/connect4/releases/download/book/7x6.book

Kullanim:
    python ai_quality_benchmark.py --solver-dir /yol/connect4
    python ai_quality_benchmark.py --solver-dir /yol/connect4 --quick
"""

import argparse
import os
import random
import subprocess
import time
from typing import Dict, List, Optional

import bench_common as bc
from ai_vs_human import OPENING_BOOK, AIEngine
from game_core import ConnectFourGame
from legacy_ai_v1 import OPENING_BOOK as V1_OPENING_BOOK
from legacy_ai_v1 import LegacyAIEngine

CENTER_ORDER = (3, 2, 4, 1, 5, 0, 6)
ENGINES = {'v1': LegacyAIEngine, 'v2': AIEngine}


class Oracle:
    """Kusursuz cozucu (c4solver -a): her sutun icin sirasi gelen acisindan kesin skor."""

    def __init__(self, solver_dir: str):
        exe = os.path.join(solver_dir, 'c4solver')
        if not os.path.exists(exe):
            raise SystemExit(f"Cozucu bulunamadi: {exe} (bkz. dosya basindaki kurulum)")
        self.proc = subprocess.Popen([exe, '-a'], cwd=solver_dir, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.DEVNULL, text=True, bufsize=1)
        self.cache: Dict[str, List[Optional[int]]] = {}

    def scores(self, moves: List[int]) -> List[Optional[int]]:
        seq = ''.join(str(c + 1) for c in moves)
        if seq not in self.cache:
            self.proc.stdin.write(seq + '\n')
            self.proc.stdin.flush()
            parts = self.proc.stdout.readline().split()
            values = parts[1:] if seq else parts
            self.cache[seq] = [None if v == '-1000' else int(v) for v in values]
        return self.cache[seq]

    def best(self, moves):
        s = self.scores(moves)
        top = max(v for v in s if v is not None)
        return top, [c for c in CENTER_ORDER if s[c] == top]


def sign(x: int) -> int:
    return (x > 0) - (x < 0)


def phase_of(n_moves: int) -> str:
    return 'erken' if n_moves < 10 else ('orta' if n_moves < 20 else 'gec')


# =============================================================================
# POZISYON KUMELERI
# =============================================================================

def random_play_positions(n: int, seed: int) -> List[ConnectFourGame]:
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        g = ConnectFourGame()
        for _ in range(rng.randint(2, 30)):
            g.make_move(rng.choice(g.get_valid_locations()))
            if g.game_over:
                break
        if not g.game_over:
            out.append(g)
    return out


def game_positions(n: int, seed: int) -> List[ConnectFourGame]:
    """Gercekci pozisyonlar: v2 D2'nin %25 rastgele hamleyle oynadigi oyunlardan."""
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        g = ConnectFourGame()
        while not g.game_over and len(out) < n:
            if g.move_count >= 2:
                out.append(g.clone())
            if rng.random() < 0.25:
                g.make_move(rng.choice(g.get_valid_locations()))
            else:
                g.make_move(AIEngine(g.current_player, 2, use_opening_book=False).find_best_move(g))
    return out


def critical(oracle: Oracle, positions: List[ConnectFourGame]):
    result = []
    for g in positions:
        s = oracle.scores(g.move_history)
        if len({sign(v) for v in s if v is not None}) > 1:
            result.append((g, s))
    return result


# =============================================================================
# OLCUMLER
# =============================================================================

def move_quality(engine_name: str, depth: int, dataset) -> Dict:
    cls = ENGINES[engine_name]
    optimal = keep = 0
    times = []
    phases: Dict[str, List[int]] = {}
    for g, s in dataset:
        t0 = time.perf_counter()
        move = cls(g.current_player, depth, use_opening_book=False).find_best_move(g)
        times.append((time.perf_counter() - t0) * 1000)
        best = max(v for v in s if v is not None)
        ok = sign(s[move]) == sign(best)
        optimal += s[move] == best
        keep += ok
        phases.setdefault(phase_of(g.move_count), []).append(ok)
    n = len(dataset)
    result = {'n': n, 'optimal_percent': 100 * optimal / n, 'value_kept_percent': 100 * keep / n,
              'blunder_percent': 100 - 100 * keep / n, 'time_ms': bc.summarize(times),
              'by_phase': {p: {'n': len(v), 'value_kept_percent': 100 * sum(v) / len(v)} for p, v in phases.items()}}
    bc.progress(f"  {engine_name} D{depth}: optimal %{result['optimal_percent']:.0f} | sonucu koruyan "
                f"%{result['value_kept_percent']:.0f} | hata %{result['blunder_percent']:.0f} | "
                f"ort {result['time_ms']['mean']:.0f} ms")
    return result


def verify_book(oracle: Oracle, book: Dict) -> Dict:
    wrong = []
    for history, move in book.items():
        top, best = oracle.best(list(history))
        score = oracle.scores(list(history))[move]
        if score != top:
            wrong.append({'history': list(history), 'book_move': move, 'book_score': score,
                          'best_moves': best, 'best_score': top,
                          'changes_result': sign(score) != sign(top)})
    return {'entries': len(book), 'wrong': len(wrong), 'details': wrong}


def draw_openings(oracle: Oracle, n: int, seed: int) -> List[List[int]]:
    rng = random.Random(seed)
    out = []
    while len(out) < n:
        g = ConnectFourGame()
        for _ in range(4):
            g.make_move(rng.choice(g.get_valid_locations()))
        if not g.game_over and oracle.best(g.move_history)[0] == 0 and g.move_history not in out:
            out.append(g.move_history[:])
    return out


def play(players, opening):
    g = ConnectFourGame.from_moves(opening)
    while not g.game_over:
        g.make_move(players[g.current_player](g))
    return g


def engine_player(name, depth, piece):
    engine = ENGINES[name](piece, depth)
    return engine.find_best_move


def versus_perfect(oracle, name, depth, openings) -> Dict:
    def perfect(g):
        return oracle.best(g.move_history)[1][0]

    held, survived = 0, []
    for op in openings:
        for ai_piece in (1, 2):
            players = {ai_piece: engine_player(name, depth, ai_piece), 3 - ai_piece: perfect}
            g = play(players, op)
            if g.winner is None or g.winner == ai_piece:
                held += 1
            else:
                survived.append(g.move_count)
    total = 2 * len(openings)
    res = {'games': total, 'draw_held_percent': 100 * held / total,
           'mean_moves_before_loss': sum(survived) / len(survived) if survived else None}
    bc.progress(f"  {name} D{depth} vs kusursuz: beraberligi koruma %{res['draw_held_percent']:.0f} "
                f"({held}/{total})")
    return res


def head_to_head(a, b, openings) -> Dict:
    (na, da), (nb, db) = a, b
    score = {'a_wins': 0, 'b_wins': 0, 'draws': 0}
    for op in openings:
        for a_piece in (1, 2):
            g = play({a_piece: engine_player(na, da, a_piece), 3 - a_piece: engine_player(nb, db, 3 - a_piece)}, op)
            key = 'draws' if g.winner is None else ('a_wins' if g.winner == a_piece else 'b_wins')
            score[key] += 1
    bc.progress(f"  {na} D{da} vs {nb} D{db}: {score['a_wins']}-{score['b_wins']} (berabere {score['draws']})")
    return {'a': f'{na} D{da}', 'b': f'{nb} D{db}', **score}


def main():
    parser = argparse.ArgumentParser(description='AI kalite benchmarki (kusursuz cozucuye karsi)')
    parser.add_argument('--solver-dir', required=True, help='c4solver ve 7x6.book iceren klasor')
    parser.add_argument('--positions', type=int, default=300)
    parser.add_argument('--openings', type=int, default=10)
    parser.add_argument('--seed', type=int, default=11)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()
    v1_depths, v2_depths = [2, 4, 6], [2, 4, 6, 8]
    if args.quick:
        args.positions, args.openings, v1_depths, v2_depths = 60, 2, [2, 4], [2, 4]

    env = bc.environment_info()
    bc.progress(f"AI QUALITY BENCHMARK | {env['cpu']} | seed {args.seed}")
    oracle = Oracle(args.solver_dir)
    t0 = time.time()

    bc.progress("\n[1/4] Acilis kitabi dogrulamasi")
    books = {'v1': verify_book(oracle, V1_OPENING_BOOK), 'v2': verify_book(oracle, OPENING_BOOK)}
    for k, b in books.items():
        bc.progress(f"  {k}: {b['entries']} giris, {b['wrong']} hatali "
                    f"({sum(d['changes_result'] for d in b['details'])} tanesi oyunun sonucunu degistiriyor)")

    datasets = {
        'random_play': critical(oracle, random_play_positions(args.positions, args.seed)),
        'game_play': critical(oracle, game_positions(args.positions, args.seed + 1)),
    }
    quality = {}
    for set_name, data in datasets.items():
        bc.progress(f"\n[2/4] Hamle kalitesi - {set_name} ({len(data)} kritik pozisyon)")
        quality[set_name] = {}
        for name, depths in (('v1', v1_depths), ('v2', v2_depths)):
            for d in depths:
                quality[set_name][f'{name}_D{d}'] = move_quality(name, d, data)

    openings = draw_openings(oracle, args.openings, args.seed + 2)
    bc.progress(f"\n[3/4] Kusursuz rakibe karsi ({len(openings)} berabere acilis x 2 renk)")
    perfect = {f'{n}_D{d}': versus_perfect(oracle, n, d, openings)
               for n, d in [('v1', max(v1_depths))] + [('v2', d) for d in v2_depths[1:]]}

    bc.progress("\n[4/4] v2 - v1 karsilasmalari")
    pairs = [(d, d) for d in v1_depths]
    if max(v2_depths) != max(v1_depths):
        pairs.append((max(v2_depths), max(v1_depths)))     # Zor seviye: v2 D8 - v1 D6
    h2h = [head_to_head(('v2', a), ('v1', b), openings) for a, b in pairs]

    report = {'suite': 'ai_quality', 'version': '1.0', 'environment': env,
              'parameters': {'seed': args.seed, 'positions_per_set': args.positions, 'openings': openings,
                             'v1_depths': v1_depths, 'v2_depths': v2_depths, 'quick': args.quick,
                             'oracle': 'Pascal Pons connect4 solver (c4solver -a, 7x6.book)'},
              'opening_books': books, 'move_quality': quality, 'versus_perfect': perfect, 'head_to_head': h2h,
              'duration_seconds': time.time() - t0}
    path = bc.save_json('ai_quality_results.json', bc.rounded(report))
    bc.progress(f"\nSure: {report['duration_seconds']:.0f} sn | Sonuc: {path}")


if __name__ == '__main__':
    main()
