import asyncio
import logging
from typing import List, Dict, Any
from app.tools.personal_poi import geocode_destination, haversine_distance, get_personal_scores
from app.tools.krisha import scrape_krisha_apartments
from app.models.schemas import PersonalScoutRequest, LocationResult, PersonalScoutResult

logger = logging.getLogger(__name__)

# Fallback residential candidates for Almaty near major universities/landmarks
ALMATY_APARTMENTS = [
    {
        "id": "apt_kbtu",
        "name": "Student Flat near KBTU",
        "district": "Almaly",
        "address": "Tole Bi St 59, Almaly, Almaty",
        "lat": 43.2558,
        "lng": 76.9423,
        "price_kzt": 280000,
        "zone": "residential",
        "krisha_link": "https://krisha.kz/a/show/111111"
    },
    {
        "id": "apt_kaznu",
        "name": "Cozy Apartment near KazNU Campus",
        "district": "Bostandyq",
        "address": "Al-Farabi Ave 71, Bostandyq, Almaty",
        "lat": 43.2241,
        "lng": 76.9272,
        "price_kzt": 320000,
        "zone": "student-friendly",
        "krisha_link": "https://krisha.kz/a/show/222222"
    },
    {
        "id": "apt_satbayev",
        "name": "Spacious Room near Satbayev University",
        "district": "Bostandyq",
        "address": "Satpaev St 22, Bostandyq, Almaty",
        "lat": 43.2382,
        "lng": 76.9155,
        "price_kzt": 240000,
        "zone": "residential",
        "krisha_link": "https://krisha.kz/a/show/333333"
    },
    {
        "id": "apt_medeu",
        "name": "Luxury Apartment in Medeu District",
        "district": "Medeu",
        "address": "Dostyk Ave 105, Medeu, Almaty",
        "lat": 43.2450,
        "lng": 76.9580,
        "price_kzt": 580000,
        "zone": "upscale",
        "krisha_link": "https://krisha.kz/a/show/444444"
    },
    {
        "id": "apt_auezov",
        "name": "Renovated Flat in Auezov District",
        "district": "Auezov",
        "address": "Raiymbek Ave 210, Auezov, Almaty",
        "lat": 43.2200,
        "lng": 76.8700,
        "price_kzt": 190000,
        "zone": "residential",
        "krisha_link": "https://krisha.kz/a/show/555555"
    }
]

