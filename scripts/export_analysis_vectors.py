"""
Hamle analizi ("isabet") icin altin vektorler: tests/csharp/vectors/analysis_vectors.json

Referans src/gui_app.py -> best_columns(): derinlik-N aramasinin esit en iyi kok
hamleleri + (varsa) acilis kitabi hamlesi. Unity istemcisi
(unity/Assets/Scripts/AI/PlayPolicies.cs -> MoveAnalysis) ayni kumeyi vermek zorundadir.

Kullanim:
    python scripts/export_analysis_vectors.py
"""

import json
import os
import random
import sys

# gui_app pygame'i import eder: ekransiz ve sessiz
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
os.environ.setdefault('CONNECT4_MUTE', '1')

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'src'))

import gui_app  # noqa: E402
from game_core import ConnectFourGame  # noqa: E402

OUT = os.path.join(ROOT, 'tests', 'csharp', 'vectors', 'analysis_vectors.json')


def live_position(rng, n_moves):
    while True:
        g = ConnectFourGame()
        for _ in range(n_moves):
            if g.game_over:
                break
            g.make_move(rng.choice(g.get_valid_locations()))
        if not g.game_over and len(g.move_history) == n_moves:
            return g


def main():
    rng = random.Random(20261112)
    positions = []   # (oyun, derinlik)
    # Acilis kitabi pozisyonlarinin hepsi (bos tahta, 7 + 49 iki hamlelik) derinlik 4 ile
    positions.append((ConnectFourGame(), 4))
    for a in range(7):
        positions.append((ConnectFourGame.from_moves([a]), 4))
        for b in range(7):
            positions.append((ConnectFourGame.from_moves([a, b]), 4))
    # Python testlerindeki sabit pozisyonlar
    positions += [(ConnectFourGame.from_moves([2, 2, 3, 3, 4, 4]), 2),
                  (ConnectFourGame.from_moves([0, 6, 1, 6, 2]), 2),
                  (ConnectFourGame.from_moves([1]), gui_app.ANALYSIS_DEPTH)]
    for depth, count, lo, hi in [(2, 60, 3, 36), (3, 40, 3, 36), (4, 40, 3, 34),
                                 (gui_app.ANALYSIS_DEPTH, 12, 3, 30)]:
        for _ in range(count):
            positions.append((live_position(rng, rng.randint(lo, hi)), depth))

    cases = [{'moves': list(g.move_history), 'depth': d, 'best': gui_app.best_columns(g, depth=d)}
             for g, d in positions]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'analysis_depth': gui_app.ANALYSIS_DEPTH, 'cases': cases}, f)
        f.write('\n')
    multi = sum(len(c['best']) > 1 for c in cases)
    print(f"{len(cases)} vaka ({multi} birden fazla en iyi) -> {os.path.relpath(OUT, ROOT)}")


if __name__ == '__main__':
    main()
