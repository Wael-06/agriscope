from tests.test_irrigation import feats
from app.engine.yield_estimation import estimate_yield
from app.engine.climatology import fallback_forecast

def test_wheat_baseline():
    y, conf, note = estimate_yield(feats())
    assert 6000 < y < 7500 and conf == "Medium" and "not a trained model" in note

def test_tomato_low_and_cotton_none():
    assert estimate_yield(feats(crop="tomato"))[1] == "Low"
    assert estimate_yield(feats(crop="cotton"))[1] == "Not available"

def test_stress_downgrades():
    _, conf, note = estimate_yield(feats(max_temp_c=38, ndvi_trend=-0.2))
    assert conf == "Low" and "Elevated" in note

def test_fallback_nearest_site():
    f = fallback_forecast(30.8, 31.0, 1)
    assert "nile_delta" in f["_source"] and f["forecast_et0_mm_day"] > 0
