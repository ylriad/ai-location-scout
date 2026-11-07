import logging
import httpx
import asyncio

logger = logging.getLogger(__name__)

# FCC API to convert lat/lng to US Census FIPS (State, County, Tract, Block)
FCC_GEO_URL = "https://geo.fcc.gov/api/census/block/find"
# US Census American Community Survey (ACS) 5-Year Estimates
# Variables:
# B01003_001E = Total Population
# B19013_001E = Median Household Income
# B25064_001E = Median Gross Rent (Residential)
# B15003_022E = Educational Attainment: Bachelor's Degree
CENSUS_URL = "https://api.census.gov/data/2022/acs/acs5"

async def get_demographics(lat: float, lng: float) -> dict:
    """
    Fetches estimated demographic data locally for Almaty (Proxy model).
    Based strictly off geospatial lat/lng bounding approximations.
    """
    from app.tools.rent import ALMATY_DISTRICTS
    
    # Sensible defaults for general Almaty
    result = {
        "population": 150000,
        "median_income_usd": 1200000, # KZT
        "median_gross_rent_usd": 400000, # KZT
        "bachelors_degree_count": 45000,
        "source": "Bureau of National Statistics RK (Modelled)",
        "demographics_fit_raw": 50.0
    }
    
    # Very crude distance-based assignment for different demographic zones in Almaty.
    # Higher income/education in Medeu and Bostandyq. Higher population in Alatau/Auezov.
    closest_district = "Bostandyq" # fallback
    min_dist = float('inf')
    
    for district, (d_lat, d_lng) in ALMATY_DISTRICTS.items():
        dist = (lat - d_lat)**2 + (lng - d_lng)**2
        if dist < min_dist:
            min_dist = dist
            closest_district = district
            
    if closest_district in ["Medeu", "Bostandyq"]:
        result["median_income_usd"] = 1800000
        result["bachelors_degree_count"] = 80000
        result["demographics_fit_raw"] = 85.0
    elif closest_district in ["Almaly", "Auezov"]:
        result["median_income_usd"] = 1100000
        result["population"] = 350000
        result["demographics_fit_raw"] = 70.0
    elif closest_district in ["Alatau", "Zhetysu", "Turksib", "Nauryzbay"]:
        result["median_income_usd"] = 800000
        result["population"] = 280000
        result["demographics_fit_raw"] = 40.0
        
    return result
