# =============================================================================
# MODULE: network_client.py
# Connect Four Pro - Istemci ag katmani (REST + Socket.IO)
# =============================================================================
"""
Socket.IO olaylari arka plan thread'inde gelir. Arayuz durumuna dogrudan
dokunmamak icin her olay `post(handler, data)` ile ana thread'in kuyruguna
birakilir; GUI bunlari kendi dongusunde isler.
"""

import threading
from typing import Any, Callable, Dict, Optional

import requests
import socketio

import config

log = config.get_logger("network")

# Sunucu olayi -> GUI metodu
_EVENT_HANDLERS = {
    'game_created': 'on_game_created',
    'game_joined': 'on_game_joined',
    'game_start': 'on_game_start',
    'move_made': 'on_move_made',
    'game_over': 'on_game_over_network',
    'elo_update': 'on_elo_update',
    'opponent_disconnected': 'on_opponent_disconnected',
    'opponent_reconnected': 'on_opponent_reconnected',
    'game_ended': 'on_game_ended',
    'error': 'on_server_error',
}


class NetworkManager:
    """
    Args:
        server_url: Sunucu adresi
        post: Ana thread'e is gonderen fonksiyon: post(callable, *args)
        handler: Olay metodlarini (on_game_created, ...) tasiyan nesne
    """

    def __init__(self, server_url: str, post: Callable[..., None], handler: Any):
        self.server_url = server_url
        self._post = post
        self._handler = handler
        self.sio = socketio.Client(reconnection=True, reconnection_attempts=5)
        self.connected = False
        self.room_id: Optional[str] = None
        self.my_piece: Optional[int] = None
        self.user_id: Optional[str] = None
        self.in_game = False             # Yeniden baglaninca odaya geri katil
        self._lock = threading.Lock()
        self._setup_events()

    def _setup_events(self) -> None:
        @self.sio.event
        def connect():
            self.connected = True
            log.info("Sunucuya baglandi")
            # Kopma sonrasi otomatik yeniden baglanma: oyuna geri don (NFR-08)
            if self.in_game and self.room_id and self.user_id:
                log.info("Oyuna yeniden katiliniyor: %s", self.room_id)
                self.sio.emit('join_game', {'room_id': self.room_id, 'user_id': self.user_id})

        @self.sio.event
        def disconnect():
            self.connected = False
            log.info("Sunucu baglantisi kesildi")

        for event, method in _EVENT_HANDLERS.items():
            self.sio.on(event, self._make_forwarder(event, method))

    def _make_forwarder(self, event: str, method: str):
        def forward(data=None):
            log.debug("<- %s %s", event, data)
            if event in ('game_created', 'game_joined') and isinstance(data, dict):
                self.room_id = data.get('room_id', self.room_id)
                self.my_piece = data.get('player_piece', self.my_piece)
                self.in_game = data.get('role') != 'spectator'
            elif event == 'game_over':
                self.in_game = False
            self._post(getattr(self._handler, method), data or {})
        return forward

    # ------------------------------------------------------------------
    # Socket.IO
    # ------------------------------------------------------------------

    def connect_to_server(self) -> bool:
        with self._lock:
            if self.connected:
                return True
            try:
                self.sio.connect(self.server_url, wait_timeout=5)
                return self.sio.connected
            except Exception as e:
                log.warning("Baglanti basarisiz: %s", e)
                return False

    def create_game(self, user_id: str) -> bool:
        if not self.connect_to_server():
            return False
        self.user_id = user_id
        self.sio.emit('create_game', {'user_id': user_id})
        return True

    def join_game(self, room_id: str, user_id: str) -> bool:
        if not self.connect_to_server():
            return False
        self.user_id = user_id
        self.sio.emit('join_game', {'room_id': room_id, 'user_id': user_id})
        return True

    def send_move(self, col: int) -> None:
        if self.connected and self.room_id:
            self.sio.emit('make_move', {'room_id': self.room_id, 'col': col, 'player_piece': self.my_piece})

    def leave_game(self) -> None:
        """Oyundan bilerek ayril (aktif oyunda hukmen yenilgi)."""
        if self.connected and self.room_id:
            try:
                self.sio.emit('leave_game', {'room_id': self.room_id})
            except Exception:
                pass
        self.in_game = False

    def disconnect(self) -> None:
        self.in_game = False
        if self.sio.connected:
            try:
                self.sio.disconnect()
            except Exception:
                pass
        self.connected = False
        self.room_id = None
        self.my_piece = None

    # ------------------------------------------------------------------
    # REST (bloklayan cagrilar; GUI bunlari arka plan thread'inde calistirir)
    # ------------------------------------------------------------------

    def _get(self, path: str, timeout: float = config.HTTP_TIMEOUT) -> requests.Response:
        return requests.get(f"{self.server_url}{path}", timeout=timeout)

    def login(self, username: str, password: str) -> requests.Response:
        return requests.post(f"{self.server_url}/login",
                             json={'username': username, 'password': password}, timeout=config.HTTP_TIMEOUT)

    def signup(self, username: str, password: str) -> requests.Response:
        return requests.post(f"{self.server_url}/signup",
                             json={'username': username, 'password': password}, timeout=config.HTTP_TIMEOUT)

    def fetch_active_games(self) -> list:
        r = self._get('/active_games', timeout=2)
        return r.json() if r.status_code == 200 else []

    def fetch_leaderboard(self) -> list:
        r = self._get('/leaderboard', timeout=3)
        r.raise_for_status()
        return r.json()

    def fetch_user(self, username: str) -> Optional[Dict[str, Any]]:
        r = self._get(f'/user/{username}', timeout=2)
        return r.json().get('user') if r.status_code == 200 else None

    def fetch_history(self, username: str) -> list:
        r = self._get(f'/user/{username}/games', timeout=3)
        r.raise_for_status()
        return r.json().get('games', [])
