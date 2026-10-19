"""
Tool: score_location
Applies the weighted scoring formula:

  final_score = (
      traffic_score   * 0.35
    + competitor_gap  * 0.25
    + rent_affordable * 0.20
    + demographics_fit* 0.20
  )

All sub-scores are expected in the range 0–100.
The result is also 0–100.
"""

import logging

logger = logging.getLogger(__name__)

WEIGHTS = {
    "traffic_score":    0.35,
    "competitor_gap":   0.25,
    "rent_affordable":  0.20,
    "demographics_fit": 0.20,
}

SCORE_LABELS = [
    (85, {"en": "Excellent",     "ru": "Отлично",       "kk": "Өте жақсы"}),
    (70, {"en": "Good",          "ru": "Хорошо",        "kk": "Жақсы"}),
    (55, {"en": "Fair",          "ru": "Средне",        "kk": "Орташа"}),
    (40, {"en": "Below average", "ru": "Ниже среднего", "kk": "Орташадан төмен"}),
    (0,  {"en": "Poor",          "ru": "Низкая оценка", "kk": "Төмен"}),
]


def _label(score: float, lang: str = "en") -> str:
    lang = lang.lower() if lang else "en"
    if lang not in ["en", "ru", "kk"]:
        lang = "en"
    for threshold, labels in SCORE_LABELS:
        if score >= threshold:
            return labels[lang]
    return SCORE_LABELS[-1][1][lang]


def _estimate_demographics_fit(
    area_size: int,
    district: str,
) -> float:
    """
    Lightweight heuristic: maps (area_size, district) pairs to a 0-100 fit.
    Extend this with real census data when available.
    """
    dist = district.lower()
    
    # Larger areas better suited for suburban/residential
    if area_size >= 100:
        suburban = ["auezov", "alatau", "nauryzbay"]
        return 85.0 if any(d in dist for d in suburban) else 60.0

    # Smaller areas (boutiques/coffee) better suited for central
    if area_size <= 50:
        central = ["medeu", "almaly", "bostandyq"]
        return 85.0 if any(d in dist for d in central) else 60.0

    # Default neutral
    return 60.0


async def score_location(factors: dict, lang: str = "en") -> dict:
    """
    Parameters
    ----------
    factors : dict
        Required keys:
          traffic_score    : float (0-100)
          competitor_gap   : float (0-100)
          rent_affordable  : float (0-100)
        Optional keys:
          demographics_fit : float (0-100)  – auto-estimated if absent
          area_size        : int  – used for demographics estimation
          district         : str  – used for demographics estimation

    Returns
    -------
    dict with final_score, breakdown, label, explanation
    """
    traffic    = float(factors.get("traffic_score",    50))
    comp_gap   = float(factors.get("competitor_gap",   50))
    rent_aff   = float(factors.get("rent_affordable",  50))
    demo_fit   = float(
        factors.get(
            "demographics_fit",
            _estimate_demographics_fit(
                factors.get("area_size", 50),
                factors.get("district", "Unknown"),
            ),
        )
    )

    final = (
        traffic  * WEIGHTS["traffic_score"]
      + comp_gap * WEIGHTS["competitor_gap"]
      + rent_aff * WEIGHTS["rent_affordable"]
      + demo_fit * WEIGHTS["demographics_fit"]
    )
    final = round(final, 2)

    breakdown = {
        "traffic_score":    {"raw": traffic,  "weighted": round(traffic  * WEIGHTS["traffic_score"],    2)},
        "competitor_gap":   {"raw": comp_gap, "weighted": round(comp_gap * WEIGHTS["competitor_gap"],   2)},
        "rent_affordable":  {"raw": rent_aff, "weighted": round(rent_aff * WEIGHTS["rent_affordable"],  2)},
        "demographics_fit": {"raw": demo_fit, "weighted": round(demo_fit * WEIGHTS["demographics_fit"], 2)},
    }

    return {
        "final_score": final,
        "label":       _label(final, lang),
        "breakdown":   breakdown,
        "weights":     WEIGHTS,
        "explanation": (
            f"Final score {final}/100 ({_label(final, lang)}). "
            f"Traffic: {traffic}×0.35={breakdown['traffic_score']['weighted']}, "
            f"CompetitorGap: {comp_gap}×0.25={breakdown['competitor_gap']['weighted']}, "
            f"Rent: {rent_aff}×0.20={breakdown['rent_affordable']['weighted']}, "
            f"Demographics: {demo_fit}×0.20={breakdown['demographics_fit']['weighted']}."
        ),
    }
