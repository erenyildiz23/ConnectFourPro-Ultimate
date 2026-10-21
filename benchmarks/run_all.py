#!/usr/bin/env python3
"""
Tum benchmark'lari sirayla calistirir ve grafikleri + raporu uretir.

    # Sunucuyu bu betik baslatir (ayri bir veritabani kullanin!)
    DATABASE_URL=postgresql://postgres:SIFRE@localhost/connect4_bench python run_all.py

    # Zaten calisan bir sunucuya karsi
    python run_all.py --server http://localhost:5000

    python run_all.py --quick          # hizli kontrol
    python run_all.py --skip-ai        # sadece ag + yuk testleri

Ciktilar: results/*.json, results/locust_*.csv|html, visualization_outputs/*.png, RESULTS.md
"""

import argparse
import csv
import os
import subprocess
import sys
import time

import requests

import bench_common as bc

PY = sys.executable


def run(cmd, **kw):
    bc.progress(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, cwd=bc.BENCH_DIR, **kw)


def wait_for_server(url, timeout=30):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if requests.get(f"{url}/health", timeout=1).ok:
                return True
        except requests.RequestException:
            time.sleep(0.5)
    return False


def parse_locust(prefix: str, users: int, spawn_rate: int, run_time: str) -> dict:
    """Locust *_stats.csv dosyasindan toplam ve uc nokta bazli ozet."""
    with open(f"{prefix}_stats.csv", newline='') as f:
        rows = list(csv.DictReader(f))

    def row_summary(r):
        return {
            'requests': int(r['Request Count']), 'failures': int(r['Failure Count']),
            'rps': float(r['Requests/s']), 'mean_ms': float(r['Average Response Time']),
            'median_ms': float(r['Median Response Time']), 'p95_ms': float(r['95%']),
            'p99_ms': float(r['99%']), 'max_ms': float(r['Max Response Time']),
        }
    total = next(r for r in rows if r['Name'] == 'Aggregated')
    summary = row_summary(total)
    summary.update(users=users, spawn_rate=spawn_rate, run_time=run_time,
                   error_rate_percent=100 * summary['failures'] / max(summary['requests'], 1),
                   endpoints={r['Name']: row_summary(r) for r in rows if r['Name'] != 'Aggregated'})
    return summary


def main():
    parser = argparse.ArgumentParser(description='Tum benchmarklari calistir')
    parser.add_argument('--server', help='Calisan sunucu adresi (verilmezse sunucu baslatilir)')
    parser.add_argument('--port', type=int, default=5055)
    parser.add_argument('--quick', action='store_true')
    parser.add_argument('--skip-ai', action='store_true')
    parser.add_argument('--skip-network', action='store_true')
    parser.add_argument('--skip-locust', action='store_true')
    parser.add_argument('--locust-users', default='50,100,200')
    parser.add_argument('--locust-time', default='2m')
    parser.add_argument('--solver-dir', help='Kusursuz cozucu klasoru (verilirse AI kalite benchmarki da calisir)')
    args = parser.parse_args()
    os.makedirs(bc.RESULTS_DIR, exist_ok=True)
    quick = ['--quick'] if args.quick else []

    if not args.skip_ai:
        run([PY, 'ai_performance_suite.py', *quick])
        run([PY, 'gui_fps_benchmark.py'])
        if args.solver_dir:
            run([PY, 'ai_quality_benchmark.py', '--solver-dir', args.solver_dir, *quick])

    server_proc = None
    url = args.server
    if not (args.skip_network and args.skip_locust):
        if not url:
            if 'DATABASE_URL' not in os.environ:
                sys.exit("DATABASE_URL ayarlayin (ayri bir benchmark veritabani) veya --server verin.")
            url = f"http://127.0.0.1:{args.port}"
            env = dict(os.environ, CONNECT4_PORT=str(args.port), CONNECT4_HOST='127.0.0.1', LOG_LEVEL='WARNING')
            log_file = open(os.path.join(bc.RESULTS_DIR, 'server.log'), 'w')
            server_proc = subprocess.Popen([PY, 'server.py'], cwd=bc.SRC_DIR, env=env,
                                           stdout=log_file, stderr=subprocess.STDOUT)
            if not wait_for_server(url):
                server_proc.terminate()
                sys.exit("Sunucu baslamadi; results/server.log dosyasina bakin.")
        try:
            if not args.skip_network:
                run([PY, 'network_benchmark.py', '--server', url, *quick])
            if not args.skip_locust:
                levels = [int(u) for u in args.locust_users.split(',')]
                run_time = '20s' if args.quick else args.locust_time
                if args.quick:
                    levels = levels[:1]
                locust_results = []
                for users in levels:
                    spawn = max(users // 10, 1)
                    prefix = os.path.join(bc.RESULTS_DIR, f'locust_{users}')
                    run([PY, '-m', 'locust', '-f', 'locustfile.py', '--host', url, '-u', str(users),
                         '-r', str(spawn), '-t', run_time, '--headless', '--only-summary',
                         '--csv', prefix, '--html', f'{prefix}.html'])
                    locust_results.append(parse_locust(prefix, users, spawn, run_time))
                    for suffix in ('_stats_history.csv', '_failures.csv', '_exceptions.csv'):
                        path = prefix + suffix
                        if os.path.exists(path):
                            os.remove(path)
                bc.save_json('locust_results.json', bc.rounded({
                    'suite': 'locust', 'environment': bc.environment_info(),
                    'parameters': {'server': url, 'levels': levels, 'run_time': run_time},
                    'tests': locust_results}))
        finally:
            if server_proc:
                server_proc.terminate()
                server_proc.wait(timeout=10)
            if 'DATABASE_URL' in os.environ:
                sys.path.insert(0, bc.SRC_DIR)
                import database
                bc.progress(f"Test hesaplari temizlendi: {database.delete_test_users()}")

    run([PY, 'visualize_all_results.py'])


if __name__ == '__main__':
    main()
