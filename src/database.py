# =============================================================================
# MODULE: database.py
# =============================================================================

import os
import hashlib
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor

# DATABASE URL
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@localhost/connect4")

# GLOBAL CONNECTION POOL
# Min 1, Max 10.
try:
    pg_pool = psycopg2.pool.ThreadedConnectionPool(1, 10, dsn=DB_URL)
    print("[DATABASE] Connection Pool created.")
except Exception as e:
    print(f"[DATABASE ERROR] Pool creation failed: {e}")
    pg_pool = None

@contextmanager
def get_db_cursor():
    """Context manager for safe connection handling."""
    conn = None
    try:
        conn = pg_pool.getconn()
        conn.autocommit = True
        yield conn.cursor(cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"[DB ERROR] {e}")
        if conn: conn.rollback()
    finally:
        if conn:
            pg_pool.putconn(conn)

def init_db() -> None:
    try:
        with get_db_cursor() as c:
            if c:
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
                print("[DATABASE] Schema verified.")
    except Exception as e:
        print(f"[INIT ERROR] {e}")

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def create_user(username: str, password: str, email: str = "") -> Optional[int]:
    try:
        with get_db_cursor() as c:
            if not c: return None
            pwd_hash = hash_password(password)
            c.execute('INSERT INTO users (username, password_hash, email) VALUES (%s, %s, %s) RETURNING user_id', 
                      (username, pwd_hash, email))
            return c.fetchone()['user_id']
    except psycopg2.IntegrityError:
        return None 
    except Exception:
        return None

def verify_user(username: str, password: str) -> Optional[Dict[str, Any]]:
    try:
        with get_db_cursor() as c:
            if not c: return None
            pwd_hash = hash_password(password)
            c.execute('SELECT user_id, username, rating, wins, losses FROM users WHERE username = %s AND password_hash = %s', 
                         (username, pwd_hash))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception:
        return None

def get_top_players(limit: int = 10) -> List[Dict[str, Any]]:
    try:
        with get_db_cursor() as c:
            if not c: return []
            c.execute('SELECT username, rating, wins, losses FROM users ORDER BY rating DESC LIMIT %s', (limit,))
            return [dict(row) for row in c.fetchall()]
    except Exception:
        return []

def update_game_result(p1_id: int, p2_id: int, winner_id: Optional[int], moves: str) -> None:
    try:
        with get_db_cursor() as c:
            if not c: return
            c.execute('INSERT INTO games (player1_id, player2_id, winner_id, moves) VALUES (%s, %s, %s, %s)',
                      (p1_id, p2_id, winner_id, moves))
            if winner_id:
                loser_id = p1_id if winner_id == p2_id else p2_id
                c.execute('UPDATE users SET rating = rating + 15, wins = wins + 1 WHERE user_id = %s', (winner_id,))
                c.execute('UPDATE users SET rating = rating - 15, losses = losses + 1 WHERE user_id = %s', (loser_id,))
    except Exception:
        pass

if __name__ == "__main__":
    init_db()