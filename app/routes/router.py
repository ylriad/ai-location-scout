"""
API Routes
==========

/health               – liveness probe
/register             – register a new account (POST)
/login                – authenticate credentials (POST)
/logout               – end active session (POST)
/me                   – get current user info (GET)
/scout                – main agent endpoint (POST)
/scout/personal       – personal search flow (POST)
/tools/traffic        – get foot-traffic score
/tools/competitors    – get nearby competitors
/tools/rent           – get rent estimate
/tools/score          – score location
/tools/krisha         – scrape listings from krisha.kz
/tools/workers        – get candidate workers
/candidates           – list candidate locations for a city
"""

import logging
import sqlite3
import uuid

from fastapi import APIRouter, HTTPException, Query, Request, Response

from app.agent         import LocationScoutAgent
from app.models.schemas import (
    ScoutRequest, ScoutResult, HealthResponse,
    TrafficRequest, CompetitorRequest, RentRequest, ScoringRequest, KrishaRequest, WorkersRequest,
    RegisterRequest, LoginRequest, PersonalScoutRequest, PersonalScoutResult
)
from app.tools import (
    get_traffic_score,
    get_nearby_competitors,
    get_rent_estimate,
    score_location,
    scrape_krisha_listings,
)
from app.agent.candidates import ALMATY_CANDIDATES
from app.db import (
    get_db_connection,
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    register_search,
    get_search_count,
    COOKIE_NAME,
    VISITOR_COOKIE_NAME
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Health ────────────────────────────────────────────────────────────────────

@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["System"],
    summary="Liveness probe",
)
async def health():
    return HealthResponse()


# ── Auth Endpoints ────────────────────────────────────────────────────────────

@router.post(
    "/register",
    tags=["Auth"],
    summary="Register a new user account",
)
async def register(request: RegisterRequest, response: Response):
    conn = get_db_connection()
    try:
        # Check if email is already registered
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (request.email.strip().lower(),)).fetchone()
        if existing:
            raise HTTPException(status_code=400, detail="Email is already registered.")
            
        password_hash = hash_password(request.password)
        conn.execute(
            "INSERT INTO users (name, phone_number, email, password_hash, consent) VALUES (?, ?, ?, ?, ?)",
            (
                request.name.strip(),
                request.phone_number.strip(),
                request.email.strip().lower(),
                password_hash,
                1 if request.consent else 0
            )
        )
        conn.commit()
        
        # Automatically log the user in after registration
        token = create_access_token(request.email.strip().lower())
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=604800, # 7 days
            httponly=True,
            samesite="lax"
        )
        return {"status": "ok", "email": request.email.strip().lower(), "name": request.name.strip()}
    except sqlite3.IntegrityError:
        raise HTTPException(status_code=400, detail="Email is already registered.")
    finally:
        conn.close()


@router.post(
    "/login",
    tags=["Auth"],
    summary="Sign in to an existing account",
)
async def login(request: LoginRequest, response: Response):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE email = ?", (request.email.strip().lower(),)).fetchone()
    conn.close()
    
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")
        
    token = create_access_token(user["email"])
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=604800, # 7 days
        httponly=True,
        samesite="lax"
    )
    return {"status": "ok", "email": user["email"], "name": user["name"]}


@router.post(
    "/logout",
    tags=["Auth"],
    summary="Sign out of the current session",
)
async def logout(response: Response):
    response.delete_cookie(COOKIE_NAME)
    return {"status": "ok"}


@router.get(
    "/me",
    tags=["Auth"],
    summary="Get current user details",
)
async def get_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    return {
        "email": user["email"],
        "name": user["name"],
        "phone_number": user["phone_number"]
    }


# ── Main Scout Endpoints ──────────────────────────────────────────────────────

