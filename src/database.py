# =============================================================================
# MODULE: database.py
# Connect Four Pro - PostgreSQL veri katmani
# =============================================================================
"""
Tum fonksiyonlar veritabanina ulasilamadiginda guvenli varsayilanlar dondurur
(None, [], 0); sunucu veritabani olmadan da acilir (misafir modu calisir).

Baglanti havuzu ilk kullanimda `config.DATABASE_URL` ile kurulur. Testler
`configure(url)` ile farkli bir veritabani kullanabilir.
"""

import hashlib
import hmac
import secrets
import threading
from contextlib import contextmanager
from typing import Any, Dict, List, Optional

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

import config

log = config.get_logger("database")

_pool: Optional[pool.ThreadedConnectionPool] = None
_pool_url: Optional[str] = None
_pool_failed = False
_pool_lock = threading.Lock()

# Yuk testlerinde olusturulan hesaplarin on ekleri (delete_test_users temizler)
TEST_USER_PREFIXES = ('locust_', 'test_user_', 'bench_')


# =============================================================================
# BAGLANTI YONETIMI
# =============================================================================

def configure(url: Optional[str] = None) -> None:
    """Havuzu kapatir; sonraki kullanimda `url` (veya config) ile yeniden kurulur."""
    global _pool, _pool_url, _pool_failed
    with _pool_lock:
        if _pool is not None:
            _pool.closeall()
        _pool = None
        _pool_failed = False
        _pool_url = url


def _get_pool() -> Optional[pool.ThreadedConnectionPool]:
    global _pool, _pool_failed
    if _pool is not None or _pool_failed:
        return _pool
    with _pool_lock:
        if _pool is None and not _pool_failed:
            try:
                _pool = pool.ThreadedConnectionPool(
                    config.DB_POOL_MIN, config.DB_POOL_MAX, dsn=_pool_url or config.DATABASE_URL)
                log.info("Connection pool created")
            except Exception as e:
                _pool_failed = True
                log.error("Veritabanina baglanilamadi (%s). DATABASE_URL ayarini kontrol edin.", e)
    return _pool


def is_available() -> bool:
    return _get_pool() is not None


@contextmanager
def get_db_cursor(transaction: bool = False):
    """
    Veritabani imleci verir; veritabani yoksa None verir.
    Blok icindeki hatalar cagirana iletilir (transaction=True ise geri alinir).
    """
    pg_pool = _get_pool()
    if pg_pool is None:
        yield None
        return
    try:
        conn = pg_pool.getconn()
    except Exception as e:
        log.error("Havuzdan baglanti alinamadi: %s", e)
        yield None
        return
    try:
        conn.autocommit = not transaction
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        if transaction:
            conn.commit()
    except Exception:
        if transaction:
            conn.rollback()
        raise
    finally:
        pg_pool.putconn(conn)


