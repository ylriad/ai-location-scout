import pytest
import sqlite3
from unittest.mock import patch
from app.db import (
    init_db, get_db_connection, hash_password, verify_password,
    create_access_token, register_search, get_search_count
)
from app.agent.personal_agent import PersonalScoutAgent
from app.models.schemas import PersonalScoutRequest

@pytest.fixture(autouse=True)
def temp_db(monkeypatch, tmp_path):
    """Overrides the DB path to a temporary database for testing."""
    test_db = tmp_path / "test_location_scout.db"
    monkeypatch.setattr("app.db.DB_PATH", test_db)
    init_db()
    yield
    if test_db.exists():
        test_db.unlink()

def test_password_hashing():
    pwd = "my-secure-password"
    h = hash_password(pwd)
    assert h != pwd
    assert verify_password(pwd, h)
    assert not verify_password("wrong-password", h)

def test_user_registration_and_auth():
    conn = get_db_connection()
    # Insert user
    email = "student@kbtu.kz"
    pwd_hash = hash_password("pass123")
    conn.execute(
        "INSERT INTO users (name, phone_number, email, password_hash, consent) VALUES (?, ?, ?, ?, ?)",
        ("Aliya", "+77071112233", email, pwd_hash, 1)
    )
    conn.commit()
    
    # Retrieve user
    user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    assert user is not None
    assert user["name"] == "Aliya"
    assert verify_password("pass123", user["password_hash"])
    
    # Duplicate email violation
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO users (name, phone_number, email, password_hash, consent) VALUES (?, ?, ?, ?, ?)",
            ("Duplicate", "+77070000000", email, pwd_hash, 1)
        )
        conn.commit()
    conn.close()

def test_demo_search_logging():
    ip = "127.0.0.1"
    cookie = "visitor-123"
    
    assert get_search_count(ip, cookie) == 0
    
    register_search(ip, cookie)
    assert get_search_count(ip, cookie) == 1
    
    # Verification with just IP fallback
    assert get_search_count(ip, None) == 1

@pytest.mark.asyncio
async def test_personal_scout_full_vs_demo():
    request = PersonalScoutRequest(
        rent_or_buy="rent",
        destination="KBTU, Almaty",
        price_min=150000,
        price_max=400000,
        city="Almaty",
        area_size=50,
        top_n=2
    )
    agent = PersonalScoutAgent(top_n=2)
    
    # Full search (authenticated)
    res_full = await agent.run(request, is_demo=False)
    assert len(res_full.top_locations) > 0
    loc_full = res_full.top_locations[0]
    assert loc_full.convenience_score != "locked"
    assert loc_full.safety_score != "locked"
    assert loc_full.lifestyle_score != "locked"
    assert loc_full.avg_rent_kzt != "locked"
    assert "2gis.ru/routeSearch" in loc_full.directions_url
    
    # Demo search (anonymous)
    res_demo = await agent.run(request, is_demo=True)
    # Reduced to 1 property
    assert len(res_demo.top_locations) == 1
    loc_demo = res_demo.top_locations[0]
    assert loc_demo.convenience_score == "locked"
    assert loc_demo.safety_score == "locked"
    assert loc_demo.lifestyle_score == "locked"
    assert loc_demo.avg_rent_kzt == "locked"
    assert "2gis.ru/routeSearch" in loc_demo.directions_url
