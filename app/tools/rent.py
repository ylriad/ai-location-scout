"""
Tool: get_rent_estimate
Estimates monthly commercial rent (USD) for a given address.

Strategy (in priority order):
  1. Look up in a local CSV database (data/rent_data.csv) by district / zone.
  2. Fall back to a deterministic synthetic model when no CSV match is found.

The CSV format is:
  city, district, business_type, avg_rent_usd, min_rent_usd, max_rent_usd
"""

import csv
import logging
import os
import re
from pathlib import Path

from app.tools.krisha import scrape_krisha_listings

logger = logging.getLogger(__name__)

# Resolve path relative to project root so it works in any environment (local/Render)
DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
RENT_CSV  = DATA_DIR / "rent_data.csv"

# Almaty district → rough centre lat/lng for synthetic distance model
ALMATY_DISTRICTS: dict[str, tuple[float, float]] = {
    "Medeu":         (43.2565, 76.9285),
    "Bostandyq":     (43.2412, 76.8820),
    "Alatau":        (43.3200, 76.8500),
    "Almaly":        (43.2575, 76.9450),
    "Auezov":        (43.2200, 76.8700),
    "Zhetysу":       (43.2800, 76.9700),
    "Turksib":       (43.3100, 77.0200),
    "Nauryzbay":     (43.2000, 76.8000),
}

CBD_LAT, CBD_LNG = 43.2551, 76.9126

def _match_district(address: str) -> str | None:
    """Fuzzy-match one of the known district names inside an address string."""
    addr_lower = address.lower()
    for district in ALMATY_DISTRICTS:
        if district.lower() in addr_lower:
            return district
    return None

import asyncio
from datetime import datetime, timedelta

_KRISHA_CACHE = {}
_KRISHA_LOCK = asyncio.Lock()

async def _krisha_rent(address: str, business_type: str, area_size: int = 50) -> dict | None:
    district = _match_district(address) or "Unknown"
    cache_key = ("almaty", business_type, area_size)
    
    async with _KRISHA_LOCK:
        now = datetime.now()
        if cache_key in _KRISHA_CACHE and now - _KRISHA_CACHE[cache_key]["time"] < timedelta(minutes=10):
            listings = _KRISHA_CACHE[cache_key]["listings"]
        else:
            listings = await scrape_krisha_listings("almaty", business_type, limit=20, area_size=area_size)
            _KRISHA_CACHE[cache_key] = {"time": now, "listings": listings}
    
    valid_prices = []
    
    # First priority: matching district
    for l in listings:
        if l["price_kzt"] > 0 and district.lower() in l["address"].lower():
            valid_prices.append(l["price_kzt"])
            
    # Second priority: any prices found for this business type in Almaty
    if not valid_prices:
        valid_prices = [l["price_kzt"] for l in listings if l["price_kzt"] > 0]
        
    if not valid_prices:
        return None
        
    avg = sum(valid_prices) / len(valid_prices)
    
    return {
        "avg_rent_kzt": round(avg),
        "min_rent_kzt": round(min(valid_prices)),
        "max_rent_kzt": round(max(valid_prices)),
        "district":     district,
        "source":       "Krisha.kz",
    }

def _affordability_score(avg_rent: float, budget: float) -> float:
    if avg_rent <= 0: return 50.0
    ratio = avg_rent / budget
    score = max(0, 100 * (1 - ratio / 0.6))
    return round(score, 2)

async def get_rent_estimate(
    address:       str,
    business_type: str   = "coffee_shop",
    monthly_budget: float = 5_000_000,
    area_size: int = 50,
) -> dict:
    
    district = _match_district(address) or "Unknown"
    
    # 1. krisha.kz live real estate data ONLY
    krisha_res = await _krisha_rent(address, business_type, area_size)
    
    if krisha_res:
        result = krisha_res
    else:
        # Fallback to actual local CSV database data if scraper fails
        found_csv = False
        try:
            if RENT_CSV.exists():
                with open(RENT_CSV, "r", encoding="utf-8") as f:
                    # CSV format: city, district, business_type, avg_rent_usd, min_rent_usd, max_rent_usd
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Fallback business type matching
                        bt_match = business_type.lower() in row["business_type"].lower() or row["business_type"].lower() in business_type.lower()
                        if row["district"].lower() == district.lower() and bt_match:
                            avg_usd = float(row["avg_rent_usd"])
                            min_usd = float(row["min_rent_usd"])
                            max_usd = float(row["max_rent_usd"])
                            # KZT conversion roughly 500 KZT per USD, scale relative to 50 sqm baseline
                            scale = area_size / 50.0
                            result = {
                                "avg_rent_kzt": int(avg_usd * 500 * scale),
                                "min_rent_kzt": int(min_usd * 500 * scale),
                                "max_rent_kzt": int(max_usd * 500 * scale),
                                "district": district,
                                "source": "Local Statistical Database"
                            }
                            found_csv = True
                            break
        except Exception as e:
            logger.error(f"Error reading rent CSV: {e}")
            
        if not found_csv:
            # Absolute fallback if CSV doesn't match or fails
            scale = area_size / 50.0
            result = {
                "avg_rent_kzt": int(1500000 * scale),
                "min_rent_kzt": int(800000 * scale),
                "max_rent_kzt": int(3000000 * scale),
                "district": district,
                "source": "Generic Fallback Model"
            }

    afford = _affordability_score(result["avg_rent_kzt"], monthly_budget)
    result["rent_affordable"] = afford
    result["explanation"] = (
        f"Est. rent {result['avg_rent_kzt']} KZT/mo "
        f"(range {result['min_rent_kzt']}–{result['max_rent_kzt']} KZT/mo) "
        f"in {result['district']} district. "
        f"Affordability score: {afford}/100 "
        f"(budget: {monthly_budget} KZT/mo). Source: {result['source']}."
    )
    return result
