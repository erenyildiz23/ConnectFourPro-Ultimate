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
import json
import secrets
import threading
import time
from contextlib import contextmanager
from datetime import datetime, timedelta
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
# psycopg2 havuzu doluyken beklemek yerine hata firlatir; semafor bekletir
_pool_slots = threading.BoundedSemaphore(config.DB_POOL_SIZE)

# id(baglanti) -> son kullanim zamani (bkz. _checkout)
_last_used: Dict[int, float] = {}

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
        _last_used.clear()
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
                # min = max: baglantilar acik kalir (her istekte yeniden baglanma yok)
                _pool = pool.ThreadedConnectionPool(
                    config.DB_POOL_SIZE, config.DB_POOL_SIZE, dsn=_pool_url or config.DATABASE_URL)
                log.info("Connection pool created")
            except Exception as e:
                _pool_failed = True
                log.error("Veritabanina baglanilamadi (%s). DATABASE_URL ayarini kontrol edin.", e)
    return _pool


def is_available() -> bool:
    return _get_pool() is not None


def _checkout(pg_pool: pool.ThreadedConnectionPool):
    """
    Havuzdan kullanilabilir bir baglanti alir. Yonetilen PostgreSQL servisleri
    (Supabase, Neon...) bosta kalan baglantilari kapatir; uzun suredir
    kullanilmamis baglanti once yoklanir, kopmussa yenisiyle degistirilir.
    Boylece kopuk baglanti ilk istegi (or. girisi) basarisiz kilmaz.
    """
    # Havuzdaki baglantilarin hepsi kopmus olabilir: saglam olani bulana kadar dene
    for _ in range(config.DB_POOL_SIZE + 1):
        conn = pg_pool.getconn()
        idle = time.monotonic() - _last_used.get(id(conn), 0.0)
        if not conn.closed and idle <= config.DB_PING_AFTER_SECONDS:
            return conn
        try:
            if conn.closed:
                raise psycopg2.InterfaceError("connection already closed")
            conn.autocommit = True
            with conn.cursor() as cur:
                cur.execute('SELECT 1')
            return conn
        except (psycopg2.OperationalError, psycopg2.InterfaceError):
            log.info("Kopmus veritabani baglantisi yenileniyor")
            _last_used.pop(id(conn), None)
            pg_pool.putconn(conn, close=True)
    return pg_pool.getconn()


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
    if not _pool_slots.acquire(timeout=config.DB_POOL_TIMEOUT):
        log.error("Veritabani baglantisi %d sn icinde bosalmadi", config.DB_POOL_TIMEOUT)
        yield None
        return
    try:
        conn = _checkout(pg_pool)
    except Exception as e:
        _pool_slots.release()
        log.error("Havuzdan baglanti alinamadi: %s", e)
        yield None
        return
    broken = False
    try:
        conn.autocommit = not transaction
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            yield cur
        if transaction:
            conn.commit()
    except (psycopg2.OperationalError, psycopg2.InterfaceError):
        broken = True    # Kopmus baglantiyi havuza geri koyma
        raise
    except Exception:
        if transaction:
            conn.rollback()
        raise
    finally:
        close = broken or bool(conn.closed)
        if close:
            _last_used.pop(id(conn), None)
        else:
            _last_used[id(conn)] = time.monotonic()
        try:
            pg_pool.putconn(conn, close=close)
        except pool.PoolError:
            # Havuz bu sirada kapatildiysa (configure) baglantiyi birak; yuva yine de iade edilir
            _last_used.pop(id(conn), None)
            try:
                conn.close()
            except Exception:
                pass
        finally:
            _pool_slots.release()


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
            # Arena turnuvasi: turnuva ve katilimci tablolari
            c.execute('''
                CREATE TABLE IF NOT EXISTS tournaments (
                    id SERIAL PRIMARY KEY,
                    creator_id INTEGER REFERENCES users(user_id),
                    duration_minutes INTEGER NOT NULL,
                    starts_at TIMESTAMPTZ NOT NULL,
                    ends_at TIMESTAMPTZ NOT NULL,
                    started_at TIMESTAMPTZ NULL,
                    status TEXT NOT NULL DEFAULT 'scheduled',
                    created_at TIMESTAMPTZ DEFAULT now(),
                    cheat_checked_at TIMESTAMPTZ NULL
                )
            ''')
            c.execute('''
                CREATE TABLE IF NOT EXISTS tournament_players (
                    tournament_id INTEGER REFERENCES tournaments(id),
                    user_id INTEGER REFERENCES users(user_id),
                    score INTEGER DEFAULT 0,
                    games_played INTEGER DEFAULT 0,
                    streak INTEGER DEFAULT 0,
                    paused BOOLEAN DEFAULT FALSE,
                    recent TEXT DEFAULT '',
                    joined_at TIMESTAMPTZ DEFAULT now(),
                    PRIMARY KEY (tournament_id, user_id)
                )
            ''')
            c.execute('ALTER TABLE games ADD COLUMN IF NOT EXISTS tournament_id INTEGER NULL')
            c.execute('CREATE INDEX IF NOT EXISTS idx_tplayers_score '
                      'ON tournament_players (tournament_id, score DESC)')
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
                moves: str, end_reason: str = 'normal',
                tournament_id: Optional[int] = None) -> bool:
    """Biten oyunu kaydeder (istege bagli turnuva ile). Iki oyuncu da kayitli degilse False."""
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
            c.execute('INSERT INTO games (player1_id, player2_id, winner_id, moves, end_reason, '
                      'tournament_id) VALUES (%s, %s, %s, %s, %s, %s)',
                      (ids[p1_username], ids[p2_username], winner_id, moves, end_reason,
                       tournament_id))
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