@router.post(
    "/scout",
    response_model=ScoutResult,
    tags=["Scout"],
    summary="Run the full business location-scout agent",
    response_description="Top-N ranked locations with scores, ROI estimates, and a narrative report.",
)
async def scout(request: ScoutRequest, req: Request, response: Response):
    # Check auth status to gate demo access
    user = get_current_user(req)
    is_demo = user is None
    
    if is_demo:
        visitor_id = req.cookies.get(VISITOR_COOKIE_NAME)
        if not visitor_id:
            visitor_id = str(uuid.uuid4())
            response.set_cookie(VISITOR_COOKIE_NAME, visitor_id, max_age=31536000, httponly=True)
            
        ip = req.client.host if req.client else "unknown"
        search_count = get_search_count(ip, visitor_id)
        if search_count >= 1:
            raise HTTPException(status_code=403, detail="Demo search limit reached. Please register or sign in.")
            
        register_search(ip, visitor_id)
        
    try:
        agent = LocationScoutAgent(top_n=request.top_n)
        result = await agent.run(request, is_demo=is_demo)
        return result
    except Exception as exc:
        logger.exception("Scout agent failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/scout/personal",
    response_model=PersonalScoutResult,
    tags=["Scout"],
    summary="Run the personal apartment-scout agent",
    response_description="Top-N ranked apartments near your university/destination.",
)
async def scout_personal(request: PersonalScoutRequest, req: Request, response: Response):
    # Check auth status to gate demo access
    user = get_current_user(req)
    is_demo = user is None
    
    if is_demo:
        visitor_id = req.cookies.get(VISITOR_COOKIE_NAME)
        if not visitor_id:
            visitor_id = str(uuid.uuid4())
            response.set_cookie(VISITOR_COOKIE_NAME, visitor_id, max_age=31536000, httponly=True)
            
        ip = req.client.host if req.client else "unknown"
        search_count = get_search_count(ip, visitor_id)
        if search_count >= 1:
            raise HTTPException(status_code=403, detail="Demo search limit reached. Please register or sign in.")
            
        register_search(ip, visitor_id)
        
    try:
        from app.agent.personal_agent import PersonalScoutAgent
        agent = PersonalScoutAgent(top_n=request.top_n)
        result = await agent.run(request, is_demo=is_demo)
        return result
    except Exception as exc:
        logger.exception("Personal scout agent failed: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc))


# ── Individual Tool Endpoints ─────────────────────────────────────────────────

@router.post(
    "/tools/traffic",
    tags=["Tools"],
    summary="Get foot-traffic score for a coordinate",
)
async def tool_traffic(req: TrafficRequest):
    try:
        return await get_traffic_score(req.lat, req.lng)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/tools/competitors",
    tags=["Tools"],
    summary="Find nearby competitors via OpenStreetMap",
)
async def tool_competitors(req: CompetitorRequest):
    try:
        return await get_nearby_competitors(req.lat, req.lng, req.business_type, req.radius)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/tools/rent",
    tags=["Tools"],
    summary="Estimate monthly rent for an address",
)
async def tool_rent(req: RentRequest):
    try:
        return await get_rent_estimate(req.address, req.business_type, req.monthly_budget)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/tools/score",
    tags=["Tools"],
    summary="Score a location from pre-computed sub-scores",
)
async def tool_score(req: ScoringRequest):
    try:
        factors = req.model_dump()
        return await score_location(factors)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/tools/krisha",
    tags=["Tools"],
    summary="Scrape real commercial listings from krisha.kz",
)
async def tool_krisha(req: KrishaRequest):
    try:
        return await scrape_krisha_listings(req.city, req.business_type, req.limit, req.area_size)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/tools/workers",
    tags=["Tools"],
    summary="Get candidate workers",
)
async def tool_workers(req: WorkersRequest):
    try:
        from app.tools.workers import get_workers
        return await get_workers(req.business_type, req.city)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Candidates Listing ────────────────────────────────────────────────────────

@router.get(
    "/candidates",
    tags=["Scout"],
    summary="List candidate locations for a city",
)
async def candidates(
    city: str = Query(default="Almaty", description="City name"),
):
    key = city.lower().strip()
    if key == "almaty":
        return {"city": city, "count": len(ALMATY_CANDIDATES), "candidates": ALMATY_CANDIDATES}
    raise HTTPException(
        status_code=404,
        detail=f"No candidates configured for city '{city}'. Currently supported: Almaty",
    )
