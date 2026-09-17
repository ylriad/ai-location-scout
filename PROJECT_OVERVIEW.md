# 🏙️ AI Location Scout — Complete Project Overview & Technical Documentation

> **Current Version**: `1.0.0`  
> **Platform**: FastAPI + Python 3.13 + Vanilla JS Single-Page App  
> **Target Region**: Almaty & Kazakhstan (with extensible regional hooks)  
> **Repository Root**: `c:\Antigravity\location_scout`

---

## 📌 1. Executive Summary

**AI Location Scout** is an end-to-end commercial and residential site-selection intelligence platform. It replaces manual real estate research and intuition-based site selection with real-time geospatial analytics, live market scraping, demographic modeling, talent sourcing, and AI-generated investment feasibility reports.

The application serves two distinct user segments:
1. **Commercial & Retail Entrepreneurs** (`/scout`): Looking for high-traffic, low-competition commercial venues with positive ROI and talent availability in Almaty.
2. **Students & Residential Renters** (`/scout/personal`): Looking for apartments near university campuses or specific landmarks, evaluated for walkability, neighborhood safety, convenience, and lifestyle amenities.

All live external dependencies (2GIS, Krisha.kz, HeadHunter, Claude AI, Google Maps, OpenStreetMap) are engineered with resilient fallbacks so the full platform functions seamlessly in both production and zero-API offline demo modes.

---

## 🏗️ 2. High-Level Architecture & Tech Stack

```
┌────────────────────────────────────────────────────────────────────────┐
│                        FRONTEND CLIENT (SPA)                           │
│  - Vanilla JavaScript (ES6+), Glassmorphism Dark Theme CSS3            │
│  - Multi-View State Router (Landing, Choice Dashboard, Search, Auth)   │
│  - Async Multi-Step Progress Loader, Tabs & Saved Favorites Modal      │
│  - Browser LocalStorage for Bookmarks + HTTP-Only Cookie Session Store │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTP / JSON API
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND ENGINE                          │
│  - Python 3.13 / FastAPI / Uvicorn (Asynchronous non-blocking runtime)  │
│  - Session Management (PyJWT, HTTP-only Lax Cookies)                   │
│  - Passwords hashed via Bcrypt                                         │
│  - Rate/Demo Limitation Tracker (IP + Cookie Tracking)                │
└───────┬───────────────────────────┬────────────────────────────┬───────┘
        │                           │                            │
        ▼                           ▼                            ▼
┌─────────────────┐       ┌─────────────────┐       ┌────────────────────┐
│   DATA & AUTH   │       │  AGENT RUNTIMES │       │   TOOL PIPELINE    │
│  SQLite3 DB     │       │                 │       │                    │
│  - users        │       │  Business Scout │       │ 1. 2GIS Catalog    │
│  - search_logs  │       │  Personal Scout │       │ 2. Krisha Scraper  │
│  rent_data.csv  │       │  Candidate Rank │       │ 3. Apify HH Talent │
│                 │       │                 │       │ 4. Claude Reports  │
└─────────────────┘       └─────────────────┘       └────────────────────┘
```

### Core Technologies
* **Runtime**: Python `3.10+` (tested on Python `3.13.7`)
* **API Framework**: `FastAPI` (v0.115.0+) with `uvicorn[standard]` (v0.30.0+)
* **Validation & Modeling**: `Pydantic` v2 (v2.7.0+)
* **Database & Persistence**: `SQLite3` (`location_scout.db`) with native connection pooling
* **Security & Auth**: `bcrypt` (password salt/hash) and `PyJWT` (HS256 signed access tokens)
* **Web Scraping & Extraction**: `BeautifulSoup4` + `lxml` + `httpx` (async HTTP client)
* **Talent Sourcing**: `apify-client` (v1.7.1+) running headless Chromium scraper actors
* **AI Analysis**: `anthropic` Python SDK calling Claude (`claude-opus-4-5` / `claude-3-7-sonnet`)
* **Test Suite**: `pytest` (v9.0+) with `pytest-asyncio` and `anyio`

---

## 🔄 3. Dual-Mode Workflows & User Journeys

The platform supports two parallel user journeys selected from the unified choice dashboard:

### Flow A: Commercial Business Scout (`POST /scout`)
Designed for entrepreneurs opening a coffee shop, restaurant, gym, salon, or retail boutique.

