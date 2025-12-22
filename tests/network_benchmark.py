#!/usr/bin/env python3
# =============================================================================
# NETWORK BENCHMARK SUITE v2.0
# Connect Four Bitirme Projesi - Ağ Performans Analizi
# =============================================================================
# 
# Bu test suite aşağıdaki metrikleri ölçer:
# 1. WebSocket Round-Trip Time (RTT)
# 2. REST API Response Time
# 3. Payload Size vs Latency ilişkisi
# 4. Concurrent Connection performansı
# 5. Jitter (gecikme varyansı) analizi
#
# Kullanım: python network_benchmark_v2.py [--server URL] [--output DIR]
# =============================================================================

import socketio
import requests
import time
import statistics
import sys
import os
import json
import csv
import threading
import argparse
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

# =============================================================================
# CONFIGURATION
# =============================================================================

DEFAULT_SERVER = 'http://localhost:5000'
DEFAULT_OUTPUT_DIR = './network_test_results'

# Test Parameters
WARMUP_REQUESTS = 10          # Isınma turları (sonuçlara dahil edilmez)
REQUESTS_PER_TEST = 100       # Her test için istek sayısı
PAYLOAD_SIZES = [64, 256, 1024, 4096]  # Bytes
CONCURRENT_LEVELS = [1, 5, 10, 20, 50]  # Eşzamanlı bağlantı sayıları

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LatencyMeasurement:
    """Tek bir latency ölçümü."""
    test_type: str          # 'websocket', 'rest_get', 'rest_post'
    timestamp: float
    latency_ms: float
    payload_size: int
    success: bool
    error_message: Optional[str] = None

@dataclass
class TestResult:
    """Bir test serisinin özet istatistikleri."""
    test_name: str
    test_type: str
    sample_count: int
    success_count: int
    failure_count: int
    min_ms: float
    max_ms: float
    mean_ms: float
    median_ms: float
    stdev_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    jitter_ms: float         # Standart sapma olarak jitter
    throughput_rps: float    # Requests per second

@dataclass 
class ConcurrencyResult:
    """Concurrent connection test sonucu."""
    concurrent_connections: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time_seconds: float
    avg_latency_ms: float
    throughput_rps: float
    error_rate_percent: float

# =============================================================================
# WEBSOCKET BENCHMARK
# =============================================================================

