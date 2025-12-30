#!/usr/bin/env python3
# =============================================================================
# NETWORK BENCHMARK SUITE v2.1 - THESIS EDITION
# Connect Four Bitirme Projesi - Network Performans Analizi
# =============================================================================
#
# Bu test suite aşağıdaki metrikleri ölçer:
# 1. WebSocket Round-Trip Time (RTT)
# 2. REST API Response Time
# 3. Payload Size vs Latency ilişkisi
# 4. Concurrent Connection performansı
# 5. Jitter (gecikme varyansı) analizi
#
# Kullanım: python network_benchmark.py [--server URL] [--output DIR]
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
DEFAULT_OUTPUT_DIR = './test_results'

# Test Parameters
WARMUP_REQUESTS = 10
REQUESTS_PER_TEST = 100
PAYLOAD_SIZES = [64, 256, 1024, 4096]
CONCURRENT_LEVELS = [1, 5, 10, 20, 50]

# =============================================================================
# DATA CLASSES
# =============================================================================

@dataclass
class LatencyMeasurement:
    """Single latency measurement."""
    test_type: str          # 'websocket', 'rest_get', 'rest_post'
    timestamp: float
    latency_ms: float
    payload_size: int
    success: bool
    error_message: Optional[str] = None

@dataclass
class TestResult:
    """Summary statistics for a test series."""
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
    jitter_ms: float
    throughput_rps: float

@dataclass 
class ConcurrencyResult:
    """Concurrent connection test result."""
    concurrent_connections: int
    total_requests: int
    successful_requests: int
    failed_requests: int
    total_time_seconds: float
    avg_latency_ms: float
    throughput_rps: float
    error_rate_percent: float

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_statistics(measurements: List[LatencyMeasurement], 
                        test_name: str) -> Optional[TestResult]:
    """Calculate summary statistics from measurements."""
    
    successful = [m for m in measurements if m.success]
    if not successful:
        return None
    
    latencies = [m.latency_ms for m in successful]
    sorted_latencies = sorted(latencies)
    n = len(sorted_latencies)
    
    # Calculate jitter (consecutive differences)
    if len(latencies) > 1:
        jitter = statistics.stdev([latencies[i+1] - latencies[i] 
                                   for i in range(len(latencies)-1)])
    else:
        jitter = 0
    
    return TestResult(
        test_name=test_name,
        test_type=measurements[0].test_type if measurements else 'unknown',
        sample_count=len(measurements),
        success_count=len(successful),
        failure_count=len(measurements) - len(successful),
        min_ms=min(latencies),
        max_ms=max(latencies),
        mean_ms=statistics.mean(latencies),
        median_ms=statistics.median(latencies),
        stdev_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0,
        p50_ms=sorted_latencies[int(n * 0.50)],
        p95_ms=sorted_latencies[int(n * 0.95)],
        p99_ms=sorted_latencies[min(int(n * 0.99), n-1)],
        jitter_ms=jitter,
        throughput_rps=len(successful) / sum(latencies) * 1000 if latencies else 0
    )

# =============================================================================
# WEBSOCKET BENCHMARK
# =============================================================================

