"""
Tool: generate_report
Calls the Anthropic Claude API to produce a polished, human-readable analysis
of the top 3 ranked locations, including ROI estimates.

Falls back to a rich template-based report when the API key is absent.
"""

import logging
import os

import anthropic

logger = logging.getLogger(__name__)

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL      = os.getenv("CLAUDE_MODEL", "claude-opus-4-5")


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_prompt(
    top3:           list[dict],
    business_type:  str,
    city:           str,
    budget:         float,
    area_size:      int,
    lang:           str = "en",
) -> str:
    location_blocks = []
    for idx, loc in enumerate(top3, 1):
        score_info = loc.get("score_result", {})
        rent_info  = loc.get("rent_result",  {})
        traffic    = loc.get("traffic_result", {})
        comp       = loc.get("competitor_result", {})

        block = f"""
### Location #{idx}: {loc.get('name', 'Unnamed')}
- **Address**: {loc.get('address', 'N/A')}
- **Coordinates**: ({loc.get('lat')}, {loc.get('lng')})
- **Final Score**: {score_info.get('final_score', 'N/A')}/100 ({score_info.get('label', '')})
- **Score Breakdown**:
  - Traffic Score: {score_info.get('breakdown', {}).get('traffic_score', {}).get('raw', 'N/A')}/100 (weight 35%)
  - Competitor Gap: {score_info.get('breakdown', {}).get('competitor_gap', {}).get('raw', 'N/A')}/100 (weight 25%)
  - Rent Affordability: {score_info.get('breakdown', {}).get('rent_affordable', {}).get('raw', 'N/A')}/100 (weight 20%)
  - Demographics Fit: {score_info.get('breakdown', {}).get('demographics_fit', {}).get('raw', 'N/A')}/100 (weight 20%)
- **Est. Monthly Rent**: {rent_info.get('avg_rent_kzt', 'N/A')} KZT (range {rent_info.get('min_rent_kzt', 'N/A')}–{rent_info.get('max_rent_kzt', 'N/A')} KZT)
- **Nearby Competitors**: {comp.get('count', 'N/A')} within {comp.get('radius_m', 1000)} m
- **Foot Traffic score**: {traffic.get('score', 'N/A')}/100 ({traffic.get('source', '')})
"""
        location_blocks.append(block)

    locations_text = "\n".join(location_blocks)

    lang_code = lang.lower() if lang else "en"
    if lang_code == "ru":
        lang_instruction = "CRITICAL REQUIREMENT: Write the entire report in Russian (на русском языке)."
    elif lang_code == "kk":
        lang_instruction = "CRITICAL REQUIREMENT: Write the entire report in Kazakh (қазақ тілінде)."
    else:
        lang_instruction = "CRITICAL REQUIREMENT: Write the entire report in English."

    return f"""You are a senior business analytics consultant specialising in retail and hospitality site selection in Central Asia.

A client wants to open a **{business_type}** in **{city}**.
- **Monthly budget**: {budget} KZT
- **Desired properties size**: {area_size} m²

Below are the top 3 candidate locations scored by our AI location-scout system:

{locations_text}

{lang_instruction}

Please write a concise yet comprehensive business report (600–900 words) covering:

1. **Executive Summary** – which location is the best pick and why.
2. **Foot Traffic & Competitors (Google Maps)** – analyse how the proxy reviews and competitor distance affects viability.
3. **Demographics & Rent (US Census)** – weigh the population & income density vs the proxy commercial rent.
4. **ROI Estimates** – for each location provide a rough 12-month ROI projection:
   - Assume average daily covers = traffic_score × 0.8 customers, average spend 2500 KZT.
   - Monthly revenue = daily_covers × 30 × avg_spend_kzt
   - Monthly costs = rent + 40% of revenue (COGS, staff, utilities)
   - Monthly profit = revenue – costs
   - Annual ROI % = (annual_profit / budget) × 100
4. **Final Recommendation** – decisive one-paragraph recommendation with the top location.

Write in a professional, confident tone suitable for an investor deck.
Use markdown headers and bullet points for clarity.
"""


# ---------------------------------------------------------------------------
# Fallback template
# ---------------------------------------------------------------------------

