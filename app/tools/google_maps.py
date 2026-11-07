import logging
import httpx
import asyncio
import os
from typing import Dict, Any, List, Tuple

logger = logging.getLogger(__name__)

def get_api_key() -> str:
    """2GIS API key from the TWOGIS_API_KEY environment variable (never hardcode it)."""
    return os.getenv("TWOGIS_API_KEY", "").strip()

async def geocode_city(city: str) -> Tuple[float, float] | None:
    """Geocodes a city/address string to coordinates using 2GIS."""
    key = get_api_key()
    if not key:
        return None
        
    url = "https://catalog.api.2gis.com/3.0/items"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params={"q": city, "key": key, "fields": "items.point"})
            if resp.status_code == 200:
                data = resp.json()
                if "result" in data and data["result"].get("items"):
                    loc = data["result"]["items"][0].get("point")
                    if loc:
                        return loc["lat"], loc["lon"]
    except Exception as e:
        logger.error(f"Geocoding error: {e}")
    return None

async def get_competitors(lat: float, lng: float, keyword: str, radius: int = 1000) -> Dict[str, Any]:
    """Finds competitors using 2GIS API."""
    key = get_api_key()
    
    result = {
        "count": -1,
        "competitors": [],
        "competitor_gap": 50.0,
        "radius_m": radius,
        "explanation": "2GIS API Key required to run active competitor proximity gap analyses."
    }
    
    if not key:
        return result
        
    url = "https://catalog.api.2gis.com/3.0/items"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # 2GIS API takes lon,lat for point parameter
            resp = await client.get(
                url,
                params={
                    "point": f"{lng},{lat}",
                    "radius": radius,
                    "q": keyword,
                    "fields": "items.point",
                    "key": key
                }
            )
            
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result", {})
                count = res.get("total", 0)
                items = res.get("items", [])
                
                competitors = []
                for p in items[:20]:
                    competitors.append({
                        "name": p.get("name", "Unknown"),
                        "lat": p.get("point", {}).get("lat"),
                        "lng": p.get("point", {}).get("lon"),
                        "rating": (p.get("reviews") or {}).get("general_review_count", 0)
                    })
                
                # Adjust score roughly
                gap_score = round(max(0, 100 - count * 5), 2)
                
                result = {
                    "count": count,
                    "competitors": competitors,
                    "competitor_gap": gap_score,
                    "radius_m": radius,
                    "source": "2GIS API",
                    "explanation": f"2GIS found {count} '{keyword}' competitors within {radius}m. Competitor gap score: {gap_score}/100."
                }
            else:
                logger.error(f"2GIS API failed: {resp.status_code}")
                
    except Exception as e:
        logger.error(f"2GIS API Error: {e}")
        
    return result

async def get_foot_traffic_proxy(lat: float, lng: float, radius: int = 400) -> Dict[str, Any]:
    """
    Since we use 2GIS now, we proxy foot-traffic density by querying all branches 
    in the direct vicinity and aggregating their count and reviews.
    """
    key = get_api_key()
    
    result = {
        "score": 50.0,
        "source": "Fallback Synthetic Traffic Model",
        "explanation": "Could not access 2GIS API."
    }
    
    if not key:
        return result
        
    url = "https://catalog.api.2gis.com/3.0/items"
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Query general branches around the point
            resp = await client.get(
                url,
                params={
                    "point": f"{lng},{lat}",
                    "radius": radius,
                    "type": "branch",
                    "key": key
                }
            )
            
            if resp.status_code == 200:
                data = resp.json()
                res = data.get("result", {})
                total_pois = res.get("total", 0)
                
                # Normalize score based on POIs: 
                # ~150 POIs nearby is decent (50 score)
                # ~350+ is excellent (100 score)
                score = min(100.0, max(0.0, total_pois / 3.5))
                
                result = {
                    "score": round(score, 1),
                    "source": "2GIS API Proxied Traffic (branch density)",
                    "explanation": f"Found {total_pois} registered branches/establishments nearby. Higher branch density maps to higher physical traffic. Proxy score: {round(score, 1)}/100."
                }
            else:
                logger.error(f"2GIS proxy search failed: {resp.text}")
                
    except Exception as e:
        logger.error(f"2GIS Traffic parsing error: {e}")

    return result
