"""
LocationScoutAgent
==================
Orchestrates the five tools to evaluate candidate locations and return
the top-N ranked results with a human-readable report.

Flow
----
1. Select candidate locations for the requested city.
2. For each candidate (concurrently):
   a. get_traffic_score(lat, lng)
   b. get_nearby_competitors(lat, lng, business_type)
   c. get_rent_estimate(address, business_type, budget)
3. For each candidate: score_location(factors)
4. Sort by final_score, take top-N.
5. generate_report(top_N, …)
6. Return structured ScoutResult.
"""

import asyncio
import logging
from typing import Any

from app.tools.google_maps import get_competitors, get_foot_traffic_proxy, geocode_city
from app.tools.census_data import get_demographics
import httpx

from app.models.schemas import ScoutRequest, LocationResult, ScoutResult

logger = logging.getLogger(__name__)

DEFAULT_TOP_N = 3


# ---------------------------------------------------------------------------
# Core helper: evaluate a single candidate
# ---------------------------------------------------------------------------

async def _evaluate_candidate(
    candidate:       dict,
    business_type:   str,
    budget:          float,
    area_size:       int,
) -> dict:
    """Runs the three data-gathering tools concurrently for one location."""
    lat = candidate.get("lat", 0)
    lng = candidate.get("lng", 0)
    
    # All three core inputs dynamically gathered via APIs!
    traffic_task  = get_foot_traffic_proxy(lat, lng)
    comp_task     = get_competitors(lat, lng, business_type)
    
    exact_rent = candidate.get("rent_kzt", 0)
    
    if exact_rent > 0:
        from app.tools.rent import _affordability_score
        afford = _affordability_score(exact_rent, budget)
        rent_result = {
            "avg_rent_kzt": exact_rent,
            "min_rent_kzt": exact_rent,
            "max_rent_kzt": exact_rent,
            "district": candidate.get("district", "Unknown"),
            "source": "Krisha.kz",
            "rent_affordable": afford,
            "explanation": f"Exact listed rent {exact_rent} KZT/mo. Affordability score: {afford}/100."
        }
        traffic_result, competitor_result = await asyncio.gather(traffic_task, comp_task)
    else:
        from app.tools.rent import get_rent_estimate
        rent_task     = get_rent_estimate(candidate.get("address", "Almaty"), business_type, budget, area_size)
        traffic_result, competitor_result, rent_result = await asyncio.gather(
            traffic_task, comp_task, rent_task
        )
    
    # Use Census data exactly for demographics fit factor!
    demo = await get_demographics(lat, lng)

    # Assemble factors for scoring
    factors = {
        "traffic_score":    traffic_result.get("score", 50.0),
        "competitor_gap":   competitor_result.get("competitor_gap", 50.0),
        "rent_affordable":  rent_result.get("rent_affordable", 50.0),
        "demographics_fit": demo.get("demographics_fit_raw", 50.0),
        "area_size":        area_size,
        "district":         rent_result.get("district", "Unknown"),
    }
    # Dynamic synthetic scoring model imported safely
    from app.tools.scoring import score_location
    score_result = await score_location(factors)

    return {
        **candidate,
        "traffic_result":    traffic_result,
        "competitor_result": competitor_result,
        "rent_result":       rent_result,
        "score_result":      score_result,
        "demo_result":       demo
    }


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class LocationScoutAgent:
    """
    Main agent class.  Instantiate once and call `run(request)` per search.
    """

    def __init__(self, top_n: int = DEFAULT_TOP_N):
        self.top_n = top_n

    async def _get_live_candidates(self, city: str, business_type: str, limit: int = 10, area_size: int = 50, rent_or_buy: str = "rent") -> list[dict]:
        """Fetches dynamic real estate candidates directly from Krisha listings."""
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Fetching live candidate properties from Krisha for '{city}' ...")
        
        from app.tools.krisha import scrape_krisha_listings
        from app.tools.rent import ALMATY_DISTRICTS, CBD_LAT, CBD_LNG, _match_district
        
        listings = await scrape_krisha_listings(city, business_type, limit=limit, area_size=area_size, rent_or_buy=rent_or_buy)
        
        if not listings:
            logger.warning("Scraping Krisha produced no listings. Falling back to static Almaty candidates.")
            from app.agent.candidates import ALMATY_CANDIDATES
            return ALMATY_CANDIDATES[:limit]

        candidates = []
        for i, l in enumerate(listings):
            district = _match_district(l["address"]) or "Almaly"
            lat, lng = ALMATY_DISTRICTS.get(district, (CBD_LAT, CBD_LNG))
            
            # small synthetic jitter so coordinates don't completely overlap for same district
            lat += (i * 0.001)
            lng += (i * 0.001)
            
            candidates.append({
                "id": str(i),
                "name": l.get("title", f"Candidate {i}"),
                "district": district,
                "address": l.get("address", city),
                "lat": lat,
                "lng": lng,
                "zone": "commercial",
                "rent_kzt": l.get("price_kzt", 0),
                "krisha_link": l.get("link", "")
            })
            
        return candidates

    async def run(self, request: ScoutRequest, is_demo: bool = False) -> ScoutResult:
        """
        Evaluate all candidates for the requested city and return top-N results.
        """
        logger.info(
            "LocationScoutAgent starting | city=%s, type=%s, budget=%s, is_demo=%s",
            request.city, request.business_type, request.budget, is_demo,
        )

        # ── Step 1: Fetch dynamic candidates from Krisha ──────────────────
        candidates = await self._get_live_candidates(
            request.city, request.business_type, limit=8, area_size=request.area_size, rent_or_buy=request.rent_or_buy
        )

        # ── Step 2: Evaluate all candidates concurrently ──────────────────
        tasks = [
            _evaluate_candidate(c, request.business_type, request.budget, request.area_size)
            for c in candidates
        ]
        evaluated = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out any failed evaluations
        results: list[dict] = []
        for item in evaluated:
            if isinstance(item, Exception):
                logger.error("Candidate evaluation failed:", exc_info=item)
            else:
                results.append(item)

        if not results:
            raise RuntimeError("All candidate evaluations failed. Cannot produce a report.")

        # ── Step 3: Rank by final_score ───────────────────────────────────
        results.sort(
            key=lambda r: r["score_result"].get("final_score", 0),
            reverse=True,
        )
        
        if is_demo:
            top_n = results[:1]
            report_md = "# 🔒 AI Investment Report Locked\nSign in to unlock the full investor-ready location report, foot-traffic analytics, competitor gap metrics, and detailed demographic profiles."
            report_source = "template"
        else:
            top_n = results[: self.top_n]
            # ── Step 4: Generate narrative report ─────────────────────────────
            from app.tools.report import generate_report
            report_result = await generate_report(
                top3_locations  = top_n,
                business_type   = request.business_type,
                city            = request.city,
                budget          = request.budget,
                area_size       = request.area_size,
            )
            report_md = report_result["report_md"]
            report_source = report_result["source"]

        # ── Step 5: Serialise to Pydantic models ──────────────────────────
        location_results = [_to_location_result(r, is_demo=is_demo) for r in top_n]

        logger.info(
            "LocationScoutAgent complete | top score=%.1f",
            top_n[0]["score_result"]["final_score"] if top_n else 0,
        )

        return ScoutResult(
            business_type   = request.business_type,
            city            = request.city,
            budget          = request.budget,
            area_size       = request.area_size,
            top_locations   = location_results,
            report_md       = report_md,
            report_source   = report_source,
            total_evaluated = len(results),
        )


