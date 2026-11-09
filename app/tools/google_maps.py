"""
2GIS Catalog API helpers (file name is historical – everything here is 2GIS).

Every function distinguishes three outcomes:
  * data found            → real numbers from 2GIS
  * nothing found         → 2GIS answered meta.code 404 → a real zero
  * no access / error     → value is None and source="unavailable";
                             the agent later substitutes an AVERAGE
                             (mean of the candidates that did get data,
                             or a neutral city default).
"""
import logging
import os
from typing import Any, Dict, Tuple

import httpx

logger = logging.getLogger(__name__)

TWOGIS_ITEMS_URL = "https://catalog.api.2gis.com/3.0/items"


def get_api_key() -> str:
    """2GIS API key from the TWOGIS_API_KEY environment variable (never hardcode it)."""
    return os.getenv("TWOGIS_API_KEY", "").strip()


async def twogis_items(params: dict, timeout: float = 10.0) -> dict | None:
    """
    Calls 2GIS /3.0/items. Returns the `result` dict (with total/items),
    an empty result for "nothing found" (meta.code 404), or None when the
    key is missing, invalid, out of quota, or the request failed.
    """
    key = get_api_key()
    if not key:
        return None
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(TWOGIS_ITEMS_URL, params={**params, "key": key})
        data = resp.json() if resp.content else {}
    except Exception as e:
        logger.warning("2GIS request failed: %r", e)
        return None

    code = (data.get("meta") or {}).get("code", resp.status_code)
    if code == 200:
        return data.get("result") or {"total": 0, "items": []}
    if code == 404:  # 2GIS uses 404 for "no results"
        return {"total": 0, "items": []}
    logger.warning("2GIS error %s: %s", code, (data.get("meta") or {}).get("error"))
    return None


async def geocode_city(city: str) -> Tuple[float, float] | None:
    """Geocodes a city/address string to coordinates using 2GIS."""
    res = await twogis_items({"q": city, "fields": "items.point"})
    if res and res.get("items"):
        loc = res["items"][0].get("point")
        if loc:
            return float(loc["lat"]), float(loc["lon"])
    return None


async def get_competitors(lat: float, lng: float, keyword: str, radius: int = 1000) -> Dict[str, Any]:
    """Counts businesses of the same type around the point (2GIS search)."""
    res = await twogis_items({
        "point": f"{lng},{lat}",       # 2GIS takes lon,lat
        "radius": radius,
        "q": keyword,
        "fields": "items.point,items.reviews",
        "page_size": 10,
    }, timeout=15.0)

    if res is None:
        return {
            "count": None,
            "competitors": [],
            "competitor_gap": None,
            "radius_m": radius,
            "source": "unavailable",
            "explanation": "2GIS data unavailable – an average value is used.",
        }

    count = int(res.get("total", 0) or 0)
    competitors = [{
        "name": p.get("name", "Unknown"),
        "lat": (p.get("point") or {}).get("lat"),
        "lng": (p.get("point") or {}).get("lon"),
        "rating": (p.get("reviews") or {}).get("general_review_count", 0),
    } for p in (res.get("items") or [])[:10]]

    gap_score = round(max(0.0, 100.0 - count * 5), 2)
    return {
        "count": count,
        "competitors": competitors,
        "competitor_gap": gap_score,
        "radius_m": radius,
        "source": "2GIS API",
        "explanation": f"2GIS found {count} '{keyword}' businesses within {radius} m. Competitor gap score: {gap_score}/100.",
    }


async def get_foot_traffic_proxy(lat: float, lng: float, radius: int = 400) -> Dict[str, Any]:
    """
    Proxy for foot traffic: number of organisations (branches) registered in
    2GIS within `radius` metres. 350+ organisations → 100 points.
    """
    res = await twogis_items({
        "point": f"{lng},{lat}",
        "radius": radius,
        "type": "branch",
        "page_size": 1,
    }, timeout=15.0)

    if res is None:
        return {
            "score": None,
            "poi_count": None,
            "source": "unavailable",
            "explanation": "2GIS data unavailable – an average value is used.",
        }

    total_pois = int(res.get("total", 0) or 0)
    score = round(min(100.0, max(0.0, total_pois / 3.5)), 1)
    return {
        "score": score,
        "poi_count": total_pois,
        "source": "2GIS API (organisation density)",
        "explanation": f"{total_pois} organisations within {radius} m in 2GIS. Traffic proxy score: {score}/100.",
    }