```
User Input: Business Type, City, Budget (KZT), Desired Area (m²), Rent/Buy Mode, Top N
   │
   ├─► 1. Live Candidate Generation
   │      - Scrapes commercial listings from Krisha.kz matching exact area bracket (20-49, 50-99, 100-199, 200+ m²)
   │      - Falls back to 10 curated Almaty commercial hubs (Medeu, Almaly, Bostandyq, etc.)
   │
   ├─► 2. Concurrent Spatial Data Gathering (per candidate)
   │      ├── [2GIS / Google Maps]: Evaluates branch establishment density for foot traffic (0-100)
   │      ├── [2GIS / Overpass]: Queries competitor count in 1000m radius -> calculates Competitor Gap (0-100)
   │      ├── [Krisha.kz / CSV DB]: Matches listed rent vs. user budget -> calculates Affordability Score (0-100)
   │      └── [Demographic Proxy]: Maps coordinates to district income/spending power (0-100)
   │
   ├─► 3. Weighted Scoring Engine
   │      Final Score = (Traffic × 0.35) + (Competitor Gap × 0.25) + (Rent Affordability × 0.20) + (Demographics × 0.20)
   │
   ├─► 4. Financial & ROI Simulation
   │      - Est. Daily Covers = Traffic Score × 0.8
   │      - Monthly Revenue = Covers × 30 × 2,500 KZT average spend
   │      - Monthly Costs = Rent + (40% of Revenue for COGS/Staff/Utilities)
   │      - Annual ROI % = (Annual Net Profit / Total Budget) × 100
   │
   ├─► 5. Narrative Investment Report Generation
   │      - Formulates structured prompt with top 3 candidates and sends to Claude API
   │      - Produces investor-ready executive summary, location comparison, and recommendation
   │      - Falls back to statistical template if Claude API key is absent
   │
   └─► 6. Result Delivery & UI Render
```

### Flow B: Student & Residential Housing Scout (`POST /scout/personal`)
Designed for university students and residential renters seeking housing near their campus or workplace.

```
User Input: Destination / University, Min/Max Price (KZT), Area Category (m²), Rent/Buy, Top N
   │
   ├─► 1. Destination Geocoding
   │      - Recognizes major universities (KBTU, KazNU, Satbayev, UIB) and landmarks
   │      - Geocodes custom destination string via 2GIS items API
   │
   ├─► 2. Live Apartment Acquisition
   │      - Crawls Krisha.kz residential listings (`/arenda/kvartiry/almaty/`) with area and price clamps
   │      - Falls back to curated residential properties near student hubs
   │
   ├─► 3. Neighborhood Intelligence & Scoring (per apartment)
   │      ├── Convenience Score: 2GIS query for pharmacies, grocery stores, schools (`min 40, max 100`)
   │      ├── Safety Score: 2GIS query for police stations, playgrounds, civic organizations (`min 45, max 100`)
   │      ├── Lifestyle Score: 2GIS query for cafes, restaurants, parks, leisure venues (`min 35, max 100`)
   │      └── Commute Score: Haversine distance in km to campus (`100 - dist_km * 5.0`)
   │
   ├─► 4. Weighted Formula
   │      Final Score = (Convenience × 0.30) + (Safety × 0.30) + (Lifestyle × 0.20) + (Commute × 0.20)
   │
   ├─► 5. Navigation Deep-Linking
   │      - Dynamically generates one-click 2GIS pedestrian walking route URLs:
   │        `https://2gis.ru/routeSearch/rsType/pedestrian/from/<lng>,<lat>/to/<dest_lng>,<dest_lat>`
   │
   └─► 6. Result Delivery & UI Render