class WebSocketBenchmark:
    """WebSocket RTT measurement class."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.measurements: List[LatencyMeasurement] = []
        self.pending_start_time: Optional[float] = None
        self.response_received = threading.Event()
        self.sio = None
        self.connected = False
        
    def connect(self) -> bool:
        """Connect to server."""
        try:
            self.sio = socketio.Client(reconnection=False)
            
            @self.sio.on('connect')
            def on_connect():
                self.connected = True
            
            @self.sio.on('disconnect')
            def on_disconnect():
                self.connected = False
            
            @self.sio.on('game_created')
            def on_game_created(data):
                self._handle_response(data)
            
            @self.sio.on('error')
            def on_error(data):
                self._handle_response(data, success=False)
            
            self.sio.connect(self.server_url, wait_timeout=10)
            time.sleep(0.5)
            return self.connected
            
        except Exception as e:
            print(f"    [WebSocket] Connection error: {e}")
            return False
    
    def disconnect(self):
        """Close connection."""
        if self.sio and self.connected:
            try:
                self.sio.disconnect()
            except:
                pass
    
    def _handle_response(self, data, success: bool = True):
        """Handle server response."""
        end_time = time.perf_counter()
        
        if self.pending_start_time is not None:
            latency_ms = (end_time - self.pending_start_time) * 1000
            
            self.measurements.append(LatencyMeasurement(
                test_type='websocket',
                timestamp=end_time,
                latency_ms=latency_ms,
                payload_size=len(str(data)) if data else 0,
                success=success,
                error_message=None if success else str(data)
            ))
            
            self.pending_start_time = None
            self.response_received.set()
    
    def run_latency_test(self, num_requests: int = 100, 
                         warmup: int = 10,
                         payload_size: int = 64) -> List[LatencyMeasurement]:
        """Run latency test."""
        self.measurements = []
        
        # Warmup
        print(f"    [WebSocket] Warmup: {warmup} requests...")
        for i in range(warmup):
            self.response_received.clear()
            self.pending_start_time = time.perf_counter()
            self.sio.emit('create_game', {'user_id': 9999, 'padding': 'x' * payload_size})
            self.response_received.wait(timeout=5)
            time.sleep(0.02)
        
        self.measurements = []  # Clear warmup data
        
        # Actual test
        print(f"    [WebSocket] Testing: {num_requests} requests (payload: {payload_size} bytes)...")
        for i in range(num_requests):
            self.response_received.clear()
            self.pending_start_time = time.perf_counter()
            self.sio.emit('create_game', {'user_id': 9999, 'padding': 'x' * payload_size})
            
            if not self.response_received.wait(timeout=5):
                # Timeout
                self.measurements.append(LatencyMeasurement(
                    test_type='websocket',
                    timestamp=time.perf_counter(),
                    latency_ms=5000,
                    payload_size=payload_size,
                    success=False,
                    error_message='Timeout'
                ))
            
            time.sleep(0.02)
            
            if (i + 1) % 20 == 0:
                print(f"    Progress: {i+1}/{num_requests}", end='\r')
        
        print(f"    Completed: {len(self.measurements)} measurements")
        return self.measurements


# =============================================================================
# REST API BENCHMARK
# =============================================================================

class RESTBenchmark:
    """REST API benchmark class."""
    
    def __init__(self, server_url: str):
        self.server_url = server_url
        self.session = requests.Session()
    
    def run_get_test(self, endpoint: str, num_requests: int = 100,
                     warmup: int = 10) -> List[LatencyMeasurement]:
        """Run GET request test."""
        measurements = []
        url = f"{self.server_url}{endpoint}"
        
        # Warmup
        for _ in range(warmup):
            try:
                self.session.get(url, timeout=5)
            except:
                pass
            time.sleep(0.01)
        
        # Test
        for i in range(num_requests):
            start_time = time.perf_counter()
            try:
                response = self.session.get(url, timeout=5)
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                measurements.append(LatencyMeasurement(
                    test_type='rest_get',
                    timestamp=end_time,
                    latency_ms=latency_ms,
                    payload_size=len(response.content),
                    success=response.status_code == 200
                ))
            except Exception as e:
                end_time = time.perf_counter()
                measurements.append(LatencyMeasurement(
                    test_type='rest_get',
                    timestamp=end_time,
                    latency_ms=(end_time - start_time) * 1000,
                    payload_size=0,
                    success=False,
                    error_message=str(e)
                ))
            
            time.sleep(0.01)
        
        return measurements
    
    def run_post_test(self, endpoint: str, payload_size: int = 64,
                      num_requests: int = 50, warmup: int = 5) -> List[LatencyMeasurement]:
        """Run POST request test."""
        measurements = []
        url = f"{self.server_url}{endpoint}"
        payload = {'data': 'x' * payload_size}
        
        # Warmup
        for _ in range(warmup):
            try:
                self.session.post(url, json=payload, timeout=5)
            except:
                pass
            time.sleep(0.01)
        
        # Test
        for i in range(num_requests):
            start_time = time.perf_counter()
            try:
                response = self.session.post(url, json=payload, timeout=5)
                end_time = time.perf_counter()
                latency_ms = (end_time - start_time) * 1000
                
                measurements.append(LatencyMeasurement(
                    test_type='rest_post',
                    timestamp=end_time,
                    latency_ms=latency_ms,
                    payload_size=payload_size,
                    success=response.status_code in [200, 201, 400, 409]
                ))
            except Exception as e:
                end_time = time.perf_counter()
                measurements.append(LatencyMeasurement(
                    test_type='rest_post',
                    timestamp=end_time,
                    latency_ms=(end_time - start_time) * 1000,
                    payload_size=payload_size,
                    success=False,
                    error_message=str(e)
                ))
            
            time.sleep(0.01)
        
        return measurements


# =============================================================================
# CONCURRENT CONNECTION TEST
# =============================================================================

def run_concurrent_test(server_url: str, concurrent_connections: int = 10,
                       requests_per_connection: int = 20) -> ConcurrencyResult:
    """Run concurrent connection test."""
    
    results = []
    lock = threading.Lock()
    start_time = time.perf_counter()
    
    def worker(worker_id: int):
        session = requests.Session()
        local_results = []
        
        for i in range(requests_per_connection):
            req_start = time.perf_counter()
            try:
                response = session.get(f"{server_url}/leaderboard", timeout=10)
                req_end = time.perf_counter()
                
                local_results.append({
                    'success': response.status_code == 200,
                    'latency_ms': (req_end - req_start) * 1000
                })
            except Exception as e:
                req_end = time.perf_counter()
                local_results.append({
                    'success': False,
                    'latency_ms': (req_end - req_start) * 1000
                })
        
        with lock:
            results.extend(local_results)
    
    # Run concurrent workers
    threads = []
    for i in range(concurrent_connections):
        t = threading.Thread(target=worker, args=(i,))
        threads.append(t)
        t.start()
    
    for t in threads:
        t.join()
    
    end_time = time.perf_counter()
    total_time = end_time - start_time
    
    # Calculate statistics
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]
    
    avg_latency = statistics.mean([r['latency_ms'] for r in successful]) if successful else 0
    throughput = len(successful) / total_time if total_time > 0 else 0
    error_rate = (len(failed) / len(results) * 100) if results else 0
    
    return ConcurrencyResult(
        concurrent_connections=concurrent_connections,
        total_requests=len(results),
        successful_requests=len(successful),
        failed_requests=len(failed),
        total_time_seconds=total_time,
        avg_latency_ms=avg_latency,
        throughput_rps=throughput,
        error_rate_percent=error_rate
    )


# =============================================================================
# MAIN BENCHMARK SUITE
# =============================================================================

class NetworkBenchmarkSuite:
    """Complete network benchmark suite."""
    
    def __init__(self, server_url: str = DEFAULT_SERVER, 
                 output_dir: str = DEFAULT_OUTPUT_DIR):
        self.server_url = server_url
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Results storage
        self.all_measurements: List[LatencyMeasurement] = []
        self.test_results: List[TestResult] = []
        self.concurrency_results: List[ConcurrencyResult] = []
    
    def run_websocket_tests(self):
        """Run WebSocket tests."""
        print("\n" + "="*60)
        print("TEST 1: WEBSOCKET LATENCY")
        print("="*60)
        
        ws = WebSocketBenchmark(self.server_url)
        
        if not ws.connect():
            print("    [ERROR] Could not connect to WebSocket server!")
            return
        
        try:
            for payload_size in PAYLOAD_SIZES:
                measurements = ws.run_latency_test(
                    num_requests=REQUESTS_PER_TEST,
                    warmup=WARMUP_REQUESTS,
                    payload_size=payload_size
                )
                self.all_measurements.extend(measurements)
                
                result = calculate_statistics(measurements, f"websocket_{payload_size}b")
                if result:
                    self.test_results.append(result)
                    print(f"    [OK] {payload_size}B: Mean={result.mean_ms:.2f}ms, "
                          f"P95={result.p95_ms:.2f}ms, P99={result.p99_ms:.2f}ms")
        finally:
            ws.disconnect()
    
    def run_rest_tests(self):
        """Run REST API tests."""
        print("\n" + "="*60)
        print("TEST 2: REST API LATENCY")
        print("="*60)
        
        rest = RESTBenchmark(self.server_url)
        
        # GET tests
        print("\n  GET /leaderboard:")
        measurements = rest.run_get_test('/leaderboard', REQUESTS_PER_TEST, WARMUP_REQUESTS)
        self.all_measurements.extend(measurements)
        
        result = calculate_statistics(measurements, "rest_get_leaderboard")
        if result:
            self.test_results.append(result)
            print(f"    [OK] Mean={result.mean_ms:.2f}ms, P95={result.p95_ms:.2f}ms")
        
        # GET active_games
        print("\n  GET /active_games:")
        measurements = rest.run_get_test('/active_games', REQUESTS_PER_TEST, WARMUP_REQUESTS)
        self.all_measurements.extend(measurements)
        
        result = calculate_statistics(measurements, "rest_get_active_games")
        if result:
            self.test_results.append(result)
            print(f"    [OK] Mean={result.mean_ms:.2f}ms, P95={result.p95_ms:.2f}ms")
        
        # POST tests
        print("\n  POST /signup (various payloads):")
        for payload_size in PAYLOAD_SIZES[:2]:  # Just first two sizes
            measurements = rest.run_post_test(
                '/signup',
                payload_size=payload_size,
                num_requests=REQUESTS_PER_TEST // 2,
                warmup=WARMUP_REQUESTS // 2
            )
            self.all_measurements.extend(measurements)
            
            result = calculate_statistics(measurements, f"rest_post_{payload_size}b")
            if result:
                self.test_results.append(result)
                print(f"    [OK] {payload_size}B: Mean={result.mean_ms:.2f}ms, "
                      f"P95={result.p95_ms:.2f}ms")
    
    def run_concurrency_tests(self):
        """Run concurrent connection tests."""
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
                
                status = "[OK]" if result.error_rate_percent < 5 else "[WARN]"
                print(f"    {status} {level} conn: "
                      f"Throughput={result.throughput_rps:.1f} RPS, "
                      f"Avg={result.avg_latency_ms:.1f}ms, "
                      f"Err={result.error_rate_percent:.1f}%")
            except Exception as e:
                print(f"    [ERROR] {level} connections: {e}")
    
    def export_results(self):
        """Export results to files."""
        print("\n" + "="*60)
        print("EXPORTING RESULTS")
        print("="*60)
        
        # 1. Raw measurements CSV
        raw_file = os.path.join(self.output_dir, f"network_raw_{self.timestamp}.csv")
        with open(raw_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['test_type', 'timestamp', 'latency_ms', 'payload_size', 'success'])
            for m in self.all_measurements:
                writer.writerow([m.test_type, m.timestamp, f"{m.latency_ms:.4f}", 
                               m.payload_size, m.success])
        print(f"    [OK] Raw data: {raw_file}")
        
        # 2. Summary statistics CSV
        summary_file = os.path.join(self.output_dir, f"network_summary_{self.timestamp}.csv")
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
        print(f"    [OK] Summary: {summary_file}")
        
        # 3. Concurrency results CSV
        conc_file = os.path.join(self.output_dir, f"network_concurrency_{self.timestamp}.csv")
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
        print(f"    [OK] Concurrency: {conc_file}")
        
        # 4. Full JSON report
        json_file = os.path.join(self.output_dir, f"network_results_{self.timestamp}.json")
        report = {
            'timestamp': self.timestamp,
            'server_url': self.server_url,
            'config': {
                'warmup_requests': WARMUP_REQUESTS,
                'requests_per_test': REQUESTS_PER_TEST,
                'payload_sizes': PAYLOAD_SIZES,
                'concurrent_levels': CONCURRENT_LEVELS
            },
            'summary': self._calculate_summary(),
            'test_results': [asdict(r) for r in self.test_results],
            'concurrency_results': [asdict(r) for r in self.concurrency_results],
            'raw_measurements_count': len(self.all_measurements)
        }
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"    [OK] Full report: {json_file}")
        
        return {
            'raw_csv': raw_file,
            'summary_csv': summary_file,
            'concurrency_csv': conc_file,
            'json_report': json_file
        }
    
    def _calculate_summary(self) -> Dict:
        """Calculate summary for JSON export."""
        ws_results = [r for r in self.test_results if r.test_type == 'websocket']
        rest_results = [r for r in self.test_results if r.test_type.startswith('rest')]
        
        summary = {}
        
        if ws_results:
            summary['websocket'] = {
                'avg_latency_ms': round(statistics.mean([r.mean_ms for r in ws_results]), 2),
                'avg_p95_ms': round(statistics.mean([r.p95_ms for r in ws_results]), 2),
                'tests_run': len(ws_results)
            }
        
        if rest_results:
            summary['rest'] = {
                'avg_latency_ms': round(statistics.mean([r.mean_ms for r in rest_results]), 2),
                'avg_p95_ms': round(statistics.mean([r.p95_ms for r in rest_results]), 2),
                'tests_run': len(rest_results)
            }
        
        if self.concurrency_results:
            stable = [r for r in self.concurrency_results if r.error_rate_percent < 1]
            if stable:
                max_stable = max(stable, key=lambda x: x.concurrent_connections)
                summary['concurrency'] = {
                    'max_stable_connections': max_stable.concurrent_connections,
                    'max_throughput_rps': round(max_stable.throughput_rps, 2)
                }
        
        return summary
    
    def print_summary(self):
        """Print summary report."""
        print("\n" + "="*60)
        print("NETWORK BENCHMARK SUMMARY")
        print("="*60)
        
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
            print(f"\n  -> {faster} is {abs(diff_percent):.1f}% faster")
        
        if self.concurrency_results:
            print(f"\n  Concurrency Test Results:")
            for r in self.concurrency_results:
                status = "[OK]" if r.error_rate_percent == 0 else "[WARN]" if r.error_rate_percent < 5 else "[FAIL]"
                print(f"    {status} {r.concurrent_connections:3d} connections: "
                      f"{r.throughput_rps:6.1f} RPS, {r.error_rate_percent:.1f}% errors")
            
            stable = [r for r in self.concurrency_results if r.error_rate_percent < 1]
            if stable:
                max_stable = max(stable, key=lambda x: x.concurrent_connections)
                print(f"\n  -> Stable up to {max_stable.concurrent_connections} concurrent connections")
                print(f"  -> Max stable throughput: {max_stable.throughput_rps:.1f} RPS")
    
    def run_all_tests(self):
        """Run all tests."""
        print("\n" + "="*60)
        print("NETWORK BENCHMARK SUITE v2.1")
        print(f"Server: {self.server_url}")
        print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        start_time = time.time()
        
        # Server reachability check
        try:
            response = requests.get(f"{self.server_url}/health", timeout=5)
            print(f"\n[OK] Server is reachable (HTTP {response.status_code})")
        except:
            try:
                response = requests.get(f"{self.server_url}/leaderboard", timeout=5)
                print(f"\n[OK] Server is reachable (HTTP {response.status_code})")
            except Exception as e:
                print(f"\n[ERROR] Server is not reachable: {e}")
                print("    Make sure the server is running!")
                return None
        
        # Run tests
        self.run_websocket_tests()
        self.run_rest_tests()
        self.run_concurrency_tests()
        
        # Export results
        exported = self.export_results()
        
        # Summary
        self.print_summary()
        
        total_time = time.time() - start_time
        print(f"\n{'='*60}")
        print(f"COMPLETED in {total_time:.1f} seconds")
        print(f"Results saved to: {self.output_dir}/")
        print(f"{'='*60}")
        
        return exported


# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Network Benchmark Suite v2.1')
    parser.add_argument('--server', default=DEFAULT_SERVER, 
                        help=f'Server URL (default: {DEFAULT_SERVER})')
    parser.add_argument('--output', default=DEFAULT_OUTPUT_DIR,
                        help=f'Output directory (default: {DEFAULT_OUTPUT_DIR})')
    args = parser.parse_args()
    
    print("="*60)
    print("  CONNECT FOUR - NETWORK BENCHMARK SUITE")
    print("="*60)
    
    suite = NetworkBenchmarkSuite(args.server, args.output)
    suite.run_all_tests()