class WebSocketBenchmark:
    """WebSocket RTT ölçüm sınıfı."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.measurements: List[LatencyMeasurement] = []
        self.pending_requests: Dict[str, float] = {}
        self.sio = None
        self.connected = False
        self.test_complete = threading.Event()
        self.current_test_count = 0
        self.target_count = 0
        
    def connect(self) -> bool:
        """Sunucuya bağlan."""
        try:
            self.sio = socketio.Client()
            
            @self.sio.on('connect')
            def on_connect():
                self.connected = True
                print(f"    [WebSocket] Bağlantı kuruldu: {self.server_url}")
            
            @self.sio.on('disconnect')
            def on_disconnect():
                self.connected = False
            
            @self.sio.on('game_created')
            def on_game_created(data):
                self._handle_response('create_game', data)
            
            @self.sio.on('active_games')
            def on_active_games(data):
                self._handle_response('get_games', data)
            
            @self.sio.on('error')
            def on_error(data):
                self._handle_response('error', data, success=False)
            
            self.sio.connect(self.server_url, wait_timeout=10)
            time.sleep(0.5)  # Bağlantı stabilizasyonu
            return self.connected
            
        except Exception as e:
            print(f"    [WebSocket] Bağlantı hatası: {e}")
            return False
    
    def disconnect(self):
        """Bağlantıyı kapat."""
        if self.sio and self.connected:
            self.sio.disconnect()
    
    def _handle_response(self, event_type: str, data, success: bool = True):
        """Sunucu yanıtını işle."""
        end_time = time.perf_counter()
        
        # En eski bekleyen isteği bul
        if self.pending_requests:
            request_id = list(self.pending_requests.keys())[0]
            start_time = self.pending_requests.pop(request_id)
            latency_ms = (end_time - start_time) * 1000
            
            self.measurements.append(LatencyMeasurement(
                test_type='websocket',
                timestamp=end_time,
                latency_ms=latency_ms,
                payload_size=len(str(data)) if data else 0,
                success=success,
                error_message=None if success else str(data)
            ))
            
            self.current_test_count += 1
            if self.current_test_count >= self.target_count:
                self.test_complete.set()
    
    def run_latency_test(self, num_requests: int = 100, 
                         warmup: int = 10,
                         payload_size: int = 64) -> List[LatencyMeasurement]:
        """Latency testi çalıştır."""
        self.measurements = []
        self.current_test_count = 0
        self.target_count = num_requests
        self.test_complete.clear()
        
        # Warmup
        print(f"    [WebSocket] Warmup: {warmup} istek...")
        for i in range(warmup):
            request_id = f"warmup_{i}"
            self.pending_requests[request_id] = time.perf_counter()
            self.sio.emit('create_game', {'user_id': 9999, 'padding': 'x' * payload_size})
            time.sleep(0.05)
        
        time.sleep(1)  # Warmup yanıtlarını bekle
        self.measurements = []  # Warmup verilerini temizle
        self.pending_requests = {}
        self.current_test_count = 0
        
        # Gerçek test
        print(f"    [WebSocket] Test: {num_requests} istek (payload: {payload_size} bytes)...")
        for i in range(num_requests):
            request_id = f"test_{i}"
            self.pending_requests[request_id] = time.perf_counter()
            self.sio.emit('create_game', {'user_id': 9999, 'padding': 'x' * payload_size})
            time.sleep(0.02)  # Rate limiting
            
            sys.stdout.write(f"\r    Progress: {i+1}/{num_requests}")
            sys.stdout.flush()
        
        # Yanıtları bekle
        self.test_complete.wait(timeout=30)
        print()
        
        return self.measurements


# =============================================================================
# REST API BENCHMARK
# =============================================================================

class RESTBenchmark:
    """REST API performans ölçüm sınıfı."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = requests.Session()
        self.measurements: List[LatencyMeasurement] = []
    
    def run_get_test(self, endpoint: str, num_requests: int = 100,
                     warmup: int = 10) -> List[LatencyMeasurement]:
        """GET endpoint testi."""
        url = f"{self.server_url}{endpoint}"
        self.measurements = []
        
        # Warmup
        print(f"    [REST GET] Warmup: {warmup} istek...")
        for _ in range(warmup):
            try:
                self.session.get(url, timeout=5)
            except:
                pass
            time.sleep(0.02)
        
        # Test
        print(f"    [REST GET] Test: {num_requests} istek -> {endpoint}")
        for i in range(num_requests):
            start_time = time.perf_counter()
            try:
                response = self.session.get(url, timeout=5)
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                self.measurements.append(LatencyMeasurement(
                    test_type='rest_get',
                    timestamp=end_time,
                    latency_ms=latency_ms,
                    payload_size=len(response.content),
                    success=response.status_code == 200,
                    error_message=None if response.status_code == 200 else f"HTTP {response.status_code}"
                ))
            except Exception as e:
                end_time = time.perf_counter()
                self.measurements.append(LatencyMeasurement(
                    test_type='rest_get',
                    timestamp=end_time,
                    latency_ms=(end_time - start_time) * 1000,
                    payload_size=0,
                    success=False,
                    error_message=str(e)
                ))
            
            sys.stdout.write(f"\r    Progress: {i+1}/{num_requests}")
            sys.stdout.flush()
            time.sleep(0.01)
        
        print()
        return self.measurements
    
    def run_post_test(self, endpoint: str, payload_size: int = 256,
                      num_requests: int = 100, warmup: int = 10) -> List[LatencyMeasurement]:
        """POST endpoint testi."""
        url = f"{self.server_url}{endpoint}"
        self.measurements = []
        payload = {'data': 'x' * payload_size, 'timestamp': 0}
        
        # Warmup
        print(f"    [REST POST] Warmup: {warmup} istek...")
        for _ in range(warmup):
            try:
                self.session.post(url, json=payload, timeout=5)
            except:
                pass
            time.sleep(0.02)
        
        # Test
        print(f"    [REST POST] Test: {num_requests} istek -> {endpoint} (payload: {payload_size} bytes)")
        for i in range(num_requests):
            payload['timestamp'] = time.time()
            start_time = time.perf_counter()
            
            try:
                response = self.session.post(url, json=payload, timeout=5)
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                self.measurements.append(LatencyMeasurement(
                    test_type='rest_post',
                    timestamp=end_time,
                    latency_ms=latency_ms,
                    payload_size=payload_size,
                    success=response.status_code in [200, 201],
                    error_message=None if response.status_code in [200, 201] else f"HTTP {response.status_code}"
                ))
            except Exception as e:
                end_time = time.perf_counter()
                self.measurements.append(LatencyMeasurement(
                    test_type='rest_post',
                    timestamp=end_time,
                    latency_ms=(end_time - start_time) * 1000,
                    payload_size=payload_size,
                    success=False,
                    error_message=str(e)
                ))
            
            sys.stdout.write(f"\r    Progress: {i+1}/{num_requests}")
            sys.stdout.flush()
            time.sleep(0.01)
        
        print()
        return self.measurements


