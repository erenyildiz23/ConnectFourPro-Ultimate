"""
Kolay seviyesinin "hata" politikasi icin altin vektorler: tests/csharp/vectors/slip_vectors.json

Referans src/gui_app.py (fmix32, slip_move). Unity istemcisi
(unity/Assets/Scripts/AI/PlayPolicies.cs -> SlipPolicy) her vektorde ayni karari
(hata var mi, hangi sutun) vermek zorundadir.

Kullanim:
    python scripts/export_slip_vectors.py
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
from game_core import PLAYER1_PIECE, PLAYER2_PIECE, ConnectFourGame  # noqa: E402

OUT = os.path.join(ROOT, 'tests', 'csharp', 'vectors', 'slip_vectors.json')


def has_immediate_win(g):
    me = g.current_player
    for col in g.get_valid_locations():
        t = g.clone()
        t.make_move(col)
        if t.winner == me:
            return True
    return False


def random_position(rng, n_moves, start):
    g = ConnectFourGame(start)
    for _ in range(n_moves):
        if g.game_over:
            break
        g.make_move(rng.choice(g.get_valid_locations()))
    return g


def position_with(rng, predicate, start, lo, hi, tries=5000):
    for _ in range(tries):
        g = random_position(rng, rng.randint(lo, hi), start)
        if predicate(g):
            return g
    raise RuntimeError("pozisyon bulunamadi")


def full_column(g):
    return not g.game_over and len(g.get_valid_locations()) < 7


def case(g, start, depth, seed):
    col = gui_app.slip_move(g, depth, seed)
    return {
        'moves': list(g.move_history),
        'start': start,
        'depth': depth,
        'seed': seed,
        'slip': col is not None,
        'col': -1 if col is None else col,
        'immediate_win': (not g.game_over) and has_immediate_win(g),
    }


def main():
    rng = random.Random(20261111)
    cases = []

    def add(g, start, depth, seed):
        cases.append(case(g, start, depth, seed))

    seeds_edge = [0, 1, 2, 0xFFFFFFFF, 0x80000000, 0x9E3779B1]
    for start in (PLAYER1_PIECE, PLAYER2_PIECE):
        # Genel pozisyonlar, cogunlukla Kolay (derinlik 2)
        for _ in range(140):
            g = position_with(rng, lambda x: not x.game_over, start, 0, 38)
            add(g, start, 2, rng.getrandbits(32))
        # Diger seviyeler hic hata yapmaz
        for depth in (1, 3, 4, 8):
            for _ in range(5):
                g = position_with(rng, lambda x: not x.game_over, start, 0, 30)
                add(g, start, depth, rng.getrandbits(32))
        # Sirasi gelenin hemen kazanan hamlesi var: asla hata yok
        for _ in range(25):
            g = position_with(rng, lambda x: not x.game_over and has_immediate_win(x), start, 5, 38)
            add(g, start, 2, rng.getrandbits(32))
        # Dolu sutunlu pozisyonlar: hata sutunu gecerli sutunlar arasindan secilir
        for _ in range(30):
            g = position_with(rng, full_column, start, 12, 40)
            add(g, start, 2, rng.getrandbits(32))
        # Kenar tohumlar (32 bit tasma)
        for seed in seeds_edge:
            g = position_with(rng, lambda x: not x.game_over, start, 0, 20)
            add(g, start, 2, seed)
        # Bitmis oyun: hata yok
        for _ in range(3):
            g = position_with(rng, lambda x: x.game_over, start, 7, 42)
            add(g, start, 2, rng.getrandbits(32))
    # Python testlerindeki sabit pozisyonlar
    for seed in range(40):
        add(ConnectFourGame.from_moves([0]), PLAYER1_PIECE, 2, seed)
        add(ConnectFourGame.from_moves([0, 6, 1, 6, 2, 6, 5]), PLAYER1_PIECE, 2, seed)

    fmix = [{'in': x, 'out': gui_app.fmix32(x)}
            for x in [0, 1, 2, 3, 0xFFFFFFFF, 0x80000000, 0x9E3779B1, 0x9E3779B9, 12345]
            + [rng.getrandbits(32) for _ in range(20)]]

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, 'w', encoding='utf-8') as f:
        json.dump({'slip_permille': {str(k): v for k, v in gui_app.SLIP_PERMILLE.items()},
                   'fmix32': fmix, 'cases': cases}, f, indent=1)
        f.write('\n')
    slips = sum(c['slip'] for c in cases)
    print(f"{len(cases)} vaka ({slips} hata), {len(fmix)} fmix32 -> {os.path.relpath(OUT, ROOT)}")


if __name__ == '__main__':
    main()
