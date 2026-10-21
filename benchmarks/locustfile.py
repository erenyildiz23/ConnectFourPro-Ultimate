#!/usr/bin/env python3
# =============================================================================
# LOCUST LOAD TEST v4.0
# Connect Four Pro - REST API yuk testi
# =============================================================================
"""
Uc kullanici profili (agirliklar %30 / %50 / %20):
  CasualPlayer  - yavas: liderlik tablosu, lobi, profil
  ActivePlayer  - orta: + tekrar giris, lobi yenileme, mac gecmisi
  PowerUser     - hizli: yogun polling, ardisik istekler, giris

Test hesaplari `locust_` on ekiyle olusturulur; temizlemek icin:
    python -c "import database; database.delete_test_users()"   (src/ icinde)

Kullanim (benchmarks/ icinde):
    locust -f locustfile.py --host http://localhost:5000 -u 100 -r 10 -t 2m --headless \
           --csv results/locust_100 --html results/locust_100.html
"""

import uuid

from locust import HttpUser, between, task

PASSWORD = "locust-pass"


class _Player(HttpUser):
    abstract = True

    def on_start(self):
        self.username = f"locust_{uuid.uuid4().hex[:12]}"
        with self.client.post("/signup", json={"username": self.username, "password": PASSWORD},
                              name="/signup", catch_response=True) as r:
            if r.status_code != 201:
                r.failure(f"signup {r.status_code}")
        self.login()

    def login(self):
        self.client.post("/login", json={"username": self.username, "password": PASSWORD}, name="/login")

    def leaderboard(self):
        self.client.get("/leaderboard", name="/leaderboard")

    def lobby(self):
        self.client.get("/active_games", name="/active_games")

    def profile(self):
        self.client.get(f"/user/{self.username}", name="/user/[name]")

    def history(self):
        self.client.get(f"/user/{self.username}/games", name="/user/[name]/games")


class CasualPlayer(_Player):
    weight = 3
    wait_time = between(3, 8)

    @task(5)
    def view_leaderboard(self):
        self.leaderboard()

    @task(3)
    def view_lobby(self):
        self.lobby()

    @task(1)
    def view_profile(self):
        self.profile()


class ActivePlayer(_Player):
    weight = 5
    wait_time = between(1, 4)

    @task(10)
    def view_leaderboard(self):
        self.leaderboard()

    @task(8)
    def view_lobby(self):
        self.lobby()

    @task(3)
    def lobby_refresh(self):
        for _ in range(3):
            self.lobby()

    @task(3)
    def view_history(self):
        self.history()

    @task(2)
    def relogin(self):
        self.login()

    @task(1)
    def health(self):
        self.client.get("/health", name="/health")


class PowerUser(_Player):
    weight = 2
    wait_time = between(0.5, 2)

    @task(15)
    def polling(self):
        self.leaderboard()
        self.lobby()

    @task(10)
    def burst(self):
        for _ in range(5):
            self.leaderboard()

    @task(5)
    def relogin(self):
        self.login()

    @task(3)
    def full_flow(self):
        self.login()
        self.leaderboard()
        self.lobby()
        self.profile()
        self.history()
