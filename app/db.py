import sqlite3
import os
import bcrypt
import jwt
import datetime
import logging
from pathlib import Path
from fastapi import Request, Response

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "location_scout.db"
JWT_SECRET = os.getenv("JWT_SECRET", "super-secret-key-change-me-in-production-123456789")
JWT_ALGORITHM = "HS256"
COOKIE_NAME = "session_token"
VISITOR_COOKIE_NAME = "demo_visitor_id"

def init_db():
    """Initializes the database schema."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_number TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            consent INTEGER NOT NULL
        )
    """)
    
    # Search logs for tracking demo limit
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ip_address TEXT NOT NULL,
            cookie_id TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # User favorites table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            location_id TEXT NOT NULL,
            location_data TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, location_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """)
    
    conn.commit()
    conn.close()

def get_db_connection():
    init_db()
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn

# ── Password Hashing ──────────────────────────────────────────────────────────
def hash_password(password: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False

# ── Session & JWT ─────────────────────────────────────────────────────────────
def create_access_token(email: str) -> str:
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=7)
    payload = {
        "sub": email,
        "exp": expire
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def get_current_user(request: Request) -> dict | None:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        return None
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        email = payload.get("sub")
        if not email:
            return None
        
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        conn.close()
        if user:
            return dict(user)
    except jwt.PyJWTError:
        pass
    return None

# ── Search Limits (Demo Mode) ──────────────────────────────────────────────────
def register_search(ip_address: str, cookie_id: str | None) -> None:
    """Logs a search request in the database."""
    conn = get_db_connection()
    conn.execute(
        "INSERT INTO search_logs (ip_address, cookie_id) VALUES (?, ?)",
        (ip_address, cookie_id or "")
    )
    conn.commit()
    conn.close()

def get_search_count(ip_address: str, cookie_id: str | None) -> int:
    """Counts search logs for a given IP or cookie ID."""
    conn = get_db_connection()
    # Check if either matches to prevent client bypasses
    if cookie_id:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM search_logs WHERE ip_address = ? OR cookie_id = ?",
            (ip_address, cookie_id)
        ).fetchone()
    else:
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM search_logs WHERE ip_address = ?",
            (ip_address,)
        ).fetchone()
    conn.close()
    return row["cnt"] if row else 0


# ── User Favorites ────────────────────────────────────────────────────────────
def get_user_favorites(user_id: int) -> list[dict]:
    """Retrieves all saved favorites for a user."""
    conn = get_db_connection()
    rows = conn.execute(
        "SELECT location_id, location_data FROM favorites WHERE user_id = ? ORDER BY id DESC",
        (user_id,)
    ).fetchall()
    conn.close()
    import json
    favs = []
    for r in rows:
        try:
            data = json.loads(r["location_data"])
            favs.append(data)
        except Exception:
            pass
    return favs


def add_user_favorite(user_id: int, location_id: str, location_data: dict) -> None:
    """Saves a location to user's favorites."""
    import json
    conn = get_db_connection()
    conn.execute(
        "INSERT OR REPLACE INTO favorites (user_id, location_id, location_data) VALUES (?, ?, ?)",
        (user_id, str(location_id), json.dumps(location_data, ensure_ascii=False))
    )
    conn.commit()
    conn.close()


def remove_user_favorite(user_id: int, location_id: str) -> None:
    """Removes a location from user's favorites."""
    conn = get_db_connection()
    conn.execute(
        "DELETE FROM favorites WHERE user_id = ? AND location_id = ?",
        (user_id, str(location_id))
    )
    conn.commit()
    conn.close()
