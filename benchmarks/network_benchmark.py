#!/usr/bin/env python3
# =============================================================================
# NETWORK BENCHMARK SUITE v3.0
# Connect Four Pro - Ag performans analizi
# =============================================================================
"""
Olculenler:
  1. Protokol karsilastirmasi (adil): WebSocket `latency_ping` yankisi ile REST
     `GET /health` - ikisi de veritabanina dokunmaz, sadece protokol maliyeti.
  2. Islem gecikmeleri: WebSocket create_game, REST leaderboard / active_games /
     login (PBKDF2 dahil).
  3. Yuk boyutu - gecikme iliskisi (WebSocket, 64 B - 16 KB).
  4. Eszamanlilik: N istemci ayni anda sabit sure boyunca REST ve WebSocket
     istekleri yapar; verim (istek/sn), gecikme, hata orani.
  5. Eszamanli oyunlar: K oda ayni anda tam oyun oynar (2K WebSocket baglantisi);
     hamle gidis-donus suresi ve tamamlanan oyun orani.

Socket.IO tasima katmani raporlanir; WebSocket degilse olcum gecersiz sayilir.

Kullanim:
    python network_benchmark.py --server http://localhost:5000
    python network_benchmark.py --quick
"""

import argparse
import random
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Dict, List

import requests
import socketio

import bench_common as bc
from game_core import ConnectFourGame

DEFAULT_SERVER = 'http://localhost:5000'


# =============================================================================
# YARDIMCILAR
# =============================================================================

class WSClient:
    """
    Istek/cevap seklinde olcum icin senkron Socket.IO sarmalayici.

    python-socketio istemcisi her mesaji ayri thread'de isler; olaylar sirasiz
    gelebilir. Bu yuzden cevap beklenirken olayin ICERIGI de kontrol edilir
    (orn. hamle gecmisi uzunlugu), sadece adi degil.
    """

    def __init__(self, url: str):
        self.sio = socketio.Client(reconnection=False)
        self._events: List[tuple] = []          # (ad, veri)
        self._cond = threading.Condition()
        for event in ('latency_pong', 'game_created', 'game_joined', 'game_start', 'move_made',
                      'game_over', 'error'):
            self.sio.on(event, self._make_handler(event))
        self.sio.connect(url, wait_timeout=10, transports=['websocket'])

    def _make_handler(self, event):
        def handler(data=None):
            with self._cond:
                self._events.append((event, data))
                self._cond.notify_all()
        return handler

    def _wait_match(self, event, predicate, start, timeout):
        deadline = time.perf_counter() + timeout
        with self._cond:
            while True:
                for name, data in self._events[start:]:
                    if name == event and (predicate is None or predicate(data)):
                        return data, True
                remaining = deadline - time.perf_counter()
                if remaining <= 0:
                    return None, False
                self._cond.wait(remaining)

    def request(self, emit_event: str, data, reply_event: str, timeout: float = 5.0, predicate=None):
        """Gonderir, eslesen cevabi bekler: (gecikme_ms, veri) - zaman asiminda (None, None)."""
        with self._cond:
            start = len(self._events)
        t0 = time.perf_counter()
        self.sio.emit(emit_event, data)
        reply, ok = self._wait_match(reply_event, predicate, start, timeout)
        if not ok:
            return None, None
        ms = (time.perf_counter() - t0) * 1000
        with self._cond:
            if len(self._events) > 1000:     # uzun olcumlerde bellegi sinirla
                del self._events[:-100]
        return ms, reply

    def wait(self, event: str, timeout: float = 5.0):
        """Baglanti boyunca gelmis (veya gelecek) ilk `event` olayini dondurur."""
        return self._wait_match(event, None, 0, timeout)[0]

    def wait_for_history(self, n: int, timeout: float = 5.0) -> bool:
        """Oyun gecmisi en az n hamle olan bir move_made gorulene kadar bekler (n=0 aninda)."""
        if n == 0:
            return True
        return self._wait_match('move_made', lambda d: len(d['history']) >= n, 0, timeout)[1]

    @property
    def transport(self) -> str:
        return self.sio.transport()

    def close(self):
        try:
            self.sio.disconnect()
        except Exception:
            pass


