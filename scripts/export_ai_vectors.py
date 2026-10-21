"""
Python AI motorundan "altin vektor" dosyasi uretir: tests/csharp/vectors/ai_vectors.json

C# portu (unity/Assets/Scripts/AI/AIEngine.cs) ayni pozisyonlarda ayni hamleyi,
ayni kok skorunu, ayni ulasilan derinligi ve AYNI dugum sayisini vermek zorundadir.
Dugum sayisinin tutmasi, arama agacinin (siralama, TT, budama) birebir ayni
oldugunu gosterir.

Kullanim:
    python scripts/export_ai_vectors.py
"""

import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

from ai_vs_human import AIEngine, winning_cells  # noqa: E402
from game_core import PLAYER1_PIECE, PLAYER2_PIECE, ConnectFourGame  # noqa: E402

OUT = os.path.join(ROOT, 'tests', 'csharp', 'vectors', 'ai_vectors.json')


def random_live_position(rng, n_moves):
    while True:
        g = ConnectFourGame()
        for _ in range(n_moves):
            if g.game_over:
                break
            g.make_move(rng.choice(g.get_valid_locations()))
        if not g.game_over and g.move_count == n_moves:
            return g


def bits(g):
    mask = g.bitboards[PLAYER1_PIECE] | g.bitboards[PLAYER2_PIECE]
    return g.bitboards[g.current_player], mask


def main():
    rng = random.Random(20261021)
    searches, evals = [], []

    configs = [  # (derinlik, kitap, exact_endgame, pozisyon sayisi, hamle araligi)
        (1, False, False, 20, (0, 30)),
        (2, False, False, 20, (0, 30)),
        (4, False, False, 20, (0, 30)),
        (6, False, None, 15, (2, 30)),
        (8, True, None, 15, (0, 30)),
        (8, False, None, 10, (2, 20)),
        (2, False, True, 10, (30, 34)),    # kesin oyun sonu
    ]
    for depth, book, exact, count, (lo, hi) in configs:
        for _ in range(count):
            g = random_live_position(rng, rng.randint(lo, hi))
            ai = AIEngine(g.current_player, depth=depth, use_opening_book=book, exact_endgame=exact)
            move = ai.find_best_move(g)
            searches.append({
                'moves': list(g.move_history),
                'depth': depth,
                'book': book,
                'exact': exact,
                'best': move,
                'score': ai.last_score,
                'depth_reached': ai.last_depth_reached,
                'nodes': ai.nodes_evaluated,
                'cutoffs': ai.cutoffs,
                'from_book': ai.last_move_from_book,
            })

    for _ in range(200):
        g = random_live_position(rng, rng.randint(0, 38))
        cur, mask = bits(g)
        evals.append({
            'moves': list(g.move_history),
            'eval': AIEngine.evaluate(cur, mask),
            'threats': str(winning_cells(cur, mask)),       # 64 bit: JSON'da metin olarak
            'opp_threats': str(winning_cells(cur ^ mask, mask)),
        })

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'searches': searches, 'evals': evals}, f, indent=1)
        f.write('\n')
    print(f"{len(searches)} arama, {len(evals)} degerlendirme -> {os.path.relpath(OUT, ROOT)}")


if __name__ == '__main__':
    main()