# =============================================================================
# ARENA TURNUVASI
# =============================================================================

_TOURNAMENT_COLS = ('t.id, u.username AS creator, t.duration_minutes, t.starts_at, t.ends_at, '
                    't.started_at, t.status, t.created_at, t.cheat_checked_at')
_TOURNAMENT_FROM = 'FROM tournaments t JOIN users u ON u.user_id = t.creator_id'


def create_tournament(creator_username: str, duration_minutes: int,
                      starts_at: datetime) -> Optional[int]:
    """Turnuva olusturur (bitis = baslangic + sure). Yaratici kayitli degilse None."""
    try:
        with get_db_cursor() as c:
            if not c:
                return None
            c.execute('SELECT user_id FROM users WHERE username = %s', (creator_username,))
            user = c.fetchone()
            if not user:
                return None
            ends_at = starts_at + timedelta(minutes=duration_minutes)
            c.execute('INSERT INTO tournaments (creator_id, duration_minutes, starts_at, ends_at, status) '
                      "VALUES (%s, %s, %s, %s, 'scheduled') RETURNING id",
                      (user['user_id'], duration_minutes, starts_at, ends_at))
            return c.fetchone()['id']
    except Exception as e:
        log.error("create_tournament hatasi: %s", e)
        return None


def get_tournament(tid: int) -> Optional[Dict[str, Any]]:
    """Tek turnuvayi dondurur; yoksa None."""
    try:
        with get_db_cursor() as c:
            if not c:
                return None
            c.execute(f'SELECT {_TOURNAMENT_COLS} {_TOURNAMENT_FROM} WHERE t.id = %s', (tid,))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception as e:
        log.error("get_tournament hatasi: %s", e)
        return None


