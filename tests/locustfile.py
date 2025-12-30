#!/usr/bin/env python3
# =============================================================================
# LOCUST LOAD TEST SUITE v3.1 - THESIS EDITION
# Connect Four Bitirme Projesi - Yuk Testi
# =============================================================================
#
# Bu test suite farkli kullanici profillerini simule eder:
# 1. CasualPlayer: Yavas etkilesim, temel islemler (%30)
# 2. ActivePlayer: Orta hiz, tum ozellikler (%50)
# 3. PowerUser: Hizli etkilesim, yogun API kullanimi (%20)
#
# Kullanim:
#   locust -f locustfile.py --host=http://localhost:5000 -u 50 -r 5 -t 2m
#
# =============================================================================

from locust import HttpUser, task, between, events
import time
import random
import json
from datetime import datetime

# =============================================================================
# TEST SENARYOLARI
# =============================================================================

class CasualPlayer(HttpUser):
    """
    Gundelik oyuncu profili
    - Yavas etkilesim
    - Sadece temel islemler
    - %30 kullanici tabani
    """
    weight = 3  # 30% oran
    wait_time = between(3, 8)  # 3-8 saniye bekleme
    
    def on_start(self):
        """Test baslangicinda login"""
        self.username = f"casual_{random.randint(10000, 99999)}"
        self.password = "test123"
        
        # Kayit ol
        self.client.post("/signup", json={
            "username": self.username,
            "password": self.password
        })
        
        # Giris yap
        response = self.client.post("/login", json={
            "username": self.username,
            "password": self.password
        })
        
        if response.status_code == 200:
            self.user_data = response.json().get('user', {})
        else:
            self.user_data = {}
            
    @task(5)
    def view_leaderboard(self):
        """Liderlik tablosunu goruntule"""
        self.client.get("/leaderboard")
        
    @task(3)
    def view_active_games(self):
        """Aktif oyunlari goruntule"""
        self.client.get("/active_games")
        
    @task(1)
    def check_profile(self):
        """Profil kontrolu"""
        if self.username:
            self.client.get(f"/user/{self.username}")


class ActivePlayer(HttpUser):
    """
    Aktif oyuncu profili
    - Orta hizda etkilesim
    - Tum ozellikler
    - %50 kullanici tabani
    """
    weight = 5  # 50% oran
    wait_time = between(1, 4)  # 1-4 saniye
    
    def on_start(self):
        self.username = f"active_{random.randint(10000, 99999)}"
        self.password = "test123"
        
        self.client.post("/signup", json={
            "username": self.username,
            "password": self.password
        })
        
        response = self.client.post("/login", json={
            "username": self.username,
            "password": self.password
        })
        
        if response.status_code == 200:
            self.user_data = response.json().get('user', {})
        else:
            self.user_data = {}
            
    @task(10)
    def view_leaderboard(self):
        self.client.get("/leaderboard")
        
    @task(8)
    def view_active_games(self):
        self.client.get("/active_games")
        
    @task(5)
    def login_flow(self):
        """Tekrar login simulasyonu"""
        self.client.post("/login", json={
            "username": self.username,
            "password": self.password
        })
        
    @task(3)
    def rapid_refresh(self):
        """Hizli yenileme (lobby)"""
        for _ in range(3):
            self.client.get("/active_games")
            time.sleep(0.5)
    
    @task(2)
    def check_health(self):
        """Sunucu saglik kontrolu"""
        self.client.get("/health")


class PowerUser(HttpUser):
    """
    Guclu kullanici profili
    - Cok hizli etkilesim
    - Yogun API kullanimi
    - %20 kullanici tabani
    """
    weight = 2  # 20% oran
    wait_time = between(0.5, 2)  # 0.5-2 saniye
    
    def on_start(self):
        self.username = f"power_{random.randint(10000, 99999)}"
        self.password = "test123"
        
        self.client.post("/signup", json={
            "username": self.username,
            "password": self.password
        })
        
        response = self.client.post("/login", json={
            "username": self.username,
            "password": self.password
        })
        
        if response.status_code == 200:
            self.user_data = response.json().get('user', {})
        else:
            self.user_data = {}
            
    @task(15)
    def aggressive_polling(self):
        """Agresif API polling"""
        self.client.get("/leaderboard")
        self.client.get("/active_games")
        
    @task(10)
    def burst_requests(self):
        """Burst request paterni"""
        for _ in range(5):
            self.client.get("/leaderboard")
            
    @task(5)
    def stress_login(self):
        """Login stress testi"""
        self.client.post("/login", json={
            "username": self.username,
            "password": self.password
        })
    
    @task(3)
    def full_flow(self):
        """Tam kullanici akisi"""
        self.client.post("/login", json={
            "username": self.username,
            "password": self.password
        })
        self.client.get("/leaderboard")
        self.client.get("/active_games")
        self.client.get(f"/user/{self.username}")


# =============================================================================
# CUSTOM METRIKLER VE EVENT LISTENERS
# =============================================================================

