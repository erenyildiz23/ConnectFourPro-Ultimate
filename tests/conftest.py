"""
Ortak pytest fixture'lari.

Veritabani testleri icin ayri bir PostgreSQL veritabani gerekir:
    TEST_DATABASE_URL=postgresql://postgres:SIFRE@localhost/connect4_test
Bu veritabanina ulasilamazsa `db` isaretli testler atlanir (skip).
DIKKAT: Testler bu veritabanindaki tablolari her testte bosaltir.
"""

import os
import socket
import threading
import time

# Ayarlar config import edilmeden once yapilmali
os.environ.setdefault("RECONNECT_GRACE_SECONDS", "1")
os.environ.setdefault("PBKDF2_ITERATIONS", "1000")   # Testleri hizlandirir
os.environ.setdefault("DB_POOL_SIZE", "4")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pytest  # noqa: E402

import database as db  # noqa: E402

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://postgres@localhost/connect4_test")
UNREACHABLE_DB_URL = "postgresql://nobody@127.0.0.1:1/none?connect_timeout=1"


def wait_until(predicate, timeout=5.0, interval=0.02):
    """Kosul saglanana kadar bekler; saglanirsa True."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


# =============================================================================
# VERITABANI
# =============================================================================

@pytest.fixture(scope="session")
def _db_reachable():
    db.configure(TEST_DATABASE_URL)
    ok = db.init_db()
    db.configure(TEST_DATABASE_URL)
    return ok


@pytest.fixture
def database(_db_reachable):
    """Bos tablolarla test veritabani."""
    if not _db_reachable:
        pytest.skip(f"Test veritabani yok: {TEST_DATABASE_URL}")
    db.configure(TEST_DATABASE_URL)
    db.init_db()
    with db.get_db_cursor() as c:
        c.execute("TRUNCATE games, users RESTART IDENTITY CASCADE")
    yield db
    db.configure(TEST_DATABASE_URL)


@pytest.fixture
def no_database():
    """Veritabanina ulasilamayan durum."""
    db.configure(UNREACHABLE_DB_URL)
    yield db
    db.configure(TEST_DATABASE_URL)


# =============================================================================
# SUNUCU
# =============================================================================

@pytest.fixture
def server():
    """Temiz oda durumuyla server modulu."""
    import server as srv
    with srv.GAMES_LOCK:
        srv.GAMES.clear()
        srv.CONNECTED_USERS.clear()
    yield srv
    with srv.GAMES_LOCK:
        srv.GAMES.clear()
        srv.CONNECTED_USERS.clear()


@pytest.fixture
def http(server):
    return server.app.test_client()


class SocketClient:
    """flask_socketio test istemcisi icin olay biriktiren sarmalayici."""

    def __init__(self, server_module):
        self._srv = server_module
        self.client = server_module.socketio.test_client(server_module.app)
        self.inbox = []

    def emit(self, event, data=None):
        self.client.emit(event, data)

    def pull(self):
        self.inbox.extend(self.client.get_received())
        return self.inbox

    def events(self, name):
        """Gelen `name` olaylarinin verileri (biriktirilmis)."""
        self.pull()
        return [m['args'][0] if m['args'] else None for m in self.inbox if m['name'] == name]

    def last(self, name):
        found = self.events(name)
        return found[-1] if found else None

    def wait_for(self, name, timeout=3.0):
        assert wait_until(lambda: self.events(name), timeout), f"'{name}' olayi gelmedi"
        return self.last(name)

    def clear(self):
        self.pull()
        self.inbox.clear()

    def disconnect(self):
        if self.client.is_connected():
            self.client.disconnect()


@pytest.fixture
def sio(server):
    """SocketClient fabrikasi: sio() yeni bir baglanti acar."""
    clients = []

    def factory():
        c = SocketClient(server)
        clients.append(c)
        return c

    yield factory
    for c in clients:
        c.disconnect()


def start_match(sio, p1="alice", p2="bob"):
    """Iki oyunculu bir odayi baslatir: (oda_id, p1_istemci, p2_istemci)."""
    a, b = sio(), sio()
    a.emit('create_game', {'user_id': p1})
    room_id = a.wait_for('game_created')['room_id']
    b.emit('join_game', {'room_id': room_id, 'user_id': p2})
    b.wait_for('game_start')
    a.wait_for('game_start')
    a.clear()
    b.clear()
    return room_id, a, b


def play(room_id, a, b, cols):
    """Sirayla hamle yapar (a = P1, b = P2)."""
    for i, col in enumerate(cols):
        client, piece = (a, 1) if i % 2 == 0 else (b, 2)
        client.emit('make_move', {'room_id': room_id, 'col': col, 'player_piece': piece})


# P1'in dikey dortluyle kazandigi hamle dizisi
P1_VERTICAL_WIN = [0, 1, 0, 1, 0, 1, 0]
# Tahtanin dolup kimsenin kazanmadigi dogrulanmis dizi
DRAW_SEQUENCE = [3, 4, 4, 6, 0, 3, 5, 2, 6, 5, 0, 6, 5, 0, 3, 6, 5, 6, 1, 3, 1, 3, 6, 5, 2, 0,
                 5, 3, 4, 4, 0, 1, 1, 1, 0, 1, 4, 2, 4, 2, 2, 2]


# =============================================================================
# CANLI SUNUCU (GUI uctan uca testleri)
# =============================================================================

def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def live_server_url():
    """Gercek HTTP/WebSocket sunucusu (ayri thread)."""
    import server as srv
    port = _free_port()
    thread = threading.Thread(
        target=lambda: srv.socketio.run(srv.app, host="127.0.0.1", port=port,
                                        allow_unsafe_werkzeug=True, log_output=False),
        daemon=True)
    thread.start()
    url = f"http://127.0.0.1:{port}"

    import requests
    assert wait_until(lambda: _is_up(requests, url), timeout=10), "Canli sunucu baslamadi"
    return url


def _is_up(requests, url):
    try:
        return requests.get(f"{url}/health", timeout=0.5).status_code == 200
    except Exception:
        return False