class PersonalScoutAgent:
    def __init__(self, top_n: int = 3):
        self.top_n = top_n

    async def run(self, request: PersonalScoutRequest, is_demo: bool = False) -> PersonalScoutResult:
        logger.info(
            "PersonalScoutAgent starting | destination=%s, rent_or_buy=%s, price=%s-%s, is_demo=%s",
            request.destination, request.rent_or_buy, request.price_min, request.price_max, is_demo
        )

        # 1. Geocode destination
        dest_lat, dest_lng = await geocode_destination(request.destination)
        
        # 2. Fetch candidates from Krisha or fall back to static apartments
        # Set a slightly larger limit to allow filtering
        listings = await scrape_krisha_apartments(
            city=request.city,
            rent_or_buy=request.rent_or_buy,
            price_min=request.price_min,
            price_max=request.price_max,
            area_size=request.area_size,
            limit=8
        )
        
        candidates = []
        if listings:
            # Map listings to candidate format
            from app.tools.rent import _match_district, ALMATY_DISTRICTS, CBD_LAT, CBD_LNG
            for i, l in enumerate(listings):
                district = _match_district(l["address"]) or "Almaly"
                lat, lng = ALMATY_DISTRICTS.get(district, (CBD_LAT, CBD_LNG))
                # Add small jitter so they don't overlay
                lat += (i * 0.0012)
                lng += (i * 0.0012)
                
                candidates.append({
                    "id": f"krisha_apt_{i}",
                    "name": l["title"],
                    "district": district,
                    "address": l["address"],
                    "lat": lat,
                    "lng": lng,
                    "price_kzt": l["price_kzt"],
                    "zone": "residential",
                    "krisha_link": l["link"]
                })
        else:
            logger.warning("Scraping Krisha apartments returned no listings. Falling back to static Almaty apartments.")
            # Filter static apartments by price if possible
            for apt in ALMATY_APARTMENTS:
                if request.price_min <= apt["price_kzt"] <= request.price_max:
                    candidates.append(apt)
            # If no apartments in range, just use all static apartments
            if not candidates:
                candidates = ALMATY_APARTMENTS[:8]

        # 3. Evaluate each candidate concurrently
        async def eval_candidate(c: dict) -> Dict[str, Any]:
            lat, lng = c["lat"], c["lng"]
            # Get convenience, safety, entertainment scores
            scores = await get_personal_scores(lat, lng)
            
            # Calculate distance and commute score
            dist_km = haversine_distance(lat, lng, dest_lat, dest_lng)
            # Distance scoring: 0km = 100, 10km = 50, >20km = 0
            commute_score = max(20.0, min(100.0, 100.0 - (dist_km * 5.0)))
            
            # Weighted formula
            # Convenience (30%), Safety (30%), Lifestyle (20%), Commute/Distance (20%)
            final_score = (
                scores["convenience_score"] * 0.30 +
                scores["safety_score"] * 0.30 +
                scores["lifestyle_score"] * 0.20 +
                commute_score * 0.20
            )
            final_score = round(final_score, 1)
            
            # Determine score label
            if final_score >= 85:
                label = "Excellent"
            elif final_score >= 70:
                label = "Good"
            elif final_score >= 55:
                label = "Fair"
            elif final_score >= 40:
                label = "Below average"
            else:
                label = "Poor"
                
            return {
                **c,
                "scores": scores,
                "distance_km": round(dist_km, 2),
                "commute_score": round(commute_score, 1),
                "final_score": final_score,
                "label": label
            }

        eval_tasks = [eval_candidate(c) for c in candidates]
        results = await asyncio.gather(*eval_tasks)

        # Rank by final score descending
        results.sort(key=lambda x: x["final_score"], reverse=True)

        # Enforce demo mode limitations
        limit_n = 1 if is_demo else self.top_n
        top_n_results = results[:limit_n]

        location_results = []
        for r in top_n_results:
            # Build 2GIS deep link for directions:
            # https://2gis.ru/routeSearch/rsType/pedestrian/from/<lon>,<lat>/to/<lon>,<lat>
            directions_url = f"https://2gis.ru/routeSearch/rsType/pedestrian/from/{r['lng']},{r['lat']}/to/{dest_lng},{dest_lat}"
            
            # If demo, lock details and hide real ratings!
            if is_demo:
                loc_res = LocationResult(
                    id=r["id"],
                    name=r["name"],
                    address=r["address"],
                    district=r["district"],
                    lat=r["lat"],
                    lng=r["lng"],
                    zone=r["zone"],
                    krisha_link=r["krisha_link"],
                    final_score=r["final_score"],
                    score_label=r["label"],
                    # Lock sub-scores
                    convenience_score="locked",
                    safety_score="locked",
                    lifestyle_score="locked",
                    distance_km=r["distance_km"],
                    directions_url=directions_url,
                    # Lock standard scores as well just in case
                    traffic_score="locked",
                    competitor_gap="locked",
                    rent_affordable="locked",
                    demographics_fit="locked",
                    avg_rent_kzt="locked",
                    min_rent_kzt="locked",
                    max_rent_kzt="locked",
                    competitor_count="locked",
                    score_explanation="Sign in to unlock full detailed ratings."
                )
            else:
                # Full access
                loc_res = LocationResult(
                    id=r["id"],
                    name=r["name"],
                    address=r["address"],
                    district=r["district"],
                    lat=r["lat"],
                    lng=r["lng"],
                    zone=r["zone"],
                    krisha_link=r["krisha_link"],
                    final_score=r["final_score"],
                    score_label=r["label"],
                    convenience_score=r["scores"]["convenience_score"],
                    safety_score=r["scores"]["safety_score"],
                    lifestyle_score=r["scores"]["lifestyle_score"],
                    distance_km=r["distance_km"],
                    directions_url=directions_url,
                    avg_rent_kzt=float(r["price_kzt"]),
                    min_rent_kzt=float(r["price_kzt"] * 0.9),
                    max_rent_kzt=float(r["price_kzt"] * 1.1),
                    score_explanation=(
                        f"Overall rating: {r['label']} ({r['final_score']}/100). "
                        f"Convenience: {r['scores']['convenience_score']}/100, "
                        f"Safety: {r['scores']['safety_score']}/100, "
                        f"Entertainment: {r['scores']['lifestyle_score']}/100, "
                        f"Distance: {r['distance_km']} km (Commute Score: {r['commute_score']}/100)."
                    )
                )
            location_results.append(loc_res)

        return PersonalScoutResult(
            rent_or_buy=request.rent_or_buy,
            destination=request.destination,
            price_min=request.price_min,
            price_max=request.price_max,
            city=request.city,
            area_size=request.area_size,
            top_locations=location_results,
            total_evaluated=len(results)
        )