```

---

## 🧑‍💼 4. Talent Sourcing Engine ("Find Workers" Tab)

Directly accessible in the UI next to the scouted locations, the **Talent Sourcing Engine** connects location selection to active hiring.

1. **Category Mapping**: Translates business categories to localized Russian HeadHunter search queries:
   * *Restaurant* → `шеф-повар`, `повар`, `официант`, `управляющий рестораном`
   * *Coffee Shop* → `бариста`, `управляющий кофейней`, `кассир кофе`
   * *Bar / Nightclub* → `бармен`, `диджей`, `управляющий баром`
   * *Gym* → `персональный тренер`, `инструктор фитнес`, `администратор зал`
   * *Beauty Salon* → `парикмахер`, `косметолог`, `мастер маникюра`, `массажист`
   * *Supermarket / Retail* → `кассир`, `продавец продуктов`, `заведующий складом`
2. **Apify Cloud Scraping**: Invokes the `apify/web-scraper` actor using `APIFY_API_TOKEN` to execute a Headless Chromium browser against `hh.kz/search/resume`.
3. **Data Extraction**: Bypasses aggressive anti-bot firewalls to parse up to 5 verified candidates featuring:
   * Full Candidate Name & Age
   * Professional Title / Role
   * Verified Experience Duration
   * Stated Salary Expectation (in ₸ / KZT)
   * Direct hot-link to `hh.kz/resume/<id>` for immediate interview scheduling

---

## 🔒 5. Authentication & Demo Mode Gating

The application includes an identity and access management layer designed to support free trials while incentivizing user registration.

### Database Schema (`data/location_scout.db`)

#### `users` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | PRIMARY KEY AUTOINCREMENT | Unique user identifier |
| `name` | `TEXT` | NOT NULL | Full name |
| `phone_number` | `TEXT` | NOT NULL | Contact phone number |
| `email` | `TEXT` | UNIQUE, NOT NULL | Login email (case-insensitive) |
| `password_hash` | `TEXT` | NOT NULL | Salted bcrypt hash |
| `consent` | `INTEGER` | NOT NULL | GDPR / Privacy policy consent |

#### `search_logs` Table
| Column | Type | Constraints | Description |
|---|---|---|---|
| `id` | `INTEGER` | PRIMARY KEY AUTOINCREMENT | Unique log identifier |
| `ip_address` | `TEXT` | NOT NULL | Request client IP address |
| `cookie_id` | `TEXT` | NULLABLE | Persistent visitor UUID cookie (`demo_visitor_id`) |
| `timestamp` | `DATETIME` | DEFAULT CURRENT_TIMESTAMP | Execution timestamp |

### Gating Logic
* **Anonymous Visitors**:
  * Allowed **exactly 1 free demo search**.
  * Tracked by both IP address and persistent 1-year HTTP-only cookie (`demo_visitor_id`) to prevent trivial browser bypasses.
  * Only **Top 1 location** is returned.
  * Granular metrics (`traffic_score`, `competitor_gap`, `rent_affordable`, `avg_rent_kzt`, ROI analytics, and AI reports) are replaced with `"locked"` markers and blur overlays.
  * Subsequent searches trigger `HTTP 403 Forbidden` with `"Demo search limit reached. Please register or sign in."`
* **Authenticated Users**:
  * Receive an HTTP-only JWT session cookie (`session_token`) valid for 7 days.
  * **Unlimited searches** across both Business and Personal flows.
  * Full visibility into all Top-N results, sub-score breakdowns, exact prices, competitor lists, and AI reports.
  * Access to bookmark locations into browser `localStorage` favorites.

---

## 📡 6. Complete API Reference

Interactive Swagger/OpenAPI documentation is available at `/docs` and ReDoc at `/redoc`.

### Authentication & User Endpoints
| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/register` | Register new account (`name`, `phone_number`, `email`, `password`, `consent`) | No |
| `POST` | `/login` | Authenticate credentials (`email`, `password`) → sets `session_token` cookie | No |
| `POST` | `/logout` | Clears `session_token` cookie | Yes |
| `GET` | `/me` | Returns current user profile (`email`, `name`, `phone_number`) | Yes |

### Scout Agent Endpoints
| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/scout` | Commercial location scout orchestrator (gated for demo) | No (1 free search) |
| `POST` | `/scout/personal` | Residential apartment scout orchestrator (gated for demo) | No (1 free search) |
| `GET` | `/candidates` | Returns pre-configured candidate nodes for a city (e.g., Almaty) | No |

### Individual Modular Tool Endpoints
| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/tools/traffic` | Returns foot-traffic score (0-100) for a given `(lat, lng)` |
| `POST` | `/tools/competitors` | Returns nearby competitors and gap score within radius |
| `POST` | `/tools/rent` | Estimates monthly rent and calculates budget affordability |
| `POST` | `/tools/score` | Calculates weighted composite score from sub-metrics |
| `POST` | `/tools/krisha` | Directly scrapes Krisha.kz commercial listings |
| `POST` | `/tools/workers` | Executes Apify scraper against HeadHunter.kz |
| `GET` | `/health` | Liveness health check returning API status and version |

---

## 🧮 7. Scoring Models & Algorithms

### Business Location Scoring Formula
$$\text{Final Score} = (\text{Traffic} \times 0.35) + (\text{Competitor Gap} \times 0.25) + (\text{Rent Affordability} \times 0.20) + (\text{Demographics} \times 0.20)$$