def timed_series(fn: Callable[[], float], n: int, warmup: int, pause: float = 0.0) -> Dict:
    """fn() -> gecikme_ms (hata icin None). n olcum, warmup isinma."""
    for _ in range(warmup):
        fn()
    values, failures = [], 0
    t0 = time.perf_counter()
    for _ in range(n):
        ms = fn()
        if ms is None:
            failures += 1
        else:
            values.append(ms)
        if pause:
            time.sleep(pause)
    stats = bc.summarize(values)
    stats.update(failures=failures, jitter=bc.jitter(values),
                 sequential_rps=len(values) / (time.perf_counter() - t0))
    return stats


# =============================================================================
# TESTLER
# =============================================================================

class NetworkBenchmark:
    def __init__(self, server: str, n: int, warmup: int, duration: float, seed: int):
        self.server = server.rstrip('/')
        self.n, self.warmup, self.duration, self.seed = n, warmup, duration, seed
        self.http = requests.Session()

    # ------------------------------------------------------------------
    def protocol_comparison(self) -> Dict:
        bc.progress("\n[1/5] Protokol karsilastirmasi (veritabanisiz uc noktalar)")
        ws = WSClient(self.server)
        transport = ws.transport
        bc.progress(f"  Socket.IO tasima katmani: {transport}")
        payload = {'pad': 'x' * 64}
        ws_stats = timed_series(lambda: ws.request('latency_ping', payload, 'latency_pong')[0],
                                self.n, self.warmup, pause=0.005)

        def rest_health():
            t0 = time.perf_counter()
            r = self.http.get(f'{self.server}/health', timeout=5)
            return (time.perf_counter() - t0) * 1000 if r.ok else None
        rest_stats = timed_series(rest_health, self.n, self.warmup, pause=0.005)
        ws.close()
        for name, s in (('WebSocket ping', ws_stats), ('REST /health', rest_stats)):
            bc.progress(f"  {name:<15} ort {s['mean']:.3f} ms | medyan {s['median']:.3f} | "
                        f"p95 {s['p95']:.3f} | p99 {s['p99']:.3f}")
        return {'transport': transport, 'websocket_ping': ws_stats, 'rest_health': rest_stats}

    # ------------------------------------------------------------------
    def operations(self) -> Dict:
        bc.progress("\n[2/5] Islem gecikmeleri")
        results = {}
        ws = WSClient(self.server)
        user = f'bench_ws_{uuid.uuid4().hex[:6]}'
        results['ws_create_game'] = timed_series(
            lambda: ws.request('create_game', {'user_id': user}, 'game_created')[0], self.n // 2, 5)
        ws.close()

        def rest(method, path, **kw):
            def call():
                t0 = time.perf_counter()
                r = self.http.request(method, f'{self.server}{path}', timeout=10, **kw)
                return (time.perf_counter() - t0) * 1000 if r.status_code < 500 else None
            return call

        name = f'bench_{uuid.uuid4().hex[:8]}'
        self.http.post(f'{self.server}/signup', json={'username': name, 'password': 'benchpw'})
        results['rest_leaderboard'] = timed_series(rest('GET', '/leaderboard'), self.n, self.warmup)
        results['rest_active_games'] = timed_series(rest('GET', '/active_games'), self.n, self.warmup)
        results['rest_login'] = timed_series(
            rest('POST', '/login', json={'username': name, 'password': 'benchpw'}), self.n // 2, 3)
        results['rest_signup_validation'] = timed_series(
            rest('POST', '/signup', json={'username': 'x', 'password': 'y'}), self.n // 2, 3)
        for k, s in results.items():
            bc.progress(f"  {k:<24} ort {s['mean']:8.3f} ms | p95 {s['p95']:8.3f} ms | hata {s['failures']}")
        return results

    # ------------------------------------------------------------------
    def payload_sweep(self, sizes: List[int]) -> List[Dict]:
        bc.progress("\n[3/5] Yuk boyutu - gecikme (WebSocket)")
        ws = WSClient(self.server)
        out = []
        for size in sizes:
            payload = {'pad': 'x' * size}
            s = timed_series(lambda p=payload: ws.request('latency_ping', p, 'latency_pong')[0],
                             self.n // 2, 10, pause=0.003)
            s['payload_bytes'] = size
            out.append(s)
            bc.progress(f"  {size:>6} B: ort {s['mean']:.3f} ms | p95 {s['p95']:.3f} ms")
        ws.close()
        return out

    # ------------------------------------------------------------------
    def _load(self, workers: int, make_call: Callable[[], Callable[[], bool]]) -> Dict:
        """`workers` istemci `duration` saniye boyunca durmaksizin istek yapar."""
        latencies, errors = [], [0]
        lock = threading.Lock()
        ready = threading.Barrier(workers + 1)
        go = threading.Event()
        stop_at = [0.0]

        def worker():
            try:
                call = make_call()      # Baglanti kurulumu olcume dahil degil
            except Exception:
                with lock:
                    errors[0] += 1
                ready.wait()
                return
            ready.wait()
            go.wait()                   # stop_at ayarlandiktan sonra baslar
            local, local_err = [], 0
            while time.perf_counter() < stop_at[0]:
                t0 = time.perf_counter()
                try:
                    ok = call()
                except Exception:
                    ok = False
                if ok:
                    local.append((time.perf_counter() - t0) * 1000)
                else:
                    local_err += 1
            with lock:
                latencies.extend(local)
                errors[0] += local_err

        with ThreadPoolExecutor(max_workers=workers) as pool:
            for _ in range(workers):
                pool.submit(worker)
            ready.wait()
            t0 = time.perf_counter()
            stop_at[0] = t0 + self.duration
            go.set()
        elapsed = time.perf_counter() - t0
        total = len(latencies) + errors[0]
        stats = bc.summarize(latencies)
        stats.update(clients=workers, requests=total, errors=errors[0],
                     error_rate_percent=100 * errors[0] / max(total, 1),
                     throughput_rps=len(latencies) / elapsed)
        return stats

    def _concurrency_level(self, n: int):
        def make_rest():
            session = requests.Session()
            return lambda: session.get(f'{self.server}/leaderboard', timeout=10).ok
        r = self._load(n, make_rest)

        clients = []

        def make_ws():
            c = WSClient(self.server)
            clients.append(c)  # list.append thread-safe
            return lambda: c.request('latency_ping', {'t': 1}, 'latency_pong', timeout=10)[0] is not None
        w = self._load(n, make_ws)
        for c in clients:
            c.close()
        return r, w

    def concurrency(self, levels: List[int]) -> Dict[str, List[Dict]]:
        bc.progress(f"\n[4/5] Eszamanlilik ({self.duration:.0f} sn / seviye)")
        out = {'rest_leaderboard': [], 'websocket_ping': []}
        for n in levels:
            r, w = self._concurrency_level(n)
            out['rest_leaderboard'].append(r)
            out['websocket_ping'].append(w)
            bc.progress(f"  {n:>4} istemci | REST {r['throughput_rps']:7.1f} rps, ort {r.get('mean', 0):7.2f} ms, "
                        f"hata %{r['error_rate_percent']:.1f} | WS {w['throughput_rps']:7.1f} rps, "
                        f"ort {w.get('mean', 0):7.2f} ms, hata %{w['error_rate_percent']:.1f}")
        return out

    # ------------------------------------------------------------------
    def _games_level(self, k: int) -> Dict:
        rng = random.Random(self.seed + k)
        scripts = []
        for _ in range(k):
            g = ConnectFourGame()
            while not g.game_over:
                g.make_move(rng.choice(g.get_valid_locations()))
            scripts.append(g.move_history)

        rtts, completed, errors = [], [0], [0]
        play_windows = []           # (oyun baslangici, bitisi): verim sadece oyun suresinden
        lock = threading.Lock()
        all_ready = threading.Barrier(k)

        def play(idx):
            tag = uuid.uuid4().hex[:6]
            a = b = None
            try:
                a, b = WSClient(self.server), WSClient(self.server)
                _, created = a.request('create_game', {'user_id': f'bench_a_{tag}'}, 'game_created', 10)
                room = created['room_id']
                b.request('join_game', {'room_id': room, 'user_id': f'bench_b_{tag}'}, 'game_start', 10)
                a.wait('game_start', 10)
            except Exception:
                with lock:
                    errors[0] += 1
                all_ready.abort()
                for c in (a, b):
                    if c:
                        c.close()
                return
            try:
                all_ready.wait(30)      # Tum odalar hazir: oyunlar ayni anda baslar
                start = time.perf_counter()
                local = []
                for i, col in enumerate(scripts[idx]):
                    client, piece = (a, 1) if i % 2 == 0 else (b, 2)
                    # Rakibin hamlesi istemciye ulasmadan sira gelmez: gercek oyuncu davranisi
                    client.wait_for_history(i, 10)
                    ms, _ = client.request(
                        'make_move', {'room_id': room, 'col': col, 'player_piece': piece}, 'move_made', 10,
                        predicate=lambda d, n=i + 1: len(d['history']) == n)
                    if ms is None:
                        raise RuntimeError('hamle zaman asimi')
                    local.append(ms)
                if a.wait('game_over', 10) is None:
                    raise RuntimeError('game_over gelmedi')
                with lock:
                    rtts.extend(local)
                    completed[0] += 1
                    play_windows.append((start, time.perf_counter()))
            except Exception:
                with lock:
                    errors[0] += 1
            finally:
                a.close()
                b.close()

        threads = [threading.Thread(target=play, args=(i,)) for i in range(k)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        play_seconds = (max(e for _, e in play_windows) - min(s for s, _ in play_windows)) if play_windows else 0
        stats = bc.summarize(rtts)
        stats.update(games=k, connections=2 * k, completed=completed[0], errors=errors[0],
                     completion_percent=100 * completed[0] / k, moves=len(rtts),
                     moves_per_second=len(rtts) / play_seconds if play_seconds else 0,
                     play_seconds=play_seconds)
        bc.progress(f"  {k:>3} oyun ({2 * k:>3} baglanti): tamamlanan {completed[0]}/{k} | hamle RTT ort "
                    f"{stats.get('mean', 0):.2f} ms, p95 {stats.get('p95', 0):.2f} ms | "
                    f"{stats['moves_per_second']:.0f} hamle/sn")
        return stats

    def concurrent_games(self, levels: List[int]) -> List[Dict]:
        bc.progress("\n[5/5] Eszamanli oyunlar (her oda 2 WebSocket istemcisi, rastgele yasal hamleler)")
        return [self._games_level(k) for k in levels]

def main():
    parser = argparse.ArgumentParser(description='Network Benchmark Suite v3.0')
    parser.add_argument('--server', default=DEFAULT_SERVER)
    parser.add_argument('--requests', type=int, default=500, help='Seri olcumlerde istek sayisi')
    parser.add_argument('--duration', type=float, default=10.0, help='Eszamanlilik seviyesi basina sure (sn)')
    parser.add_argument('--seed', type=int, default=2024)
    parser.add_argument('--quick', action='store_true')
    args = parser.parse_args()

    levels, game_levels, sizes = [1, 5, 10, 20, 50, 100], [1, 10, 25, 50], [64, 256, 1024, 4096, 16384]
    if args.quick:
        args.requests, args.duration = 60, 2.0
        levels, game_levels, sizes = [1, 10], [1, 5], [64, 1024]

    health = requests.get(f'{args.server}/health', timeout=5).json()
    env = bc.environment_info()
    bc.progress(f"NETWORK BENCHMARK v3.0 | {args.server} | veritabani: {health.get('database')} | {env['cpu']}")

    bench = NetworkBenchmark(args.server, args.requests, warmup=20, duration=args.duration, seed=args.seed)
    t0 = time.time()
    protocol = bench.protocol_comparison()
    if protocol['transport'] != 'websocket':
        raise SystemExit("HATA: Socket.IO WebSocket kullanmiyor (websocket-client kurulu mu?). Olcum gecersiz.")
    report = {
        'suite': 'network', 'version': '3.0', 'environment': env,
        'parameters': {'server': args.server, 'requests': args.requests, 'duration_per_level_s': args.duration,
                       'concurrency_levels': levels, 'game_levels': game_levels, 'payload_sizes': sizes,
                       'quick': args.quick, 'server_health': health},
        'protocol': protocol,
        'operations': bench.operations(),
        'payload': bench.payload_sweep(sizes),
        'concurrency': bench.concurrency(levels),
        'concurrent_games': bench.concurrent_games(game_levels),
    }
    report['duration_seconds'] = time.time() - t0
    path = bc.save_json('network_results.json', bc.rounded(report))
    bc.progress(f"\nSure: {report['duration_seconds']:.0f} sn | Sonuc: {path}")


if __name__ == '__main__':
    main()