def list_tournaments(now: datetime) -> List[Dict[str, Any]]:
    """Planli/suren turnuvalar ve son 7 gundeki bitenler (iptaller yok)."""
    try:
        with get_db_cursor() as c:
            if not c:
                return []
            c.execute(f"SELECT {_TOURNAMENT_COLS} {_TOURNAMENT_FROM} "
                      "WHERE t.status IN ('scheduled', 'running') "
                      "OR (t.status = 'finished' AND t.ends_at >= %s) "
                      'ORDER BY t.starts_at, t.id', (now - timedelta(days=7),))
            return [dict(row) for row in c.fetchall()]
    except Exception as e:
        log.error("list_tournaments hatasi: %s", e)
        return []


def active_tournament_of_creator(username: str) -> Optional[int]:
    """Kullanicinin planli/suren turnuvasinin id'si; yoksa None."""
    try:
        with get_db_cursor() as c:
            if not c:
                return None
            c.execute(f"SELECT t.id {_TOURNAMENT_FROM} "
                      "WHERE u.username = %s AND t.status IN ('scheduled', 'running') "
                      'ORDER BY t.id LIMIT 1', (username,))
            row = c.fetchone()
            return row['id'] if row else None
    except Exception as e:
        log.error("active_tournament_of_creator hatasi: %s", e)
        return None


def set_tournament_status(tid: int, status: str, started_at: Optional[datetime] = None,
                          ends_at: Optional[datetime] = None) -> bool:
    """Durumu gunceller; verilirse started_at / ends_at de yazilir."""
    try:
        with get_db_cursor() as c:
            if not c:
                return False
            c.execute('UPDATE tournaments SET status = %s, '
                      'started_at = COALESCE(%s, started_at), ends_at = COALESCE(%s, ends_at) '
                      'WHERE id = %s', (status, started_at, ends_at, tid))
            return c.rowcount > 0
    except Exception as e:
        log.error("set_tournament_status hatasi: %s", e)
        return False


def join_tournament(tid: int, username: str) -> bool:
    """Oyuncuyu turnuvaya ekler; zaten uyeyse duraklatmayi kaldirir. Basariliysa True."""
    try:
        with get_db_cursor() as c:
            if not c:
                return False
            c.execute('SELECT user_id FROM users WHERE username = %s', (username,))
            user = c.fetchone()
            if not user:
                return False
            c.execute('SELECT 1 FROM tournaments WHERE id = %s', (tid,))
            if not c.fetchone():
                return False
            c.execute('INSERT INTO tournament_players (tournament_id, user_id) VALUES (%s, %s) '
                      'ON CONFLICT (tournament_id, user_id) DO UPDATE SET paused = FALSE',
                      (tid, user['user_id']))
            return True
    except Exception as e:
        log.error("join_tournament hatasi: %s", e)
        return False


def set_player_paused(tid: int, username: str, paused: bool) -> bool:
    """Oyuncunun duraklatma bayragini ayarlar. Uye degilse False."""
    try:
        with get_db_cursor() as c:
            if not c:
                return False
            c.execute('UPDATE tournament_players SET paused = %s WHERE tournament_id = %s '
                      'AND user_id = (SELECT user_id FROM users WHERE username = %s)',
                      (paused, tid, username))
            return c.rowcount > 0
    except Exception as e:
        log.error("set_player_paused hatasi: %s", e)
        return False


def get_standings_rows(tid: int) -> List[Dict[str, Any]]:
    """Turnuva katilimcilari: puana gore azalan, esitlikte katilma sirasi."""
    try:
        with get_db_cursor() as c:
            if not c:
                return []
            c.execute('SELECT u.username, u.rating, p.score, p.games_played, p.streak, p.paused, p.recent '
                      'FROM tournament_players p JOIN users u ON u.user_id = p.user_id '
                      'WHERE p.tournament_id = %s '
                      'ORDER BY p.score DESC, p.joined_at, u.username', (tid,))
            rows = []
            for row in c.fetchall():
                item = dict(row)
                item['recent'] = item['recent'] or ''
                rows.append(item)
            return rows
    except Exception as e:
        log.error("get_standings_rows hatasi: %s", e)
        return []