* **Traffic Score (35%)**: Derived from 2GIS branch density in a 400m radius ($S = \min(100, \text{branches} / 3.5)$) or Google Maps Places count + review totals.
* **Competitor Gap (25%)**: Measures market vacancy in a 1,000m radius. $S = \max(0, 100 - \text{competitors} \times 5)$. Zero competitors yields 100/100; 20+ competitors yields 0/100.
* **Rent Affordability (20%)**: Compares average monthly rent to user budget. $S = \max(0, 100 \times (1 - \frac{\text{Rent} / \text{Budget}}{0.60}))$. Rent exceeding 60% of budget yields 0.
* **Demographics Fit (20%)**: Spatial matching against district income tiers (Medeu/Bostandyq = 85, Almaly/Auezov = 70, Alatau/Zhetysu/Turksib = 40) calibrated with property square meters.

### Student Apartment Scoring Formula
$$\text{Final Score} = (\text{Convenience} \times 0.30) + (\text{Safety} \times 0.30) + (\text{Lifestyle} \times 0.20) + (\text{Commute} \times 0.20)$$

* **Convenience (30%)**: Density of pharmacies, grocery stores, kindergartens, and transit within 1km.
* **Safety (30%)**: Density of police stations, civic facilities, and well-lit residential courtyards.
* **Lifestyle & Entertainment (20%)**: Density of student-friendly cafes, restaurants, and parks.
* **Commute & Proximity (20%)**: Haversine distance to campus. $S = \max(20, \min(100, 100 - \text{distance\_km} \times 5))$.

### Score Label Matrix
| Score Range | Classification | UI Badge Style |
|---|---|---|
| **85.0 – 100.0** | `Excellent` | Emerald Green gradient |
| **70.0 – 84.9** | `Good` | Royal Purple gradient |
| **55.0 – 69.9** | `Fair` | Golden Amber |
| **40.0 – 54.9** | `Below average` | Slate Gray |
| **0.0 – 39.9** | `Poor` | Rose Red |

---

## 📂 8. Repository Structure & File Inventory

```
location_scout/
├── main.py                      # Production entrypoint (Uvicorn host, port, reload config)
├── requirements.txt             # Pip dependency declarations
├── pyproject.toml               # Pytest and build metadata
├── .env                         # Active runtime environment credentials
├── .env.example                 # Template for API credentials
├── PROJECT_OVERVIEW.md          # Complete system documentation (this file)
├── SYSTEM_ARCHITECTURE.md       # High-level pipeline architecture notes
├── INSTRUCTIONS.md              # User manual & quickstart instructions
├── README.md                    # Summary repository overview
├── data/
│   ├── rent_data.csv            # Statistical fallback database (24 rows, 8 districts)
│   └── location_scout.db        # SQLite database (auto-generated for users & logs)
├── app/
│   ├── main.py                  # FastAPI application factory, CORS, static routes
│   ├── db.py                    # Database connection, migrations, auth, JWT, cookies
│   ├── agent/
│   │   ├── agent.py             # Commercial LocationScoutAgent orchestrator
│   │   ├── personal_agent.py    # Residential PersonalScoutAgent orchestrator
│   │   └── candidates.py        # Curated Almaty commercial hub coordinates
│   ├── models/
│   │   └── schemas.py           # Pydantic v2 schemas for all requests and responses
│   ├── routes/
│   │   └── router.py            # APIRouter definitions for auth, scout, and tools
│   ├── tools/
│   │   ├── google_maps.py       # 2GIS API integration (traffic, competitors, geocoding)
│   │   ├── krisha.py            # Live Krisha.kz scraper (commercial & apartments)
│   │   ├── personal_poi.py      # University geocoding, haversine, convenience/safety
│   │   ├── workers.py           # Apify HeadHunter scraper integration
│   │   ├── scoring.py           # Weighted formula calculations & labels
│   │   ├── rent.py              # Rent estimation (Krisha scraper -> CSV DB -> fallback)
│   │   ├── report.py            # Anthropic Claude API report & template fallback
│   │   ├── traffic.py           # Google Maps Places fallback / synthetic hash
│   │   ├── competitors.py       # OpenStreetMap Overpass API fallback
│   │   ├── census_data.py       # Almaty district demographic & income model
│   │   └── rent_usa.py          # US Census commercial rent multiplier model
│   └── static/
│       └── index.html           # Complete single-page frontend (HTML5/CSS3/Vanilla JS)
└── tests/
    ├── test_agent.py            # 16 tests: traffic, competitors, rent, scoring, agent
    └── test_auth_personal.py    # 4 tests: auth, bcrypt, demo limiting, personal scout
```

