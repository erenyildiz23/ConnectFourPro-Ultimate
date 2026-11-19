"""Arena gece hile kontrolu.

Kontrol edilmemis turnuvalarin oyunlarini sunucudan alir, her oyuncunun kritik hamlelerini
kusursuz cozucuyle (c4solver -a) degerlendirir; esik asilirsa GitHub issue acar ve turnuvayi
"kontrol edildi" diye isaretler. Bu bir otomatik sinyaldir, kanit degildir.

Kullanim:
    python scripts/arena_cheat_check.py --server https://... --solver-dir <c4solver ve 7x6.book dizini> [--dry-run]
Ortam: ARENA_CHECK_SECRET (isaretleme uc noktasi icin), GH_TOKEN (gh icin).
Yalnizca standart kutuphane kullanir.
"""

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from typing import Dict, List, Optional, Tuple

BOOK_PLIES = 4      # ilk yarim hamleler (acilis) sayilmaz
MIN_GAMES = 3
MIN_CRITICAL = 20
HTTP_TIMEOUT = 30
GH_TIMEOUT = 60


class Oracle:
    """Kusursuz cozucu (c4solver -a); benchmarks/ai_quality_benchmark.py'deki Oracle ile ayni protokol."""

    def __init__(self, solver_dir: str):
        exe = os.path.join(solver_dir, 'c4solver')
        if not os.path.exists(exe):
            raise SystemExit(f"Cozucu bulunamadi: {exe}")
        # 7x6.book cozucunun calisma dizininde olmali
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

    def close(self):
        try:
            self.proc.stdin.close()
            self.proc.wait(timeout=5)
        except Exception:
            self.proc.kill()


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def critical_moves(oracle, moves: List[int]) -> List[Tuple[int, bool]]:
    """(ply_index, dogru_mu) listesi; yalnizca ply >= BOOK_PLIES ve kritik pozisyonlar."""
    out = []
    for i in range(BOOK_PLIES, len(moves)):
        scores = oracle.scores(moves[:i])
        signs = {_sign(s) for s in scores if s is not None}
        if len(signs) <= 1:
            continue    # zorunlu pozisyon
        chosen = scores[moves[i]]
        out.append((i, chosen is not None and _sign(chosen) == max(signs)))
    return out


def evaluate_player(oracle, games: List[Dict], username: str) -> Dict:
    played = critical = correct = 0
    for g in games:
        if g['player1'] == username:
            parity = 0
        elif g['player2'] == username:
            parity = 1
        else:
            continue
        played += 1
        for ply, ok in critical_moves(oracle, g['moves']):
            if ply % 2 == parity:
                critical += 1
                correct += ok
    return {'games': played, 'critical': critical, 'correct': correct,
            'flagged': played >= MIN_GAMES and critical >= MIN_CRITICAL and correct == critical}


# ---- Ag ve gh yardimcilari (testlerde taklit edilir) ----

def http_get_json(url: str):
    with urllib.request.urlopen(url, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode('utf-8'))


def http_post_checked(url: str, secret: str) -> None:
    req = urllib.request.Request(url, data=b'{}', method='POST',
                                 headers={'X-Arena-Check-Secret': secret, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        if resp.status != 200:
            raise RuntimeError(f"isaretleme basarisiz: HTTP {resp.status}")


def run_gh(args: List[str]) -> str:
    res = subprocess.run(['gh'] + args, capture_output=True, text=True, timeout=GH_TIMEOUT)
    if res.returncode != 0:
        raise RuntimeError(f"gh {' '.join(args[:2])} basarisiz: {res.stderr.strip()}")
    return res.stdout


def issue_title(tid: int, username: str) -> str:
    return f"Arena #{tid}: {username} kritik hamlelerin %100'\u00fc"


def issue_body(tid: int, username: str, r: Dict) -> str:
    return (f"Turnuva: #{tid}\nOyuncu: {username}\n\n"
            f"- Oyun sayısı: {r['games']}\n- Kritik hamle: {r['critical']}\n- Doğru kritik hamle: {r['correct']}\n\n"
            "Bu otomatik bir sinyaldir, kanıt değildir. Sahibi tarafından gözden geçirilmelidir.")


def _issue_exists(title: str) -> bool:
    out = run_gh(['issue', 'list', '--state', 'all', '--search', f'{title} in:title',
                  '--json', 'title', '--limit', '100'])
    return any(i.get('title') == title for i in json.loads(out or '[]'))


def _process_tournament(server, tid, oracle, secret, dry_run) -> None:
    games = http_get_json(f"{server}/tournaments/{tid}/games")['games']
    players = sorted({p for g in games for p in (g['player1'], g['player2'])})
    for user in players:
        r = evaluate_player(oracle, games, user)
        print(f"Turnuva {tid} / {user}: {r}")
        if not r['flagged']:
            continue
        title = issue_title(tid, user)
        if dry_run:
            print(f"[dry-run] issue acilacak: {title}")
        elif _issue_exists(title):
            print(f"Issue zaten var, atlandi: {title}")
        else:
            run_gh(['issue', 'create', '--title', title, '--body', issue_body(tid, user, r)])
            print(f"Issue acildi: {title}")
    if dry_run:
        print(f"[dry-run] turnuva {tid} isaretlenmeyecek")
    else:
        http_post_checked(f"{server}/tournaments/{tid}/checked", secret)
        print(f"Turnuva {tid} kontrol edildi olarak isaretlendi")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--server', required=True)
    ap.add_argument('--solver-dir', required=True)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(errors='replace')    # diakritikli baslik konsolu cokertmesin
    server = args.server.rstrip('/')
    secret = os.environ.get('ARENA_CHECK_SECRET', '')
    if not secret and not args.dry_run:
        print("ARENA_CHECK_SECRET tanimli degil", file=sys.stderr)
        return 2
    try:
        ids = http_get_json(f"{server}/tournaments/unchecked")['tournament_ids']
    except Exception as e:
        print(f"Turnuva listesi alinamadi: {e}", file=sys.stderr)
        return 1
    if not ids:
        print("Kontrol edilecek turnuva yok")
        return 0
    oracle = Oracle(args.solver_dir)
    failed = False
    try:
        for tid in ids:
            try:
                _process_tournament(server, tid, oracle, secret, args.dry_run)
            except Exception as e:    # turnuva isaretlenmez, sonraki gece tekrar denenir
                failed = True
                print(f"Turnuva {tid} islenemedi, isaretlenmedi: {e}", file=sys.stderr)
    finally:
        oracle.close()
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
