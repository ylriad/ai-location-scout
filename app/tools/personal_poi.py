import logging
import httpx
import asyncio
import hashlib
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
    key = get_api_key()
    if key:
        url = "https://catalog.api.2gis.com/3.0/items"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url, params={"q": destination, "key": key, "fields": "items.point"})
                if resp.status_code == 200:
                    data = resp.json()
                    if "result" in data and data["result"].get("items"):
                        loc = data["result"]["items"][0].get("point")
                        if loc:
                            return float(loc["lat"]), float(loc["lon"])
        except Exception as e:
            logger.error(f"Error geocoding destination '{destination}': {e}")
            
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

async def get_poi_count(lat: float, lng: float, query: str) -> int:
    """Queries 2GIS for the count of a POI rubric or keyword around a point."""
    key = get_api_key()
    if not key:
        # Stable deterministic mock count based on coords + query hash
        h = int(hashlib.md5(f"{query}-{lat}-{lng}".encode("utf-8")).hexdigest(), 16)
        return (h % 15) + 3
        
    url = "https://catalog.api.2gis.com/3.0/items"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                url,
                params={
                    "point": f"{lng},{lat}",
                    "radius": 1000,
                    "q": query,
                    "key": key
                }
            )
            if resp.status_code == 200:
                return resp.json().get("result", {}).get("total", 0)
    except Exception as e:
        logger.error(f"Error fetching POI count for '{query}': {e}")
    return 5

async def get_personal_scores(lat: float, lng: float) -> Dict[str, float]:
    """Calculates Safety, Convenience, and Entertainment scores."""
    # Gather counts in parallel
    conv_task = get_poi_count(lat, lng, "аптека, магазин, школа, детский сад")
    safe_task = get_poi_count(lat, lng, "детская площадка, полиция, общественные организации")
    ent_task = get_poi_count(lat, lng, "кафе, ресторан, парк, развлечения")
    
    conv_cnt, safe_cnt, ent_cnt = await asyncio.gather(conv_task, safe_task, ent_task)
    
    # Map raw counts to 0-100 scales
    conv_score = min(100.0, max(40.0, conv_cnt * 6.5))
    safe_score = min(100.0, max(45.0, safe_cnt * 12.0))
    ent_score = min(100.0, max(35.0, ent_cnt * 5.0))
    
    return {
        "convenience_score": round(conv_score, 1),
        "safety_score": round(safe_score, 1),
        "lifestyle_score": round(ent_score, 1)
    }
