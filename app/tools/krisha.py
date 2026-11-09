import logging
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

import re as _re

# "265 000 〒", "от 3 500 〒 за м²", "45 000 000 ₸" ...
_PRICE_RE = _re.compile(
    r'(\d[\d   ]*)\s*(?:〒|₸|тг|тенге)\s*(за\s*(?:кв\.?\s*м|м²|м2)|/\s*м²|/\s*м2)?',
    _re.IGNORECASE,
)
_AREA_RE = _re.compile(r'(\d+(?:[.,]\d+)?)\s*(?:м²|м2|кв\.?\s*м)', _re.IGNORECASE)


def parse_area(text: str) -> float | None:
    """Area in m² from a listing title like 'Помещение · 60 м²'."""
    m = _AREA_RE.search(text or "")
    return float(m.group(1).replace(",", ".")) if m else None


def parse_price(price_text: str, listing_area: float | None = None) -> tuple[int, int | None]:
    """
    Returns (total_price_kzt, price_per_m2_kzt).

    Krisha cards often show BOTH the full price and a per-m² price
    ("265 000 〒" + "5 300 〒 за м²"). The full price is the first amount
    WITHOUT a per-m² suffix. Only if a card shows nothing but a per-m² price
    do we multiply it by the listing's own area (from its title).
    """
    total, per_m2 = None, None
    for m in _PRICE_RE.finditer(price_text or ""):
        val = int(_re.sub(r"\D", "", m.group(1)) or 0)
        if not val:
            continue
        if m.group(2):
            per_m2 = per_m2 or val
        elif total is None:
            total = val
    if total is None and per_m2 and listing_area:
        total = round(per_m2 * listing_area)
    if total is None and not per_m2:
        # No currency sign at all – take the first number as the full price.
        nums = _re.findall(r"\d[\d   ]*", price_text or "")
        if nums:
            total = int(_re.sub(r"\D", "", nums[0]) or 0)
    return int(total or 0), per_m2


def area_range(area_size: int) -> tuple[int, int]:
    """Search window around the requested area: −30% … +50%."""
    area_size = max(10, int(area_size or 50))
    return max(10, int(area_size * 0.7)), int(area_size * 1.5) + 1

# Map our app's business types to krisha.kz URL paths
BUSINESS_TYPE_TO_KRISHA = {
    "coffee_shop": "obshchepit",
    "coffee shop": "obshchepit",
    "restaurant": "obshchepit",
    "gym": "ofisy", # safe fallback
    "office": "ofisy",
    "retail": "magaziny_i_butiki",
    "shop": "magaziny_i_butiki",
    "supermarket": "magaziny_i_butiki",
    "grocery": "magaziny_i_butiki",
    "salon": "salony_krasoty",
    "beauty salon": "salony_krasoty",
}

async def scrape_krisha_listings(city: str, business_type: str, limit: int = 5, area_size: int = 50, rent_or_buy: str = "rent") -> List[Dict[str, Any]]:
    """
    Scrapes commercial listings from krisha.kz.
    """
    krisha_type = BUSINESS_TYPE_TO_KRISHA.get(business_type.lower().strip(), "ofisy")
    city_slug = city.lower().strip()
    action = "arenda" if rent_or_buy.lower().strip() == "rent" else "prodazha"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    }
    
    min_area, max_area = area_range(area_size)

    params = f"?das[live.square][from]={min_area}"
    if max_area < 99999:
        params += f"&das[live.square][to]={max_area}"
    
    url = f"https://krisha.kz/{action}/kommercheskaya-nedvizhimost/{city_slug}/typi-{krisha_type}/{params}"
    fallback_url = f"https://krisha.kz/{action}/kommercheskaya-nedvizhimost/{city_slug}/{params}"
    
    listings = []
    
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            
            # If 404 or bad routing on category, fallback to just city-wide commercial
            if resp.status_code != 200:
                logger.warning(f"Category URL {url} hit {resp.status_code}. Using fallback {fallback_url}")
                resp = await client.get(fallback_url, headers=headers, follow_redirects=True)
                if resp.status_code != 200:
                    logger.error(f"Fallback URL {fallback_url} also hit {resp.status_code}.")
                    return []
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.select('.a-card')
            
            import re
            
            for card in cards:
                if len(listings) >= limit:
                    break
                    
                title_el = card.select_one('.a-card__title')
                if not title_el:
                    continue
                    
                title = title_el.text.strip()
                
                # Filter out promoted listings that bypass Krisha URL filters
                sqm = parse_area(title)
                if sqm:
                    if sqm < min_area or sqm > max_area:
                        continue
                price_el = card.select_one('.a-card__price')
                address_el = card.select_one('.a-card__subtitle')
                
                title = title_el.text.strip() if title_el else "Unknown Commercial Property"
                price_text = price_el.text.strip() if price_el else ""
                
                link = ""
                if title_el and title_el.has_attr("href"):
                    link = "https://krisha.kz" + title_el["href"]
                    
                address = address_el.text.strip() if address_el else city

                listing_area = parse_area(title)
                price_val, per_m2 = parse_price(price_text, listing_area)

                listings.append({
                    "title": title,
                    "address": address,
                    "price_kzt_str": price_text,
                    "price_kzt": price_val,
                    "price_per_m2": per_m2,
                    "area_m2": listing_area,
                    "link": link,
                    "source": "krisha.kz"
                })
                
    except Exception as e:
        logger.exception("Error scraping Krisha.kz")

    return listings


async def scrape_krisha_apartments(
    city: str,
    rent_or_buy: str,
    price_min: float | None = None,
    price_max: float | None = None,
    area_size: int = 50,
    limit: int = 5
) -> list[dict]:
    """Scrapes residential apartment listings from krisha.kz."""
    city_slug = city.lower().strip()
    action = "arenda" if rent_or_buy.lower().strip() == "rent" else "prodazha"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,ru;q=0.8",
    }
    
    min_area, max_area = area_range(area_size)

    params = f"?das[live.square][from]={min_area}"
    if max_area < 99999:
        params += f"&das[live.square][to]={max_area}"
        
    if price_min is not None:
        params += f"&das[price][from]={int(price_min)}"
    if price_max is not None:
        params += f"&das[price][to]={int(price_max)}"
        
    url = f"https://krisha.kz/{action}/kvartiry/{city_slug}/{params}"
    
    listings = []
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, headers=headers, follow_redirects=True)
            if resp.status_code != 200:
                logger.error(f"Apartment URL {url} hit {resp.status_code}")
                return []
                
            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.select('.a-card')
            
            import re
            for card in cards:
                if len(listings) >= limit:
                    break
                    
                title_el = card.select_one('.a-card__title')
                if not title_el:
                    continue
                    
                title = title_el.text.strip()
                
                # Check square meters
                sqm = parse_area(title)
                if sqm:
                    if sqm < min_area or sqm > max_area:
                        continue
                        
                price_el = card.select_one('.a-card__price')
                address_el = card.select_one('.a-card__subtitle')
                
                price_text = price_el.text.strip() if price_el else ""
                address = address_el.text.strip() if address_el else city
                
                link = ""
                if title_el and title_el.has_attr("href"):
                    link = "https://krisha.kz" + title_el["href"]
                    
                listing_area = parse_area(title)
                price_val, _ = parse_price(price_text, listing_area)

                listings.append({
                    "title": title,
                    "address": address,
                    "price_kzt_str": price_text,
                    "price_kzt": price_val,
                    "area_m2": listing_area,
                    "link": link,
                    "source": "krisha.kz"
                })
    except Exception as e:
        logger.exception("Error scraping Krisha apartments")
        
    return listings
