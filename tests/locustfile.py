# =============================================================================
# LOCUST YÜK TESTİ - GELİŞMİŞ VERSİYON v3.0
# 50-500 Concurrent User Test Suite
# =============================================================================

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner, WorkerRunner
import time
import random
import json
from datetime import datetime

# =============================================================================
# TEST SENARYOLARI
# =============================================================================

class CasualPlayer(HttpUser):
    """
    Gündelik oyuncu profili
    - Yavaş etkileşim
    - Sadece temel işlemler
    - %30 kullanıcı tabanı
    """
    weight = 3  # 30% oran
    wait_time = between(3, 8)  # 3-8 saniye bekleme
    
    def on_start(self):
        """Test başlangıcında login"""
        self.username = f"casual_{random.randint(1000, 9999)}"
        self.password = "test123"
        
        # Kayıt ol
        self.client.post("/signup", json={
            "username": self.username,
            "password": self.password
        })
        
        # Giriş yap
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
        """Liderlik tablosunu görüntüle"""
        self.client.get("/leaderboard")
        
    @task(3)
    def view_active_games(self):
        """Aktif oyunları görüntüle"""
        self.client.get("/active_games")
        
    @task(1)
    def check_profile(self):
        """Profil kontrolü"""
        if self.user_data:
            self.client.get(f"/user/{self.user_data.get('user_id', 0)}")


class ActivePlayer(HttpUser):
    """
    Aktif oyuncu profili
    - Orta hızda etkileşim
    - Tüm özellikler
    - %50 kullanıcı tabanı
    """
    weight = 5  # 50% oran
    wait_time = between(1, 4)  # 1-4 saniye
    
    def on_start(self):
        self.username = f"active_{random.randint(1000, 9999)}"
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
            
    @task(10)
    def view_leaderboard(self):
        self.client.get("/leaderboard")
        
    @task(8)
    def view_active_games(self):
        self.client.get("/active_games")
        
    @task(5)
    def login_flow(self):
        """Tekrar login simülasyonu"""
        self.client.post("/login", json={
            "username": self.username,
            "password": self.password
        })
        
    @task(3)
    def rapid_refresh(self):
        """Hızlı yenileme (lobby)"""
        for _ in range(3):
            self.client.get("/active_games")
            time.sleep(0.5)


class PowerUser(HttpUser):
    """
    Güçlü kullanıcı profili
    - Çok hızlı etkileşim
    - Yoğun API kullanımı
    - %20 kullanıcı tabanı
    """
    weight = 2  # 20% oran
    wait_time = between(0.5, 2)  # 0.5-2 saniye
    
    def on_start(self):
        self.username = f"power_{random.randint(1000, 9999)}"
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


# =============================================================================
# CUSTOM METRİKLER
# =============================================================================

# Test sonuçlarını kaydet
test_results = {
    "start_time": None,
    "end_time": None,
    "total_requests": 0,
    "successful_requests": 0,
    "failed_requests": 0,
    "avg_response_time": 0,
    "percentiles": {},
    "errors": []
}

@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    test_results["start_time"] = datetime.now().isoformat()
    print(f"\n{'='*60}")
    print(f"TEST BAŞLADI: {test_results['start_time']}")
    print(f"{'='*60}\n")

@events.test_stop.add_listener  
def on_test_stop(environment, **kwargs):
    test_results["end_time"] = datetime.now().isoformat()
    
    # Sonuçları dosyaya kaydet
    filename = f"load_test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(test_results, f, indent=2)
        
    print(f"\n{'='*60}")
    print(f"TEST BİTTİ: {test_results['end_time']}")
    print(f"Sonuçlar: {filename}")
    print(f"{'='*60}\n")

@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, **kwargs):
    test_results["total_requests"] += 1
    
    if exception:
        test_results["failed_requests"] += 1
        test_results["errors"].append(str(exception)[:100])
    else:
        test_results["successful_requests"] += 1


# =============================================================================
# KULLANIM TALİMATLARI
# =============================================================================
"""
50 Kullanıcı Testi:
------------------
locust -f locustfile_advanced.py --host=http://localhost:5000 -u 50 -r 5 -t 2m

100 Kullanıcı Testi:
-------------------
locust -f locustfile_advanced.py --host=http://localhost:5000 -u 100 -r 10 -t 3m

200 Kullanıcı Stress Testi:
--------------------------
locust -f locustfile_advanced.py --host=http://localhost:5000 -u 200 -r 20 -t 5m

500 Kullanıcı Maksimum Kapasite:
-------------------------------
locust -f locustfile_advanced.py --host=http://localhost:5000 -u 500 -r 50 -t 10m

Web UI ile:
----------
locust -f locustfile_advanced.py --host=http://localhost:5000
# Tarayıcıda http://localhost:8089 aç

Headless (CI/CD için):
---------------------
locust -f locustfile_advanced.py --host=http://localhost:5000 -u 100 -r 10 -t 5m --headless --csv=results

Parametreler:
- -u: Toplam kullanıcı sayısı
- -r: Saniyede spawn edilecek kullanıcı (ramp-up)
- -t: Test süresi (s/m/h)
- --headless: Web UI olmadan çalıştır
- --csv: CSV çıktısı prefix'i
"""