def init_db() -> bool:
    """Tablolari olusturur / gunceller. Basariliysa True."""
    try:
        with get_db_cursor() as c:
            if not c:
                return False
            c.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id SERIAL PRIMARY KEY,
                    username TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    email TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rating INTEGER DEFAULT 1200,
                    wins INTEGER DEFAULT 0,
                    losses INTEGER DEFAULT 0
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS games (
                    game_id SERIAL PRIMARY KEY,
                    player1_id INTEGER REFERENCES users(user_id),
                    player2_id INTEGER REFERENCES users(user_id),
                    winner_id INTEGER,
                    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    moves TEXT
                )
            ''')
            # v3 gocu: oyun bitis nedeni (normal / forfeit)
            c.execute("ALTER TABLE games ADD COLUMN IF NOT EXISTS end_reason TEXT DEFAULT 'normal'")
            c.execute('CREATE INDEX IF NOT EXISTS idx_users_rating ON users (rating DESC)')
            c.execute('CREATE INDEX IF NOT EXISTS idx_games_players ON games (player1_id, player2_id)')
            log.info("Schema verified")
            return True
    except Exception as e:
        log.error("init_db hatasi: %s", e)
        return False


# =============================================================================
# SIFRELEME
# =============================================================================

def _legacy_hash(password: str) -> str:
    """Eski format: tuzsuz SHA-256 (sadece eski hesaplari dogrulamak icin)."""
    return hashlib.sha256(password.encode()).hexdigest()


def hash_password(password: str, iterations: Optional[int] = None) -> str:
    """Tuzlu PBKDF2-SHA256. Format: pbkdf2_sha256$iterasyon$tuz$hash"""
    iterations = iterations or config.PBKDF2_ITERATIONS
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), iterations).hex()
    return f"pbkdf2_sha256${iterations}${salt}${digest}"


def check_password(password: str, stored: str) -> bool:
    if stored.startswith('pbkdf2_sha256$'):
        try:
            _, iterations, salt, digest = stored.split('$')
            calc = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), int(iterations)).hex()
            return hmac.compare_digest(calc, digest)
        except ValueError:
            return False
    return hmac.compare_digest(_legacy_hash(password), stored)


def _needs_rehash(stored: str) -> bool:
    if not stored.startswith('pbkdf2_sha256$'):
        return True
    try:
        return int(stored.split('$')[1]) < config.PBKDF2_ITERATIONS
    except (IndexError, ValueError):
        return True


# =============================================================================
# KULLANICILAR
# =============================================================================

_USER_COLUMNS = 'user_id, username, rating, wins, losses'


def create_user(username: str, password: str, email: str = "") -> Optional[int]:
    """Yeni kullanici; kullanici adi aliniyorsa veya DB yoksa None."""
    try:
        with get_db_cursor() as c:
            if not c:
                return None
            c.execute('INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s) RETURNING user_id',
                      (username, hash_password(password), email))
            return c.fetchone()['user_id']
    except psycopg2.IntegrityError:
        return None  # Kullanici adi zaten alinmis
    except Exception as e:
        log.error("create_user hatasi: %s", e)
        return None


def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Sifre dogruysa kullanici bilgisi (sifre hash'i olmadan), degilse None."""
    try:
        with get_db_cursor() as c:
            if not c:
                return None
            c.execute(f'SELECT {_USER_COLUMNS}, password_hash FROM users WHERE username = %s', (username,))
            row = c.fetchone()
            if not row or not check_password(password, row['password_hash']):
                return None
            # Eski/zayif hash'i basarili giriste guncelle
            if _needs_rehash(row['password_hash']):
                c.execute('UPDATE users SET password_hash = %s WHERE user_id = %s',
                          (hash_password(password), row['user_id']))
            user = dict(row)
            del user['password_hash']
            return user
    except Exception as e:
        log.error("verify_user hatasi: %s", e)
        return None


def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    try:
        with get_db_cursor() as c:
            if not c:
                return None
            c.execute(f'SELECT {_USER_COLUMNS} FROM users WHERE username = %s', (username,))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception as e:
        log.error("get_user_by_username hatasi: %s", e)
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    try:
        with get_db_cursor() as c:
            if not c:
                return None
            c.execute(f'SELECT {_USER_COLUMNS} FROM users WHERE user_id = %s', (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception as e:
        log.error("get_user_by_id hatasi: %s", e)
        return None


def get_top_players(limit: int = 10) -> List[Dict[str, Any]]:
    try:
        with get_db_cursor() as c:
            if not c:
                return []
            c.execute(f'SELECT {_USER_COLUMNS} FROM users ORDER BY rating DESC, wins DESC LIMIT %s', (limit,))
            return [dict(row) for row in c.fetchall()]
    except Exception as e:
        log.error("get_top_players hatasi: %s", e)
        return []


def get_user_count() -> int:
    try:
        with get_db_cursor() as c:
            if not c:
                return 0
            c.execute('SELECT COUNT(*) AS count FROM users')
            return c.fetchone()['count']
    except Exception:
        return 0


# =============================================================================
# ELO VE OYUN KAYITLARI
# =============================================================================

def elo_change(winner_rating: int, loser_rating: int,
               k_factor: Optional[int] = None, minimum: Optional[int] = None) -> int:
    """Kazananin kazanacagi puan (kaybeden ayni miktari kaybeder)."""
    k_factor = config.ELO_K_FACTOR if k_factor is None else k_factor
    minimum = config.ELO_MIN_CHANGE if minimum is None else minimum
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    return max(int(k_factor * (1 - expected_winner)), minimum)


def update_elo_by_username(winner_username: str, loser_username: str,
                           k_factor: Optional[int] = None) -> Dict[str, int]:
    """
    Iki kayitli oyuncunun ELO ve galibiyet/maglubiyet sayilarini gunceller.
    Oyunculardan biri kayitli degilse (misafir) degisiklik 0 doner.
    """
    no_change = {'winner_change': 0, 'loser_change': 0}
    try:
        # Tek transaction + satir kilidi: ya iki UPDATE birlikte uygulanir ya hic
        with get_db_cursor(transaction=True) as c:
            if not c:
                return no_change
            c.execute('SELECT user_id, rating FROM users WHERE username = %s FOR UPDATE', (winner_username,))
            winner = c.fetchone()
            c.execute('SELECT user_id, rating FROM users WHERE username = %s FOR UPDATE', (loser_username,))
            loser = c.fetchone()
            if not winner or not loser:
                log.info("ELO atlandi (kayitsiz oyuncu): %s vs %s", winner_username, loser_username)
                return no_change

            change = elo_change(winner['rating'], loser['rating'], k_factor)
            c.execute('UPDATE users SET rating = rating + %s, wins = wins + 1 WHERE user_id = %s',
                      (change, winner['user_id']))
            c.execute('UPDATE users SET rating = rating - %s, losses = losses + 1 WHERE user_id = %s',
                      (change, loser['user_id']))
            log.info("ELO %s +%d, %s -%d", winner_username, change, loser_username, change)
            return {'winner_change': change, 'loser_change': -change}
    except Exception as e:
        log.error("update_elo_by_username hatasi: %s", e)
        return no_change


def record_game(p1_username: str, p2_username: str, winner_username: Optional[str],
                moves: str, end_reason: str = 'normal') -> bool:
    """Biten oyunu kaydeder. Iki oyuncu da kayitli degilse False."""
    try:
        with get_db_cursor() as c:
            if not c:
                return False
            c.execute('SELECT user_id, username FROM users WHERE username = ANY(%s)',
                      ([p1_username, p2_username],))
            ids = {row['username']: row['user_id'] for row in c.fetchall()}
            if p1_username not in ids or p2_username not in ids:
                return False
            winner_id = ids.get(winner_username) if winner_username else None
            c.execute('INSERT INTO games (player1_id, player2_id, winner_id, moves, end_reason) '
                      'VALUES (%s, %s, %s, %s, %s)',
                      (ids[p1_username], ids[p2_username], winner_id, moves, end_reason))
            return True
    except Exception as e:
        log.error("record_game hatasi: %s", e)
        return False


def get_user_games(username: str, limit: int = 20) -> List[Dict[str, Any]]:
    """Kullanicinin son oyunlari (en yeni once)."""
    try:
        with get_db_cursor() as c:
            if not c:
                return []
            c.execute('''
                SELECT g.game_id, g.start_time, g.moves, g.end_reason,
                       p1.username AS player1, p2.username AS player2, w.username AS winner
                FROM games g
                JOIN users p1 ON p1.user_id = g.player1_id
                JOIN users p2 ON p2.user_id = g.player2_id
                LEFT JOIN users w ON w.user_id = g.winner_id
                WHERE p1.username = %s OR p2.username = %s
                ORDER BY g.start_time DESC, g.game_id DESC
                LIMIT %s
            ''', (username, username, limit))
            games = []
            for row in c.fetchall():
                game = dict(row)
                game['start_time'] = row['start_time'].isoformat() if row['start_time'] else None
                game['result'] = ('draw' if game['winner'] is None
                                  else 'win' if game['winner'] == username else 'loss')
                games.append(game)
            return games
    except Exception as e:
        log.error("get_user_games hatasi: %s", e)
        return []


def delete_test_users() -> int:
    """Yuk testlerinde olusturulan hesaplari ve oyunlarini siler."""
    patterns = [p.replace('_', r'\_') + '%' for p in TEST_USER_PREFIXES]
    try:
        with get_db_cursor(transaction=True) as c:
            if not c:
                return 0
            c.execute('SELECT user_id FROM users WHERE username LIKE ANY(%s)', (patterns,))
            ids = [row['user_id'] for row in c.fetchall()]
            if not ids:
                return 0
            c.execute('DELETE FROM games WHERE player1_id = ANY(%s) OR player2_id = ANY(%s)', (ids, ids))
            c.execute('DELETE FROM users WHERE user_id = ANY(%s)', (ids,))
            log.info("%d test kullanicisi silindi", len(ids))
            return len(ids)
    except Exception as e:
        log.error("delete_test_users hatasi: %s", e)
        return 0


if __name__ == "__main__":
    init_db()
