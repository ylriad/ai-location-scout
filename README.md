# 🏙️ AI Business & Residential Location Scout

> 📖 **Comprehensive Documentation**: See [PROJECT_OVERVIEW.md](file:///c:/Antigravity/location_scout/PROJECT_OVERVIEW.md) for the full end-to-end breakdown of the current version (v1.0.0), including the Student/Personal Housing Scout, SQLite authentication & demo gating, 2GIS spatial maps, Krisha.kz scraper, and HeadHunter talent sourcing.

An intelligent FastAPI agent that evaluates commercial real-estate and residential housing locations using
foot-traffic data, competitor analysis, rent estimates, and demographic fit — then
generates an AI-written investment report via Claude.

## Quick Start

```bash
# 1. Clone / enter the project
cd location_scout

# 2. Copy and fill in your API keys
copy .env.example .env
# Edit .env → add GOOGLE_MAPS_API_KEY and ANTHROPIC_API_KEY

# 3. Install dependencies
py -3.13 -m pip install -r requirements.txt

# 4. Run the server
py -3.13 main.py
# → http://localhost:8000/docs
```

> **Works without API keys!**
> All tools have smart fallbacks — synthetic traffic scores, Overpass OSM queries,
> and a template-based report — so the full pipeline runs in demo mode out of the box.

---

## 🚀 Deploy to Render

This repository includes a `render.yaml` Blueprint file for one-click, zero-config deployment on [Render](https://render.com).

### Option 1: Blueprint Deployment (Recommended)
1. Go to your [Render Dashboard](https://dashboard.render.com).
2. Click **New +** → **Blueprint**.
3. Select this repository (`ylriad/business-ai-agent` or `ai-location-scout`).
4. Render will automatically configure the build and start commands, Python 3.11.9 runtime, and generate a secure `JWT_SECRET`.
5. Click **Apply**.

### Option 2: Manual Web Service
- **Runtime**: Python
- **Build Command**: `pip install --upgrade pip && pip install -r requirements.txt`
- **Start Command**: `python main.py`
- **Environment Variables**:
  - `PYTHON_VERSION`: `3.11.9`
  - `ENVIRONMENT`: `prod`

---

## Project Structure

```
location_scout/
├── main.py                      # Uvicorn entrypoint
├── requirements.txt
├── pyproject.toml
├── .env.example                 # API key template
├── data/
│   └── rent_data.csv            # Almaty commercial rent DB (24 rows, 8 districts)
├── app/
│   ├── main.py                  # FastAPI app factory
│   ├── models/
│   │   └── schemas.py           # Pydantic request/response models
│   ├── agent/
│   │   ├── agent.py             # LocationScoutAgent (orchestrator)
│   │   └── candidates.py        # 10 Almaty candidate locations
│   ├── tools/
│   │   ├── traffic.py           # get_traffic_score   (Google Maps / synthetic)
│   │   ├── competitors.py       # get_nearby_competitors (Overpass OSM)
│   │   ├── rent.py              # get_rent_estimate   (CSV + distance model)
│   │   ├── scoring.py           # score_location      (weighted formula)
│   │   └── report.py            # generate_report     (Claude API / template)
│   └── routes/
│       └── router.py            # All FastAPI endpoints
└── tests/
    └── test_agent.py            # pytest-asyncio test suite
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/health` | Liveness probe |
| `POST` | `/scout` | **Main agent** — runs full pipeline |
| `GET`  | `/candidates?city=Almaty` | List candidate locations |
| `POST` | `/tools/traffic` | Individual: foot-traffic score |
| `POST` | `/tools/competitors` | Individual: nearby competitor count |
| `POST` | `/tools/rent` | Individual: rent estimate |
| `POST` | `/tools/score` | Individual: weighted scorer |

Interactive docs: **http://localhost:8000/docs**

---

## Agent Pipeline

```
ScoutRequest (business_type, city, budget, target_audience)
      │
      ▼
 get_candidates(city)          ← 10 Almaty locations
      │
      ▼  [parallel for each candidate]
 ┌────────────────────────────────────────┐
 │  get_traffic_score(lat, lng)           │  → 0-100
 │  get_nearby_competitors(lat, lng)      │  → count + gap score
 │  get_rent_estimate(address, budget)    │  → USD + affordability
 └────────────────────────────────────────┘
      │
      ▼
 score_location(factors)
   traffic×0.35 + gap×0.25 + rent×0.20 + demographics×0.20
      │
      ▼
 sort → top 3
      │
      ▼
 generate_report(top3)         ← Claude API or rich template
      │
      ▼
 ScoutResult (scores + report_md + ROI estimates)
```

---

## Scoring Formula

| Factor | Weight | Source |
|--------|--------|--------|
| `traffic_score` | **35%** | Google Maps Places Nearby API |
| `competitor_gap` | **25%** | OpenStreetMap Overpass API |
| `rent_affordable` | **20%** | CSV DB / distance-from-CBD model |
| `demographics_fit` | **20%** | Heuristic (audience × district) |

---

## Example Request

```bash
curl -X POST http://localhost:8000/scout \
  -H "Content-Type: application/json" \
  -d '{
    "business_type": "coffee shop",
    "city": "Almaty",
    "budget": 10000,
    "target_audience": "young professionals",
    "top_n": 3
  }'
```

---

## Running Tests

```bash
py -3.13 -m pytest tests/ -v
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_MAPS_API_KEY` | Optional | Enables real foot-traffic data |
| `ANTHROPIC_API_KEY` | Optional | Enables Claude-generated reports |
| `CLAUDE_MODEL` | Optional | Default: `claude-opus-4-5` |
| `LOG_LEVEL` | Optional | Default: `INFO` |