def _template_report(
    top3:            list[dict],
    business_type:   str,
    city:            str,
    budget:          float,
    area_size:       int,
    lang:            str = "en",
) -> str:
    lines = [
        f"# Business Location Scout Report",
        f"**Business Type**: {business_type}  |  **City**: {city}  |  "
        f"**Budget**: {budget} KZT/mo  |  **Area Size**: {area_size} m²",
        "",
        "---",
        "",
        "## Top 3 Recommended Locations",
        "",
    ]
    for idx, loc in enumerate(top3, 1):
        sr  = loc.get("score_result", {})
        rr  = loc.get("rent_result",  {})
        tr  = loc.get("traffic_result", {})
        cr  = loc.get("competitor_result", {})
        bd  = sr.get("breakdown", {})

        # Simple ROI calc
        traffic_score = tr.get("score", 50)
        daily_covers  = traffic_score * 0.8
        avg_spend_kzt = 2500
        monthly_rev   = daily_covers * 30 * avg_spend_kzt
        rent          = rr.get("avg_rent_kzt", budget * 0.25)
        monthly_cost  = rent + 0.40 * monthly_rev
        monthly_profit = monthly_rev - monthly_cost
        annual_roi     = ((monthly_profit * 12) / budget * 100) if budget else 0

        lines += [
            f"### #{idx} – {loc.get('name', 'Location')} (Score: {sr.get('final_score', 'N/A')}/100 – {sr.get('label', '')})",
            f"**Address**: {loc.get('address', 'N/A')}",
            "",
            "| Factor | Score | Weight |",
            "|--------|-------|--------|",
            f"| 🚶 Foot Traffic | {bd.get('traffic_score',{}).get('raw','N/A')}/100 | 35% |",
            f"| 🏪 Competitor Gap | {bd.get('competitor_gap',{}).get('raw','N/A')}/100 | 25% |",
            f"| 💰 Rent Affordability | {bd.get('rent_affordable',{}).get('raw','N/A')}/100 | 20% |",
            f"| 👥 Demographics Fit | {bd.get('demographics_fit',{}).get('raw','N/A')}/100 | 20% |",
            "",
            f"**Rent**: ~{rr.get('avg_rent_kzt','N/A')} KZT/mo  |  "
            f"**ROI**: {annual_roi:.1f}%\n"
            f"**Foot Traffic**: {bd.get('traffic_score',{}).get('raw',0)}/100, "
            f"**Competitor Gap**: {bd.get('competitor_gap',{}).get('raw',0)}/100, "
            f"**Demographics Fit**: {bd.get('demographics_fit',{}).get('raw',0)}/100\n\n"
            f"- Monthly revenue: {monthly_rev:,.0f} KZT\n"
            f"- Monthly costs (rent + ops): {monthly_cost:,.0f} KZT\n"
            f"- Monthly profit: {monthly_profit:,.0f} KZT\n",
            f"- **Annual ROI: {annual_roi:.1f}%**",
            "",
            "---",
            "",
        ]

    lines.append(
        f"*Report generated by LocationScoutAgent. "
        f"Scores are AI-derived estimates; perform on-site due diligence before investing.*"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def generate_report(
    top3_locations:  list[dict],
    business_type:   str   = "coffee shop",
    city:            str   = "Almaty",
    budget:          float = 10_000,
    area_size:       int   = 50,
    lang:            str   = "en",
) -> dict:
    """
    Returns:
      - report_md : str    full markdown report
      - source    : 'claude' | 'template'
    """
    if not ANTHROPIC_API_KEY:
        logger.warning("ANTHROPIC_API_KEY not set – using template-based report.")
        report = _template_report(top3_locations, business_type, city, budget, area_size, lang=lang)
        return {"report_md": report, "source": "template"}

    try:
        client  = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        prompt  = _build_prompt(top3_locations, business_type, city, budget, area_size, lang=lang)
        message = client.messages.create(
            model       = CLAUDE_MODEL,
            max_tokens  = 2048,
            messages    = [{"role": "user", "content": prompt}],
        )
        report = message.content[0].text
        return {"report_md": report, "source": "claude"}

    except Exception as exc:
        logger.error("Claude API error: %s – falling back to template.", exc)
        report = _template_report(top3_locations, business_type, city, budget, area_size, lang=lang)
        return {"report_md": report, "source": "template_fallback"}