# =============================================================================
# CONCURRENT CONNECTION TEST
# =============================================================================

def single_request(server_url: str, request_id: int) -> Dict:
    """Tek bir HTTP isteği gönder (thread içinde çalışır)."""
    start_time = time.perf_counter()
    try:
        response = requests.get(f"{server_url}/leaderboard", timeout=10)
        end_time = time.perf_counter()
        return {
            'request_id': request_id,
            'latency_ms': (end_time - start_time) * 1000,
            'success': response.status_code == 200,
            'status_code': response.status_code
        }
    except Exception as e:
        end_time = time.perf_counter()
        return {
            'request_id': request_id,
            'latency_ms': (end_time - start_time) * 1000,
            'success': False,
            'error': str(e)
        }


def run_concurrent_test(server_url: str, concurrent_connections: int,
                        requests_per_connection: int = 10) -> ConcurrencyResult:
    """Eşzamanlı bağlantı testi."""
    total_requests = concurrent_connections * requests_per_connection
    results = []
    
    print(f"    [Concurrent] {concurrent_connections} bağlantı x {requests_per_connection} istek = {total_requests} toplam")
    
    start_time = time.perf_counter()
    
    with ThreadPoolExecutor(max_workers=concurrent_connections) as executor:
        futures = []
        for i in range(total_requests):
            futures.append(executor.submit(single_request, server_url, i))
        
        for future in as_completed(futures):
            results.append(future.result())
            sys.stdout.write(f"\r    Progress: {len(results)}/{total_requests}")
            sys.stdout.flush()
    
    end_time = time.perf_counter()
    total_time = end_time - start_time
    print()
    
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    latencies = [r['latency_ms'] for r in successful]
    
    return ConcurrencyResult(
        concurrent_connections=concurrent_connections,
        total_requests=total_requests,
        successful_requests=len(successful),
        failed_requests=len(failed),
        total_time_seconds=total_time,
        avg_latency_ms=statistics.mean(latencies) if latencies else 0,
        throughput_rps=len(successful) / total_time if total_time > 0 else 0,
        error_rate_percent=(len(failed) / total_requests * 100) if total_requests > 0 else 0
    )


# =============================================================================
# STATISTICS CALCULATOR
# =============================================================================

