import pytest

from app.engine._reference import load_crops, load_json
from app.engine.rotation import SEP, recommend_rotations
from app.engine.yield_estimation import estimate_yield, estimate_yield_details
from app.schemas.contracts import EnvironmentalFeatures

DB = load_crops()


def make(**over):
    base = dict(
        lat=31.11, lon=30.94, crop="wheat", field_size_ha=2.5, planting_date="2026-11-15",
        avg_temp_c=20.5, max_temp_c=28.5, total_precip_mm=3.0, avg_solar_rad=14.0,
        soil_moisture_root=0.55, soil_moisture_top=0.40, ndvi_current=0.55, ndvi_trend=0.02,
        forecast_precip_7d_mm=0.0, forecast_max_temp_c=25.0, forecast_et0_mm_day=3.1,
        irrigation_availability="available",
    )
    base.update(over)
    return EnvironmentalFeatures(**base)


NILE_WHEAT = make()
UPPER_MAIZE = make(lat=25.7, lon=32.6, crop="maize", planting_date="2026-06-01",
                   avg_temp_c=34.0, max_temp_c=42.0, total_precip_mm=0.0,
                   soil_moisture_root=0.25, soil_moisture_top=0.15, ndvi_current=0.6,
                   forecast_max_temp_c=43.0, forecast_et0_mm_day=8.0,
                   soil_texture="sandy_loam", irrigation_availability="limited")
STRESS = make(avg_temp_c=30.0, max_temp_c=38.0, total_precip_mm=0.0, soil_moisture_root=0.15,
              soil_moisture_top=0.08, ndvi_current=0.25, ndvi_trend=-0.12,
              forecast_max_temp_c=39.0, forecast_et0_mm_day=7.5, irrigation_availability="none")


def parse(opt):
    return opt.crop.split(SEP)


# ---------------------------------------------------------------- rotation
@pytest.mark.parametrize("f", [NILE_WHEAT, UPPER_MAIZE, STRESS])
def test_rotation_shape_and_validity(f):
    out = recommend_rotations(f)
    assert 1 <= len(out) <= 3
    scores = [o.score for o in out]
    assert scores == sorted(scores, reverse=True)
    for o in out:
        assert 0.0 <= o.score <= 1.0 and o.reason
        seq = parse(o)
        assert len(seq) == f.planning_horizon_seasons
        chain = [f.crop, *seq]
        assert all(a != b for a, b in zip(chain, chain[1:]))          # no back-to-back repeat
        for c in set(chain):
            assert not (DB[c]["no_repeat"] and chain.count(c) > 1)    # no_repeat crops


def test_nile_wheat_includes_a_legume():
    out = recommend_rotations(NILE_WHEAT)
    assert any("berseem_clover" in o.crop for o in out)


def test_no_irrigation_excludes_rice():
    for o in recommend_rotations(STRESS):
        assert "rice" not in parse(o)


def test_weights_change_ranking():
    soil = NILE_WHEAT.model_copy(update={"rotation_priority_weights": {
        "soil_health": 0.9, "water_demand": 0.03, "climate_suitability": 0.04, "rotation_diversity": 0.03}})
    water = NILE_WHEAT.model_copy(update={"rotation_priority_weights": {
        "soil_health": 0.03, "water_demand": 0.9, "climate_suitability": 0.04, "rotation_diversity": 0.03}})
    a, b = recommend_rotations(soil), recommend_rotations(water)
    assert [o.crop for o in a] != [o.crop for o in b]

    def avg_water(o):
        s = parse(o)
        return sum(DB[c]["water_req_mm"] for c in s) / len(s)
    assert avg_water(b[0]) <= avg_water(a[0])


def test_unknown_current_crop_does_not_crash():
    assert recommend_rotations(make(crop="quinoa"))


# ------------------------------------------------------------------- yield
def test_yield_never_high_and_in_range_for_normal_case():
    est, conf, note = estimate_yield(NILE_WHEAT)
    assert conf in ("Low", "Medium") and "not a trained model" in note
    d = estimate_yield_details(NILE_WHEAT)
    assert d["in_range"] or conf == "Low"


def test_stress_raises_risk_not_the_number():
    # estimate is the plain historical median; stress only changes the risk flag
    normal, _, _ = estimate_yield(NILE_WHEAT)
    stressed, conf, note = estimate_yield(STRESS)
    assert stressed == normal == load_json("yield_baseline.json")["wheat"]["median_kg_ha"]
    assert estimate_yield_details(STRESS)["risk"] == "High"
    assert estimate_yield_details(NILE_WHEAT)["risk"] == "Low"
    assert conf == "Low" and "stress risk: High" in note


def test_missing_baseline_returns_low_zero():
    est, conf, note = estimate_yield(make(crop="berseem_clover"))
    assert est == 0.0 and conf == "Low" and "No estimate" in note


def test_out_of_range_input_is_low():
    _, conf, note = estimate_yield(make(ndvi_current=5.0))
    assert conf == "Low" and "ndvi_current" in note


def test_yield_confidence_is_low_for_national_baseline():
    estimate, confidence, note = estimate_yield(NILE_WHEAT)
    assert estimate == load_json("yield_baseline.json")["wheat"]["median_kg_ha"]
    assert confidence == "Low"
    assert "national median benchmark" in note
    assert "not a field-level prediction" in note
