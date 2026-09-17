import logging
import httpx
from bs4 import BeautifulSoup
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

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
    
    if area_size <= 20:
        min_area, max_area = 20, 49
    elif area_size <= 50:
        min_area, max_area = 50, 99
    elif area_size <= 100:
        min_area, max_area = 100, 199
    else:
        min_area, max_area = 200, 99999
        
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
                
            soup = BeautifulSoup(resp.text, 'lxml' if 'lxml' in globals() else 'html.parser')
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
                sqm_match = re.search(r'(\d+(?:\.\d+)?)\s*м²', title)
                if sqm_match:
                    sqm = float(sqm_match.group(1))
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

                # Parse price (roughly) from text like "540 000 〒 за месяц"
                price_val = 0
                import re
                nums = re.findall(r'\d+', price_text.replace('\xa0', '').replace(' ', ''))
                if nums:
                    price_val = int(nums[0])
                    
                    # Convert per sq.m rent to approximate monthly total
                    if "за кв. м" in price_text.lower():
                        price_val = price_val * area_size
                
                listings.append({
                    "title": title,
                    "address": address,
                    "price_kzt_str": price_text,
                    "price_kzt": price_val,
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
    
    # Area thresholds matching the business flow pattern
    if area_size <= 20:
        min_area, max_area = 20, 49
    elif area_size <= 50:
        min_area, max_area = 50, 99
    elif area_size <= 100:
        min_area, max_area = 100, 199
    else:
        min_area, max_area = 200, 99999
        
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
                
            soup = BeautifulSoup(resp.text, 'lxml' if 'lxml' in globals() else 'html.parser')
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
                sqm_match = re.search(r'(\d+(?:\.\d+)?)\s*м²', title)
                if sqm_match:
                    sqm = float(sqm_match.group(1))
                    if sqm < min_area or sqm > max_area:
                        continue
                        
                price_el = card.select_one('.a-card__price')
                address_el = card.select_one('.a-card__subtitle')
                
                price_text = price_el.text.strip() if price_el else ""
                address = address_el.text.strip() if address_el else city
                
                link = ""
                if title_el and title_el.has_attr("href"):
                    link = "https://krisha.kz" + title_el["href"]
                    
                price_val = 0
                nums = re.findall(r'\d+', price_text.replace('\xa0', '').replace(' ', ''))
                if nums:
                    price_val = int(nums[0])
                    
                listings.append({
                    "title": title,
                    "address": address,
                    "price_kzt_str": price_text,
                    "price_kzt": price_val,
                    "link": link,
                    "source": "krisha.kz"
                })
    except Exception as e:
        logger.exception("Error scraping Krisha apartments")
        
    return listings