def apply_tournament_result(tid: int, username: str, points: int, new_streak: int,
                            outcome: str) -> bool:
    """Oyuncunun puanini/serisini isler; son 5 sonuc dizesine outcome ('W','D','L') eklenir."""
    if outcome not in ('W', 'D', 'L'):
        return False
    try:
        with get_db_cursor() as c:
            if not c:
                return False
            c.execute('UPDATE tournament_players SET score = score + %s, '
                      'games_played = games_played + 1, streak = %s, '
                      "recent = RIGHT(COALESCE(recent, '') || %s, 5) "
                      'WHERE tournament_id = %s '
                      'AND user_id = (SELECT user_id FROM users WHERE username = %s)',
                      (points, new_streak, outcome, tid, username))
            return c.rowcount > 0
    except Exception as e:
        log.error("apply_tournament_result hatasi: %s", e)
        return False


def tournament_games(tid: int) -> List[Dict[str, Any]]:
    """Turnuvada oynanan oyunlar; moves bir tamsayi listesi olarak doner."""
    try:
        with get_db_cursor() as c:
            if not c:
                return []
            c.execute('SELECT g.game_id, g.moves, g.end_reason, '
                      'p1.username AS player1, p2.username AS player2, w.username AS winner '
                      'FROM games g '
                      'JOIN users p1 ON p1.user_id = g.player1_id '
                      'JOIN users p2 ON p2.user_id = g.player2_id '
                      'LEFT JOIN users w ON w.user_id = g.winner_id '
                      'WHERE g.tournament_id = %s ORDER BY g.game_id', (tid,))
            games = []
            for row in c.fetchall():
                game = dict(row)
                try:
                    game['moves'] = [int(m) for m in json.loads(row['moves'] or '[]')]
                except (ValueError, TypeError):
                    game['moves'] = []
                games.append(game)
            return games
    except Exception as e:
        log.error("tournament_games hatasi: %s", e)
        return []


def finished_unchecked_tournaments() -> List[int]:
    """Bitmis ama hile taramasi yapilmamis turnuvalarin id'leri."""
    try:
        with get_db_cursor() as c:
            if not c:
                return []
            c.execute("SELECT id FROM tournaments WHERE status = 'finished' "
                      'AND cheat_checked_at IS NULL ORDER BY id')
            return [row['id'] for row in c.fetchall()]
    except Exception as e:
        log.error("finished_unchecked_tournaments hatasi: %s", e)
        return []


def mark_cheat_checked(tid: int) -> bool:
    """Turnuvayi hile taramasi yapildi diye isaretler."""
    try:
        with get_db_cursor() as c:
            if not c:
                return False
            c.execute('UPDATE tournaments SET cheat_checked_at = now() WHERE id = %s', (tid,))
            return c.rowcount > 0
    except Exception as e:
        log.error("mark_cheat_checked hatasi: %s", e)
        return False


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
            # Turnuva satirlari once (FK sirasi): oyuncu kayitlari, sonra yaratici olduklari turnuvalar
            c.execute('SELECT id FROM tournaments WHERE creator_id = ANY(%s)', (ids,))
            tids = [row['id'] for row in c.fetchall()]
            c.execute('DELETE FROM tournament_players WHERE user_id = ANY(%s) OR tournament_id = ANY(%s)',
                      (ids, tids))
            c.execute('UPDATE games SET tournament_id = NULL WHERE tournament_id = ANY(%s)', (tids,))
            c.execute('DELETE FROM tournaments WHERE id = ANY(%s)', (tids,))
            c.execute('DELETE FROM games WHERE player1_id = ANY(%s) OR player2_id = ANY(%s)', (ids, ids))
            c.execute('DELETE FROM users WHERE user_id = ANY(%s)', (ids,))
            log.info("%d test kullanicisi silindi", len(ids))
            return len(ids)
    except Exception as e:
        log.error("delete_test_users hatasi: %s", e)
        return 0


if __name__ == "__main__":
    init_db()
