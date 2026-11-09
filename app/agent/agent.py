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


def _in_almaty(lat: float, lng: float) -> bool:
    """Sanity check that a geocoded point is inside Almaty's bounding box."""
    return 43.10 <= lat <= 43.45 and 76.70 <= lng <= 77.15


# ---------------------------------------------------------------------------
# Core helper: evaluate a single candidate
# ---------------------------------------------------------------------------

async def _evaluate_candidate(
    candidate:       dict,
    business_type:   str,
    budget:          float,
    area_size:       int,
    rent_or_buy:     str = "rent",
) -> dict:
    """Runs the three data-gathering tools concurrently for one location."""
    lat = candidate.get("lat", 0)
    lng = candidate.get("lng", 0)
    
    # All three core inputs dynamically gathered via APIs!
    # 2GIS search works much better with Russian queries ("кофейня", not "coffee shop").
    from app.i18n.terms import get_search_ru
    search_q = get_search_ru(business_type, "business_type").split(",")[0].strip() or business_type
    traffic_task  = get_foot_traffic_proxy(lat, lng)
    comp_task     = get_competitors(lat, lng, search_q)
    
    exact_rent = candidate.get("rent_kzt", 0)
    
    if exact_rent > 0:
        from app.tools.rent import _affordability_score
        if (rent_or_buy or "rent").lower() == "buy":
            # Purchase price → monthly equivalent over a 10-year payback horizon,
            # so it is comparable with the monthly budget.
            monthly_equiv = round(exact_rent / 120)
            explanation = (f"Purchase price {exact_rent} KZT ≈ {monthly_equiv} KZT/mo "
                           f"over 10 years.")
        else:
            monthly_equiv = exact_rent
            explanation = f"Exact listed rent {exact_rent} KZT/mo."
        afford = _affordability_score(monthly_equiv, budget)
        rent_result = {
            "avg_rent_kzt": monthly_equiv,
            "min_rent_kzt": monthly_equiv,
            "max_rent_kzt": monthly_equiv,
            "purchase_price_kzt": exact_rent if monthly_equiv != exact_rent else None,
            "district": candidate.get("district", "Unknown"),
            "source": "Krisha.kz",
            "rent_affordable": afford,
            "explanation": f"{explanation} Affordability score: {afford}/100."
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

    # Scoring happens in the agent after missing values are replaced by averages.
    return {
        **candidate,
        "area_size":         area_size,
        "budget":            budget,
        "business_type":     business_type,
        "traffic_result":    traffic_result,
        "competitor_result": competitor_result,
        "rent_result":       rent_result,
        "demo_result":       demo
    }


NEUTRAL_DEFAULT = 50.0


def _fill_missing_with_averages(results: list[dict]) -> None:
    """
    When 2GIS gave no data for some candidates (no key, quota exhausted,
    timeout) we do NOT invent numbers: the missing value becomes the mean of
    the candidates that did get real data, or a neutral 50 if none did.
    The result is flagged so the UI/report can say it is an average.
    """
    for res_key, val_key in (("traffic_result", "score"), ("competitor_result", "competitor_gap")):
        real = [r[res_key][val_key] for r in results if r[res_key].get(val_key) is not None]
        avg = round(sum(real) / len(real), 1) if real else NEUTRAL_DEFAULT
        note = (f"Average of {len(real)} locations with 2GIS data" if real
                else "No 2GIS data – neutral average used")
        for r in results:
            if r[res_key].get(val_key) is None:
                r[res_key] = {**r[res_key], val_key: avg, "estimated": True,
                              "source": "average", "explanation": f"{note}: {avg}/100."}
                if res_key == "traffic_result":
                    r[res_key]["score"] = avg


async def _score(r: dict) -> dict:
    from app.tools.scoring import score_location
    return await score_location({
        "traffic_score":    r["traffic_result"].get("score", NEUTRAL_DEFAULT),
        "competitor_gap":   r["competitor_result"].get("competitor_gap", NEUTRAL_DEFAULT),
        "rent_affordable":  r["rent_result"].get("rent_affordable", NEUTRAL_DEFAULT),
        "demographics_fit": r["demo_result"].get("demographics_fit_raw", NEUTRAL_DEFAULT),
        "area_size":        r.get("area_size", 50),
        "district":         r["rent_result"].get("district", "Unknown"),
    })


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

        # Geocode every listing address via 2GIS so each candidate gets its own
        # real coordinates (falls back to the district centre if that fails).
        geo_results = await asyncio.gather(
            *[geocode_city(f"{city}, {l.get('address', '')}") for l in listings],
            return_exceptions=True,
        )

        candidates = []
        for i, l in enumerate(listings):
            district = _match_district(l["address"]) or "Almaly"
            geo = geo_results[i]
            if isinstance(geo, tuple) and _in_almaty(*geo):
                lat, lng = geo
            else:
                lat, lng = ALMATY_DISTRICTS.get(district, (CBD_LAT, CBD_LNG))
                # small jitter so coordinates don't completely overlap for same district
                lat += (i * 0.002)
                lng += (i * 0.002)

            candidates.append({
                "id": str(i),
                "name": l.get("title", f"Candidate {i}"),
                "district": district,
                "address": l.get("address", city),
                "lat": lat,
                "lng": lng,
                "zone": "commercial",
                "rent_kzt": l.get("price_kzt", 0),
                "listing_area_m2": l.get("area_m2"),
                "price_per_m2": l.get("price_per_m2"),
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
            _evaluate_candidate(c, request.business_type, request.budget, request.area_size, request.rent_or_buy)
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

        _fill_missing_with_averages(results)
        scores = await asyncio.gather(*[_score(r) for r in results])
        for r, sc in zip(results, scores):
            r["score_result"] = sc

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
                lang            = request.lang,
            )
            report_md = report_result["report_md"]
            report_source = report_result["source"]

        # ── Step 5: Serialise to Pydantic models ──────────────────────────
        location_results = [_to_location_result(r, is_demo=is_demo, lang=request.lang) for r in top_n]

        logger.info(
            "LocationScoutAgent complete | top score=%.1f",
            top_n[0]["score_result"]["final_score"] if top_n else 0,
        )

        from app.i18n.terms import get_display_label
        display_biz = get_display_label(request.business_type, "business_type", request.lang)
        display_city = get_display_label(request.city, "city", request.lang)

        return ScoutResult(
            business_type   = display_biz,
            city            = display_city,
            budget          = request.budget,
            area_size       = request.area_size,
            top_locations   = location_results,
            report_md       = report_md,
            report_source   = report_source,
            total_evaluated = len(results),
        )


def _to_location_result(r: dict, is_demo: bool = False, lang: str = "en") -> LocationResult:
    from app.i18n.terms import translate_location_name, translate_address, get_display_label
    sr = r.get("score_result", {})
    rr = r.get("rent_result",  {})
    tr = r.get("traffic_result", {})
    cr = r.get("competitor_result", {})
    bd = sr.get("breakdown", {})

    raw_name = r.get("name", "")
    raw_address = r.get("address", "")
    raw_district = r.get("district", rr.get("district", ""))
    raw_zone = r.get("zone", "")

    loc_name = translate_location_name(raw_name, lang)
    loc_address = translate_address(raw_address, lang)
    loc_district = get_display_label(raw_district, "district", lang)
    loc_zone = get_display_label(raw_zone, "zone", lang)

    if is_demo:
        return LocationResult(
            id                    = r.get("id", ""),
            name                  = loc_name,
            address               = loc_address,
            district              = loc_district,
            lat                   = r["lat"],
            lng                   = r["lng"],
            zone                  = loc_zone,
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

    # ROI quick-calc – same function is used by the report, so numbers match.
    from app.tools.scoring import calc_roi
    roi = calc_roi(
        traffic_score = tr.get("score", 50),
        rent_kzt      = rr.get("avg_rent_kzt", 0) or 0,
        budget_kzt    = r.get("budget", 0) or 0,
        business_type = r.get("business_type", ""),
    )
    monthly_rev    = roi["monthly_revenue"]
    monthly_profit = roi["monthly_profit"]
    annual_roi     = roi["annual_roi_pct"]

    return LocationResult(
        id                    = r.get("id", ""),
        name                  = loc_name,
        address               = loc_address,
        district              = loc_district,
        lat                   = r["lat"],
        lng                   = r["lng"],
        zone                  = loc_zone,
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
        competitor_count      = cr.get("count") if cr.get("count") is not None else -1,
        competitors_nearby    = cr.get("competitors", []),
        traffic_source        = tr.get("source", ""),
        est_monthly_revenue   = round(monthly_rev, 2),
        est_monthly_profit    = round(monthly_profit, 2),
        est_annual_roi_pct    = round(annual_roi, 2),
        score_explanation     = sr.get("explanation", ""),
    )
