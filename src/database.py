# =============================================================================
# MODULE: database.py
# Connect Four Pro - Database Layer with PostgreSQL
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
        if pg_pool is None:
            yield None
            return
        conn = pg_pool.getconn()
        conn.autocommit = True
        yield conn.cursor(cursor_factory=RealDictCursor)
    except Exception as e:
        print(f"[DB ERROR] {e}")
        if conn: 
            conn.rollback()
        yield None
    finally:
        if conn and pg_pool:
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

def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """Get user by username"""
    try:
        with get_db_cursor() as c:
            if not c: return None
            c.execute('SELECT user_id, username, rating, wins, losses FROM users WHERE username = %s', (username,))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception:
        return None

def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by user_id"""
    try:
        with get_db_cursor() as c:
            if not c: return None
            c.execute('SELECT user_id, username, rating, wins, losses FROM users WHERE user_id = %s', (user_id,))
            row = c.fetchone()
            return dict(row) if row else None
    except Exception:
        return None

def get_top_players(limit: int = 10) -> List[Dict[str, Any]]:
    try:
        with get_db_cursor() as c:
            if not c: return []
            c.execute('SELECT user_id, username, rating, wins, losses FROM users ORDER BY rating DESC LIMIT %s', (limit,))
            return [dict(row) for row in c.fetchall()]
    except Exception:
        return []

def update_elo_by_username(winner_username: str, loser_username: str, k_factor: int = 30) -> Dict[str, int]:
    """
    Update ELO ratings by username.
    Returns dict with 'winner_change' and 'loser_change'.
    """
    try:
        with get_db_cursor() as c:
            if not c: 
                return {'winner_change': 0, 'loser_change': 0}
            
            # Get current ratings
            c.execute('SELECT user_id, rating FROM users WHERE username = %s', (winner_username,))
            winner = c.fetchone()
            
            c.execute('SELECT user_id, rating FROM users WHERE username = %s', (loser_username,))
            loser = c.fetchone()
            
            if not winner or not loser:
                print(f"[ELO] User not found: winner={winner_username}, loser={loser_username}")
                return {'winner_change': 0, 'loser_change': 0}
            
            winner_rating = winner['rating']
            loser_rating = loser['rating']
            
            # Calculate ELO change
            expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
            change = int(k_factor * (1 - expected_winner))
            change = max(change, 10)  # Minimum 10 points
            
            # Update ratings
            c.execute('UPDATE users SET rating = rating + %s, wins = wins + 1 WHERE user_id = %s', 
                     (change, winner['user_id']))
            c.execute('UPDATE users SET rating = rating - %s, losses = losses + 1 WHERE user_id = %s', 
                     (change, loser['user_id']))
            
            print(f"[ELO] {winner_username} +{change}, {loser_username} -{change}")
            
            return {'winner_change': change, 'loser_change': -change}
    except Exception as e:
        print(f"[ELO ERROR] {e}")
        return {'winner_change': 0, 'loser_change': 0}

def record_game(p1_username: str, p2_username: str, winner_username: Optional[str], moves: str) -> bool:
    """Record a game with usernames"""
    try:
        with get_db_cursor() as c:
            if not c: return False
            
            # Get user IDs
            c.execute('SELECT user_id FROM users WHERE username = %s', (p1_username,))
            p1 = c.fetchone()
            
            c.execute('SELECT user_id FROM users WHERE username = %s', (p2_username,))
            p2 = c.fetchone()
            
            if not p1 or not p2:
                return False
            
            winner_id = None
            if winner_username:
                c.execute('SELECT user_id FROM users WHERE username = %s', (winner_username,))
                winner = c.fetchone()
                if winner:
                    winner_id = winner['user_id']
            
            c.execute('INSERT INTO games (player1_id, player2_id, winner_id, moves) VALUES (%s, %s, %s, %s)',
                      (p1['user_id'], p2['user_id'], winner_id, moves))
            return True
    except Exception as e:
        print(f"[GAME RECORD ERROR] {e}")
        return False

def update_game_result(p1_id, p2_id, winner_id, moves: str) -> None:
    """Legacy function - works with both user_id (int) and username (str)"""
    try:
        # Check if these are usernames or IDs
        if isinstance(p1_id, str) and not p1_id.isdigit():
            # These are usernames
            winner_username = winner_id if winner_id else None
            loser_username = p1_id if winner_id == p2_id else p2_id
            
            if winner_username and loser_username:
                update_elo_by_username(winner_username, loser_username)
            record_game(p1_id, p2_id, winner_username, moves)
        else:
            # These are user IDs (legacy behavior)
            with get_db_cursor() as c:
                if not c: return
                c.execute('INSERT INTO games (player1_id, player2_id, winner_id, moves) VALUES (%s, %s, %s, %s)',
                          (p1_id, p2_id, winner_id, moves))
                if winner_id:
                    loser_id = p1_id if winner_id == p2_id else p2_id
                    c.execute('UPDATE users SET rating = rating + 15, wins = wins + 1 WHERE user_id = %s', (winner_id,))
                    c.execute('UPDATE users SET rating = rating - 15, losses = losses + 1 WHERE user_id = %s', (loser_id,))
    except Exception as e:
        print(f"[UPDATE RESULT ERROR] {e}")

def delete_test_users() -> int:
    """Delete all test users created by Locust load testing"""
    try:
        with get_db_cursor() as c:
            if not c: return 0
            c.execute('''
                DELETE FROM games 
                WHERE player1_id IN (SELECT user_id FROM users WHERE username LIKE 'locust_user_%%' OR username LIKE 'test_user_%%' OR username LIKE 'user_%%')
                OR player2_id IN (SELECT user_id FROM users WHERE username LIKE 'locust_user_%%' OR username LIKE 'test_user_%%' OR username LIKE 'user_%%')
            ''')
            c.execute('''
                DELETE FROM users 
                WHERE username LIKE 'locust_user_%%' 
                OR username LIKE 'test_user_%%' 
                OR username LIKE 'user_%%'
            ''')
            deleted = c.rowcount
            print(f"[DATABASE] Deleted {deleted} test users")
            return deleted
    except Exception as e:
        print(f"[DATABASE ERROR] Failed to delete test users: {e}")
        return 0

def get_user_count() -> int:
    """Get total user count"""
    try:
        with get_db_cursor() as c:
            if not c: return 0
            c.execute('SELECT COUNT(*) as count FROM users')
            return c.fetchone()['count']
    except Exception:
        return 0

if __name__ == "__main__":
    init_db()