def calculate_statistics(measurements: List[LatencyMeasurement], 
                         test_name: str) -> Optional[TestResult]:
    """Ölçümlerden istatistik hesapla."""
    successful = [m for m in measurements if m.success]
    
    if not successful:
        return None
    
    latencies = [m.latency_ms for m in successful]
    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)
    
    # Percentile hesaplama
    p50_idx = int(n * 0.50)
    p95_idx = int(n * 0.95)
    p99_idx = int(n * 0.99)
    
    # Jitter (ardışık ölçümler arası fark)
    jitter_values = [abs(latencies[i] - latencies[i-1]) for i in range(1, len(latencies))]
    jitter = statistics.mean(jitter_values) if jitter_values else 0
    
    # Toplam süre (throughput için)
    if successful:
        total_time = successful[-1].timestamp - successful[0].timestamp
        throughput = len(successful) / total_time if total_time > 0 else 0
    else:
        throughput = 0
    
    return TestResult(
        test_name=test_name,
        test_type=successful[0].test_type if successful else 'unknown',
        sample_count=len(measurements),
        success_count=len(successful),
        failure_count=len(measurements) - len(successful),
        min_ms=min(latencies),
        max_ms=max(latencies),
        mean_ms=statistics.mean(latencies),
        median_ms=statistics.median(latencies),
        stdev_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0,
        p50_ms=sorted_latencies[p50_idx] if p50_idx < n else sorted_latencies[-1],
        p95_ms=sorted_latencies[p95_idx] if p95_idx < n else sorted_latencies[-1],
        p99_ms=sorted_latencies[p99_idx] if p99_idx < n else sorted_latencies[-1],
        jitter_ms=jitter,
        throughput_rps=throughput
    )


# =============================================================================
# NETWORK BENCHMARK SUITE
# =============================================================================

