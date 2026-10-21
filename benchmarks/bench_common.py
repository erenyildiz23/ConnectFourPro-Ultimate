"""Benchmark betikleri icin ortak yardimcilar: ortam bilgisi, istatistik, dosya yazma."""

import json
import os
import platform
import statistics
import subprocess
import sys
from datetime import datetime
from typing import Dict, List, Sequence

BENCH_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(BENCH_DIR)
SRC_DIR = os.path.join(ROOT_DIR, 'src')
RESULTS_DIR = os.path.join(BENCH_DIR, 'results')
FIGURES_DIR = os.path.join(BENCH_DIR, 'visualization_outputs')

if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def _cpu_model() -> str:
    try:
        with open('/proc/cpuinfo') as f:
            for line in f:
                if line.startswith('model name'):
                    return line.split(':', 1)[1].strip()
    except OSError:
        pass
    return platform.processor() or platform.machine()


def _git_commit() -> str:
    try:
        return subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD'], cwd=ROOT_DIR,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return 'unknown'


def environment_info() -> Dict[str, str]:
    """Olcumun yapildigi ortam (sonuclarin yorumlanmasi icin her dosyaya yazilir)."""
    return {
        'timestamp': datetime.now().isoformat(timespec='seconds'),
        'cpu': _cpu_model(),
        'logical_cpus': str(os.cpu_count()),
        'platform': platform.platform(),
        'python': platform.python_version(),
        'implementation': platform.python_implementation(),
        'git_commit': _git_commit(),
    }


def summarize(values: Sequence[float]) -> Dict[str, float]:
    """Ortalama, standart sapma, medyan ve yuzdelikler (n < 2 icin guvenli)."""
    values = list(values)
    if not values:
        return {'n': 0}
    result = {
        'n': len(values),
        'mean': statistics.fmean(values),
        'stdev': statistics.stdev(values) if len(values) > 1 else 0.0,
        'min': min(values),
        'median': statistics.median(values),
        'max': max(values),
    }
    if len(values) >= 2:
        q = statistics.quantiles(values, n=100, method='inclusive')
        result.update(p95=q[94], p99=q[98])
    else:
        result.update(p95=values[0], p99=values[0])
    return result


def jitter(values: Sequence[float]) -> float:
    """Ardisik olcumler arasindaki farklarin ortalama mutlak degeri (RFC 3550 tarzi)."""
    values = list(values)
    if len(values) < 2:
        return 0.0
    return statistics.fmean(abs(b - a) for a, b in zip(values, values[1:], strict=False))


def save_json(name: str, data: dict, directory: str = RESULTS_DIR) -> str:
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def load_json(name: str, directory: str = RESULTS_DIR):
    path = os.path.join(directory, name)
    if not os.path.exists(path):
        return None
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def rounded(d, digits: int = 3):
    """Ic ice sozluk/listelerdeki float'lari yuvarlar (okunabilir JSON)."""
    if isinstance(d, float):
        return round(d, digits)
    if isinstance(d, dict):
        return {k: rounded(v, digits) for k, v in d.items()}
    if isinstance(d, list):
        return [rounded(v, digits) for v in d]
    return d


def progress(msg: str) -> None:
    print(msg, flush=True)


__all__: List[str] = ['BENCH_DIR', 'ROOT_DIR', 'RESULTS_DIR', 'FIGURES_DIR', 'environment_info', 'summarize',
                      'jitter', 'save_json', 'load_json', 'rounded', 'progress']