# Test sonuclarini kaydet
test_results = {
    "start_time": None,
    "end_time": None,
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "response_times": [],
    "errors": []
}

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    test_results["start_time"] = datetime.now().isoformat()
    test_results["response_times"] = []
    test_results["errors"] = []
    test_results["total_requests"] = 0
    test_results["successful_requests"] = 0
    test_results["failed_requests"] = 0
    
    print(f"\n{'='*60}")
    print(f"  LOAD TEST STARTED")
    print(f"  Time: {test_results['start_time']}")
    print(f"{'='*60}\n")

@events.test_stop.add_listener  
def on_test_stop(environment, **kwargs):
    test_results["end_time"] = datetime.now().isoformat()
    
    # Sonuclari dosyaya kaydet
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"locust_results_{timestamp}.json"
    
    # Istatistikleri hesapla
    if test_results["response_times"]:
        sorted_times = sorted(test_results["response_times"])
        n = len(sorted_times)
        stats = {
            "min_ms": round(min(sorted_times), 2),
            "max_ms": round(max(sorted_times), 2),
            "avg_ms": round(sum(sorted_times) / n, 2),
            "median_ms": round(sorted_times[n // 2], 2),
            "p95_ms": round(sorted_times[int(n * 0.95)], 2),
            "p99_ms": round(sorted_times[min(int(n * 0.99), n-1)], 2),
        }
        test_results["statistics"] = stats
    
    # Error rate hesapla
    total = test_results["total_requests"]
    if total > 0:
        test_results["error_rate_percent"] = round(
            test_results["failed_requests"] / total * 100, 2
        )
        test_results["success_rate_percent"] = round(
            test_results["successful_requests"] / total * 100, 2
        )
    
    # Dosyaya kaydet
    with open(filename, 'w', encoding='utf-8') as f:
        # Response times listesini kisalt (cok buyuk olabilir)
        export_data = test_results.copy()
        export_data["response_times_sample"] = test_results["response_times"][:1000]
        del export_data["response_times"]
        json.dump(export_data, f, indent=2, ensure_ascii=False)
        
    print(f"\n{'='*60}")
    print(f"  LOAD TEST COMPLETED")
    print(f"  Time: {test_results['end_time']}")
    print(f"  Results: {filename}")
    print(f"{'='*60}")
    
    # Ozet yazdir
    if "statistics" in test_results:
        stats = test_results["statistics"]
        print(f"\n  Summary:")
        print(f"    Total Requests:  {test_results['total_requests']}")
        print(f"    Successful:      {test_results['successful_requests']}")
        print(f"    Failed:          {test_results['failed_requests']}")
        print(f"    Error Rate:      {test_results.get('error_rate_percent', 0)}%")
        print(f"    Avg Latency:     {stats['avg_ms']}ms")
        print(f"    P95 Latency:     {stats['p95_ms']}ms")
        print(f"    P99 Latency:     {stats['p99_ms']}ms")
    print()

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    test_results["total_requests"] += 1
    
    if exception:
        test_results["failed_requests"] += 1
        error_msg = str(exception)[:100]
        if len(test_results["errors"]) < 100:  # Limit error storage
            test_results["errors"].append({
                "endpoint": name,
                "error": error_msg
            })
    else:
        test_results["successful_requests"] += 1
        # Response time'lari kaydet (limit ile)
        if len(test_results["response_times"]) < 10000:
            test_results["response_times"].append(response_time)


# =============================================================================
# KULLANIM TALIMATLARI
# =============================================================================
"""
TEMEL KULLANIM:
===============

50 Kullanici Testi (2 dakika):
    locust -f locustfile.py --host=http://localhost:5000 -u 50 -r 5 -t 2m

100 Kullanici Testi (3 dakika):
    locust -f locustfile.py --host=http://localhost:5000 -u 100 -r 10 -t 3m

200 Kullanici Stress Testi (5 dakika):
    locust -f locustfile.py --host=http://localhost:5000 -u 200 -r 20 -t 5m

Web UI ile (tarayicida http://localhost:8089):
    locust -f locustfile.py --host=http://localhost:5000

Headless (CI/CD icin):
    locust -f locustfile.py --host=http://localhost:5000 -u 100 -r 10 -t 5m --headless --csv=results


PARAMETRELER:
=============
-u, --users     : Toplam kullanici sayisi
-r, --spawn-rate: Saniyede spawn edilecek kullanici (ramp-up)
-t, --run-time  : Test suresi (s/m/h)
--headless      : Web UI olmadan calistir
--csv           : CSV ciktisi prefix'i
--html          : HTML rapor dosyasi


ORNEK TEST SENARYOLARI:
=======================

1. Hafif Yuk (Normal kullanim):
   locust -f locustfile.py --host=http://localhost:5000 -u 20 -r 2 -t 1m

2. Orta Yuk (Yogun kullanim):
   locust -f locustfile.py --host=http://localhost:5000 -u 50 -r 5 -t 2m

3. Agir Yuk (Stress testi):
   locust -f locustfile.py --host=http://localhost:5000 -u 100 -r 10 -t 3m

4. Maksimum Kapasite (Boundary testi):
   locust -f locustfile.py --host=http://localhost:5000 -u 200 -r 20 -t 5m


NOT:
====
- Server'in onceden calisir durumda olmasi gerekir
- Test sonuclari otomatik olarak JSON dosyasina kaydedilir
- Web UI'da detayli grafikler gorulebilir
"""

if __name__ == "__main__":
    print(__doc__)
