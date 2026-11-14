from tests.test_irrigation import feats
from app.engine.yield_estimation import estimate_yield
from app.engine.climatology import fallback_forecast


def test_wheat_model_prediction():
    y, conf, note = estimate_yield(feats())
    assert y > 1000 and conf in ("Low", "Medium") and "Random Forest" in note


def test_tomato_and_unknown_crop():
    y_tom, conf_tom, _ = estimate_yield(feats(crop="tomato"))
    assert y_tom > 1000 and conf_tom in ("Low", "Medium")
    y_unk, conf_unk, note_unk = estimate_yield(feats(crop="berseem_clover"))
    assert y_unk == 0.0 and conf_unk == "Low" and "not in the trained yield model" in note_unk


def test_far_location_downgrades_confidence():
    _, conf, _ = estimate_yield(feats(lat=22.0, lon=28.0))
    assert conf == "Low"


def test_fallback_nearest_site():
    f = fallback_forecast(30.8, 31.0, 1)
    assert "nile_delta" in f["_source"] and f["forecast_et0_mm_day"] > 0