def _to_location_result(r: dict, is_demo: bool = False) -> LocationResult:
    sr = r.get("score_result", {})
    rr = r.get("rent_result",  {})
    tr = r.get("traffic_result", {})
    cr = r.get("competitor_result", {})
    bd = sr.get("breakdown", {})

    if is_demo:
        return LocationResult(
            id                    = r.get("id", ""),
            name                  = r.get("name", ""),
            address               = r.get("address", ""),
            district              = r.get("district", rr.get("district", "")),
            lat                   = r["lat"],
            lng                   = r["lng"],
            zone                  = r.get("zone", ""),
            krisha_link           = r.get("krisha_link", ""),
            final_score           = sr.get("final_score", 0.0),
            score_label           = sr.get("label", ""),
            traffic_score         = "locked",
            competitor_gap        = "locked",
            rent_affordable       = "locked",
            demographics_fit      = "locked",
            avg_rent_kzt          = "locked",
            min_rent_kzt          = "locked",
            max_rent_kzt          = "locked",
            competitor_count      = "locked",
            competitors_nearby    = [],
            traffic_source        = "locked",
            est_monthly_revenue   = "locked",
            est_monthly_profit    = "locked",
            est_annual_roi_pct    = "locked",
            score_explanation     = "Sign in to unlock full detailed ratings.",
        )

    # ROI quick-calc  (mirrors the template formula)
    traffic_score  = tr.get("score", 50)
    daily_covers   = traffic_score * 0.8
    avg_spend_kzt  = 2500
    monthly_rev    = daily_covers * 30 * avg_spend_kzt
    rent           = rr.get("avg_rent_kzt", 0)
    monthly_cost   = rent + (0.40 * monthly_rev)
    monthly_profit = monthly_rev - monthly_cost
    annual_roi     = (monthly_profit * 12 / r.get("budget", monthly_rev)) if monthly_rev else 0

    return LocationResult(
        id                    = r.get("id", ""),
        name                  = r.get("name", ""),
        address               = r.get("address", ""),
        district              = r.get("district", rr.get("district", "")),
        lat                   = r["lat"],
        lng                   = r["lng"],
        zone                  = r.get("zone", ""),
        krisha_link           = r.get("krisha_link", ""),
        final_score           = sr.get("final_score", 0.0),
        score_label           = sr.get("label", ""),
        traffic_score         = bd.get("traffic_score",   {}).get("raw", 0.0),
        competitor_gap        = bd.get("competitor_gap",  {}).get("raw", 0.0),
        rent_affordable       = bd.get("rent_affordable", {}).get("raw", 0.0),
        demographics_fit      = r.get("demo_result", {}).get("demographics_fit_raw", 50.0),
        avg_rent_kzt          = rr.get("avg_rent_kzt", 0.0),
        min_rent_kzt          = rr.get("min_rent_kzt", 0.0),
        max_rent_kzt          = rr.get("max_rent_kzt", 0.0),
        competitor_count      = cr.get("count", -1),
        competitors_nearby    = cr.get("competitors", []),
        traffic_source        = tr.get("source", ""),
        est_monthly_revenue   = round(monthly_rev, 2),
        est_monthly_profit    = round(monthly_profit, 2),
        est_annual_roi_pct    = round(annual_roi, 2),
        score_explanation     = sr.get("explanation", ""),
    )
