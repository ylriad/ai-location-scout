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
