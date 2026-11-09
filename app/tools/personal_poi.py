import logging
import httpx
import asyncio
import math
from typing import Tuple, Dict, Any
from app.tools.google_maps import get_api_key

logger = logging.getLogger(__name__)

# Fallback coordinates for popular Almaty landmarks to guarantee robust operation
LANDMARK_COORDINATES = {
    "kbtu": (43.2558, 76.9423),
    "kaznu": (43.2241, 76.9272),
    "satbayev": (43.2382, 76.9155),
    "uib": (43.2427, 76.9536),
    "malls": (43.2390, 76.9100),
    "panfilov": (43.2607, 76.9467)
}

async def geocode_destination(destination: str) -> Tuple[float, float]:
    """Geocodes destination name or address. Returns (lat, lon)."""
    dest_clean = destination.lower().strip()
    
    # Check exact matching fallbacks first to support offline/local testing
    for key, coords in LANDMARK_COORDINATES.items():
        if key in dest_clean:
            return coords
            
    # Try 2GIS geocoding
    from app.tools.google_maps import geocode_city
    loc = await geocode_city(destination if "алматы" in dest_clean or "almaty" in dest_clean else f"Алматы, {destination}")
    if loc:
        return loc

    # Fallback default: Almaty Center (KBTU)
    return LANDMARK_COORDINATES["kbtu"]

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates distance between two points in km."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 + 
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

async def get_poi_count(lat: float, lng: float, query: str) -> int | None:
    """Number of 2GIS objects matching `query` within 1 km, or None if 2GIS is unavailable."""
    from app.tools.google_maps import twogis_items
    res = await twogis_items({"point": f"{lng},{lat}", "radius": 1000, "q": query, "page_size": 1})
    if res is None:
        return None
    return int(res.get("total", 0) or 0)


async def get_personal_scores(lat: float, lng: float) -> Dict[str, float | None]:
    """Convenience, safety and lifestyle scores (0–100). None = no 2GIS data (agent uses an average)."""
    conv_cnt, safe_cnt, ent_cnt = await asyncio.gather(
        get_poi_count(lat, lng, "аптека, магазин, школа, детский сад"),
        get_poi_count(lat, lng, "детская площадка, полиция, общественные организации"),
        get_poi_count(lat, lng, "кафе, ресторан, парк, развлечения"),
    )

    def scale(cnt, mult, floor):
        return None if cnt is None else round(min(100.0, max(floor, cnt * mult)), 1)

    return {
        "convenience_score": scale(conv_cnt, 6.5, 40.0),
        "safety_score":      scale(safe_cnt, 12.0, 45.0),
        "lifestyle_score":   scale(ent_cnt, 5.0, 35.0),
    }