---

## 🔑 9. Environment Variables & Configuration

The application reads configuration from the `.env` file in the root directory:

| Variable | Required | Default | Description |
|---|---|---|---|
| `TWOGIS_API_KEY` | Recommended | Built-in fallback key | 2GIS Catalog API 3.0 key for foot traffic, POIs, and competitors |
| `APIFY_API_TOKEN` | Recommended | Built-in fallback token | Apify token to run headless Chromium scrapers on HeadHunter.kz |
| `ANTHROPIC_API_KEY` | Optional | `""` (Template used) | Anthropic key for Claude-generated narrative investment reports |
| `CLAUDE_MODEL` | Optional | `claude-opus-4-5` | Model name (`claude-opus-4-5`, `claude-3-7-sonnet`, `claude-3-5-haiku`) |
| `GOOGLE_MAPS_API_KEY` | Optional | `""` (Synthetic used) | Google Maps Places API key for global foot-traffic queries |
| `JWT_SECRET` | Optional | Default secret string | HMAC-SHA256 secret used to sign session cookies |
| `LOG_LEVEL` | Optional | `INFO` | Console log verbosity (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `PORT` | Optional | `8000` | Port for the Uvicorn web server |
| `ENVIRONMENT` | Optional | `dev` | Set to `prod` to disable live reload |

---

## 🧪 10. Test Suite & Verification

The test suite provides complete asynchronous coverage for both core scoring algorithms, external tool wrappers, database transactions, session authentication, and agent runtimes.

To execute all tests:
```bash
pytest tests/ -v
```

### Test Coverage Breakdown (20/20 Passing)
* **`tests/test_agent.py`**
  1. `test_synthetic_traffic_deterministic`: Verifies coordinate hash reproducibility.
  2. `test_synthetic_traffic_range`: Verifies traffic scores remain strictly between 0 and 100.
  3. `test_get_traffic_score_returns_required_keys`: Validates dict structure.
  4. `test_resolve_osm_types_coffee`: Tests amenity resolution for cafe categories.
  5. `test_resolve_osm_types_unknown`: Tests tag fallback behavior.
  6. `test_get_nearby_competitors_keys`: Checks competitor count and gap scores.
  7. `test_affordability_full_budget`: Tests boundary affordability when rent equals budget.
  8. `test_affordability_over_budget`: Tests boundary affordability when rent exceeds budget.
  9. `test_affordability_very_cheap`: Tests high affordability when rent is well below budget.
  10. `test_get_rent_estimate_keys`: Validates district matching and rent ranges.
  11. `test_score_location_formula`: Verifies math of the 35/25/20/20 weighted formula.
  12. `test_score_zero_inputs`: Verifies behavior at zero lower bound.
  13. `test_score_max_inputs`: Verifies behavior at 100 upper bound.
  14. `test_generate_report_no_api_key`: Verifies automatic fallback to rich markdown template.
  15. `test_agent_returns_top3`: End-to-end evaluation returning top 3 sorted locations.
  16. `test_agent_unknown_city_falls_back_to_almaty`: Verifies city fallback resilience.
* **`tests/test_auth_personal.py`**
  17. `test_password_hashing`: Verifies bcrypt salting, hashing, and password rejection.
  18. `test_user_registration_and_auth`: Verifies user insertion, retrieval, and unique email constraints.
  19. `test_demo_search_logging`: Verifies search logging and rate-limiting counts by IP/cookie.
  20. `test_personal_scout_full_vs_demo`: Verifies that anonymous users receive 1 locked property while authenticated users receive full unlocked scores, commute metrics, and 2GIS navigation routes.

---

## 🚀 11. Quickstart & Deployment Guide

### Local Development
```bash
# 1. Clone or open the repository
cd location_scout

# 2. Activate virtual environment (if present)
.\.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the server
python main.py
```
Open your browser at `http://localhost:8000`.

### Cloud Deployment (Render, Railway, Fly.io)
* **Start Command**: `python main.py` or `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
* **Port**: Bound dynamically via the `PORT` environment variable.
* **Volume**: Persistent disk recommended for `data/` to retain SQLite user accounts and search logs across deployments.
