import pytest
from app.i18n.terms import get_business_type_key, get_search_ru, get_display_label
from app.tools.scoring import SCORE_LABELS, _label, score_location

def test_resolve_business_type_all_langs():
    # Same business type resolving to the same canonical key
    assert get_business_type_key("coffee shop") == "coffee shop"
    assert get_business_type_key("кофейня") == "coffee shop"
    assert get_business_type_key("кофехана") == "coffee shop"

def test_resolve_business_type_typos():
    # Typos and transliteration variants
    assert get_business_type_key("kofe shop") == "coffee shop"
    assert get_business_type_key("кофе шоп") == "coffee shop"
    
def test_search_ru_resolves_correctly():
    # Canonical key yields the exact same Russian search term
    assert get_search_ru("coffee shop", "business_type") == "кофейня"
    assert get_search_ru("restaurant", "business_type") == "ресторан"
    
def test_score_label_all_langs():
    # Test that score-label dict returns correct strings
    assert _label(85, "en") == "Excellent"
    assert _label(70, "en") == "Good"
    assert _label(55, "en") == "Fair"
    assert _label(40, "en") == "Below average"
    assert _label(0, "en") == "Poor"

@pytest.mark.asyncio
async def test_score_location_regression():
    # Regression check that the numeric score threshold logic is byte-for-byte unchanged
    factors = {
        "traffic_score":    80,
        "competitor_gap":   60,
        "rent_affordable":  70,
        "demographics_fit": 90,
    }
    result_en = await score_location(factors, lang="en")
    result_ru = await score_location(factors, lang="ru")
    
    expected = 80*0.35 + 60*0.25 + 70*0.20 + 90*0.20
    assert abs(result_en["final_score"] - expected) < 0.01
    assert result_en["final_score"] == result_ru["final_score"]
    
    # Also verify labels are translated properly on the exact same score
    assert result_en["label"] == "Good"
    assert result_ru["label"] == _label(result_ru["final_score"], "ru")


def test_report_prompt_lang_instruction():
    from app.tools.report import _build_prompt
    sample_locs = [{"name": "Loc 1", "lat": 43.25, "lng": 76.92}]
    
    prompt_en = _build_prompt(sample_locs, "coffee shop", "Almaty", 100000, 50, lang="en")
    assert "CRITICAL REQUIREMENT: Write the entire report in English." in prompt_en
    
    prompt_ru = _build_prompt(sample_locs, "coffee shop", "Almaty", 100000, 50, lang="ru")
    assert "CRITICAL REQUIREMENT: Write the entire report in Russian" in prompt_ru
    
    prompt_kk = _build_prompt(sample_locs, "coffee shop", "Almaty", 100000, 50, lang="kk")
    assert "CRITICAL REQUIREMENT: Write the entire report in Kazakh" in prompt_kk