class NetworkBenchmarkSuite:
    """Ana benchmark suite sınıfı."""
    
    def __init__(self, server_url: str, output_dir: str):
        self.server_url = server_url
        self.output_dir = output_dir
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.all_measurements: List[LatencyMeasurement] = []
        self.test_results: List[TestResult] = []
        self.concurrency_results: List[ConcurrencyResult] = []
        
        os.makedirs(output_dir, exist_ok=True)
    
    def run_websocket_tests(self):
        """WebSocket testlerini çalıştır."""
        print("\n" + "="*60)
        print("TEST 1: WEBSOCKET LATENCY")
        print("="*60)
        
        ws = WebSocketBenchmark(self.server_url)
        if not ws.connect():
            print("    [HATA] WebSocket bağlantısı kurulamadı!")
            return
        
        try:
            # Farklı payload boyutlarıyla test
            for payload_size in PAYLOAD_SIZES:
                measurements = ws.run_latency_test(
                    num_requests=REQUESTS_PER_TEST,
                    warmup=WARMUP_REQUESTS,
                    payload_size=payload_size
                )
                self.all_measurements.extend(measurements)
                
                result = calculate_statistics(
                    measurements, 
                    f"websocket_payload_{payload_size}b"
                )
                if result:
                    self.test_results.append(result)
                    print(f"    ✓ Payload {payload_size}B: "
                          f"Mean={result.mean_ms:.2f}ms, P95={result.p95_ms:.2f}ms")
        finally:
            ws.disconnect()
    
    def run_rest_tests(self):
        """REST API testlerini çalıştır."""
        print("\n" + "="*60)
        print("TEST 2: REST API LATENCY")
        print("="*60)
        
        rest = RESTBenchmark(self.server_url)
        
        # GET endpoint testi
        endpoints = ['/leaderboard', '/active_games']
        for endpoint in endpoints:
            try:
                measurements = rest.run_get_test(
                    endpoint=endpoint,
                    num_requests=REQUESTS_PER_TEST,
                    warmup=WARMUP_REQUESTS
                )
                self.all_measurements.extend(measurements)
                
                result = calculate_statistics(measurements, f"rest_get_{endpoint.strip('/')}")
                if result:
                    self.test_results.append(result)
                    print(f"    ✓ GET {endpoint}: "
                          f"Mean={result.mean_ms:.2f}ms, P95={result.p95_ms:.2f}ms")
            except Exception as e:
                print(f"    ✗ GET {endpoint}: {e}")
        
        # POST endpoint testi (farklı payload boyutları)
        print("\n    --- POST Tests ---")
        for payload_size in PAYLOAD_SIZES[:2]:  # İlk 2 boyut yeterli
            try:
                measurements = rest.run_post_test(
                    endpoint='/signup',  # veya başka bir POST endpoint
                    payload_size=payload_size,
                    num_requests=REQUESTS_PER_TEST // 2,  # Daha az istek
                    warmup=WARMUP_REQUESTS // 2
                )
                self.all_measurements.extend(measurements)
                
                result = calculate_statistics(measurements, f"rest_post_{payload_size}b")
                if result:
                    self.test_results.append(result)
                    print(f"    ✓ POST {payload_size}B: "
                          f"Mean={result.mean_ms:.2f}ms, P95={result.p95_ms:.2f}ms")
            except Exception as e:
                print(f"    ✗ POST {payload_size}B: {e}")
    
    def run_concurrency_tests(self):
        """Eşzamanlı bağlantı testlerini çalıştır."""
        print("\n" + "="*60)
        print("TEST 3: CONCURRENT CONNECTIONS")
        print("="*60)
        
        for level in CONCURRENT_LEVELS:
            try:
                result = run_concurrent_test(
                    self.server_url,
                    concurrent_connections=level,
                    requests_per_connection=20
                )
                self.concurrency_results.append(result)
                
                status = "✓" if result.error_rate_percent < 5 else "⚠"
                print(f"    {status} {level} conn: "
                      f"Throughput={result.throughput_rps:.1f} RPS, "
                      f"Avg={result.avg_latency_ms:.1f}ms, "
                      f"Err={result.error_rate_percent:.1f}%")
            except Exception as e:
                print(f"    ✗ {level} connections: {e}")
    
    def export_results(self):
        """Sonuçları dosyalara kaydet."""
        print("\n" + "="*60)
        print("EXPORTING RESULTS")
        print("="*60)
        
        # 1. Raw measurements CSV
        raw_file = os.path.join(self.output_dir, f"raw_latency_{self.timestamp}.csv")
        with open(raw_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['test_type', 'timestamp', 'latency_ms', 'payload_size', 'success'])
            for m in self.all_measurements:
                writer.writerow([m.test_type, m.timestamp, f"{m.latency_ms:.4f}", 
                               m.payload_size, m.success])
        print(f"    [✓] Raw data: {raw_file}")
        
        # 2. Summary statistics CSV
        summary_file = os.path.join(self.output_dir, f"summary_{self.timestamp}.csv")
        with open(summary_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['test_name', 'test_type', 'samples', 'success', 'failure',
                           'min_ms', 'max_ms', 'mean_ms', 'median_ms', 'stdev_ms',
                           'p50_ms', 'p95_ms', 'p99_ms', 'jitter_ms', 'throughput_rps'])
            for r in self.test_results:
                writer.writerow([r.test_name, r.test_type, r.sample_count, r.success_count,
                               r.failure_count, f"{r.min_ms:.2f}", f"{r.max_ms:.2f}",
                               f"{r.mean_ms:.2f}", f"{r.median_ms:.2f}", f"{r.stdev_ms:.2f}",
                               f"{r.p50_ms:.2f}", f"{r.p95_ms:.2f}", f"{r.p99_ms:.2f}",
                               f"{r.jitter_ms:.2f}", f"{r.throughput_rps:.2f}"])
        print(f"    [✓] Summary: {summary_file}")
        
        # 3. Concurrency results CSV
        conc_file = os.path.join(self.output_dir, f"concurrency_{self.timestamp}.csv")
        with open(conc_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['concurrent_connections', 'total_requests', 'successful',
                           'failed', 'total_time_sec', 'avg_latency_ms', 
                           'throughput_rps', 'error_rate_percent'])
            for r in self.concurrency_results:
                writer.writerow([r.concurrent_connections, r.total_requests,
                               r.successful_requests, r.failed_requests,
                               f"{r.total_time_seconds:.2f}", f"{r.avg_latency_ms:.2f}",
                               f"{r.throughput_rps:.2f}", f"{r.error_rate_percent:.2f}"])
        print(f"    [✓] Concurrency: {conc_file}")
        
        # 4. Full JSON report
        json_file = os.path.join(self.output_dir, f"full_report_{self.timestamp}.json")
        report = {
            'timestamp': self.timestamp,
            'server_url': self.server_url,
            'config': {
                'warmup_requests': WARMUP_REQUESTS,
                'requests_per_test': REQUESTS_PER_TEST,
                'payload_sizes': PAYLOAD_SIZES,
                'concurrent_levels': CONCURRENT_LEVELS
            },
            'test_results': [asdict(r) for r in self.test_results],
            'concurrency_results': [asdict(r) for r in self.concurrency_results],
            'raw_measurements_count': len(self.all_measurements)
        }
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"    [✓] Full report: {json_file}")
        
        return {
            'raw_csv': raw_file,
            'summary_csv': summary_file,
            'concurrency_csv': conc_file,
            'json_report': json_file
        }
    
    def print_summary(self):
        """Özet raporu yazdır."""
        print("\n" + "="*60)
        print("NETWORK BENCHMARK SUMMARY")
        print("="*60)
        
        # WebSocket vs REST karşılaştırması
        ws_results = [r for r in self.test_results if r.test_type == 'websocket']
        rest_results = [r for r in self.test_results if r.test_type.startswith('rest')]
        
        if ws_results:
            ws_avg = statistics.mean([r.mean_ms for r in ws_results])
            print(f"\n  WebSocket Average: {ws_avg:.2f} ms")
        
        if rest_results:
            rest_avg = statistics.mean([r.mean_ms for r in rest_results])
            print(f"  REST API Average:  {rest_avg:.2f} ms")
        
        if ws_results and rest_results:
            diff_percent = ((rest_avg - ws_avg) / ws_avg) * 100
            faster = "WebSocket" if diff_percent > 0 else "REST"
            print(f"\n  → {faster} is {abs(diff_percent):.1f}% faster")
        
        # Concurrency summary
        if self.concurrency_results:
            print(f"\n  Concurrency Test Results:")
            for r in self.concurrency_results:
                status = "✓" if r.error_rate_percent == 0 else "⚠" if r.error_rate_percent < 5 else "✗"
                print(f"    {status} {r.concurrent_connections:3d} connections: "
                      f"{r.throughput_rps:6.1f} RPS, {r.error_rate_percent:.1f}% errors")
            
            # Find breaking point
            stable = [r for r in self.concurrency_results if r.error_rate_percent < 1]
            if stable:
                max_stable = max(stable, key=lambda x: x.concurrent_connections)
                print(f"\n  → Stable up to {max_stable.concurrent_connections} concurrent connections")
                print(f"  → Max stable throughput: {max_stable.throughput_rps:.1f} RPS")
    
    def run_all_tests(self):
        """Tüm testleri çalıştır."""
        print("\n" + "="*60)
        print("NETWORK BENCHMARK SUITE v2.0")
        print(f"Server: {self.server_url}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        start_time = time.time()
        
        # Sunucu erişilebilirlik kontrolü
        try:
            response = requests.get(f"{self.server_url}/leaderboard", timeout=5)
            print(f"\n[✓] Server is reachable (HTTP {response.status_code})")
        except Exception as e:
            print(f"\n[✗] Server is not reachable: {e}")
            print("    Make sure the server is running!")
            return None
        
        # Testleri çalıştır
        self.run_websocket_tests()
        self.run_rest_tests()
        self.run_concurrency_tests()
        
        # Sonuçları kaydet
        exported = self.export_results()
        
        # Özet
        self.print_summary()
        
        total_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"COMPLETED in {total_time:.1f} seconds")
        print(f"{'='*60}")
        
        return exported


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Network Benchmark Suite v2.0')
    parser.add_argument('--server', default=DEFAULT_SERVER, 
                        help=f'Server URL (default: {DEFAULT_SERVER})')
    parser.add_argument('--output', default=DEFAULT_OUTPUT_DIR,
                        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})')
    args = parser.parse_args()
    
    suite = NetworkBenchmarkSuite(args.server, args.output)
    suite.run_all_tests()