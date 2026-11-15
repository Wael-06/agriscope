import pytest

from app.engine._reference import load_crops, load_json
from app.engine.rotation import SEP, recommend_rotations, score_baseline_rotation
from app.engine.yield_estimation import estimate_yield
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


def test_baseline_score_uses_previous_and_current_crop():
    legume_baseline = score_baseline_rotation(NILE_WHEAT.model_copy(
        update={"previous_crop": "berseem_clover"}
    ))
    repeated_crop_baseline = score_baseline_rotation(NILE_WHEAT.model_copy(
        update={"previous_crop": "wheat"}
    ))
    assert legume_baseline is not None
    assert repeated_crop_baseline is not None
    assert 0.0 <= legume_baseline <= 1.0
    assert legume_baseline > repeated_crop_baseline


def test_baseline_score_is_omitted_without_supported_crop_history():
    assert score_baseline_rotation(NILE_WHEAT) is None
    assert score_baseline_rotation(NILE_WHEAT.model_copy(
        update={"previous_crop": "quinoa"}
    )) is None


def test_unknown_current_crop_does_not_crash():
    assert recommend_rotations(make(crop="quinoa"))


# ------------------------------------------------------------------- yield
def test_yield_model_returns_positive_kg_ha():
    est, conf, note = estimate_yield(NILE_WHEAT)
    assert est > 1000.0
    assert conf in ("Low", "Medium")
    assert "Random Forest" in note


def test_yield_model_handles_upper_egypt_maize():
    est, conf, note = estimate_yield(UPPER_MAIZE)
    assert est > 1000.0
    assert conf in ("Low", "Medium")


def test_unknown_crop_returns_zero_low_confidence():
    est, conf, note = estimate_yield(make(crop="berseem_clover"))
    assert est == 0.0
    assert conf == "Low"
    assert "not in the trained yield model" in note


@pytest.mark.parametrize(
    ("lat", "lon", "crop", "country"),
    [
        (42.03, -93.62, "maize", "USA"),
        (34.75, 113.62, "wheat", "CHINA"),
    ],
)
def test_country_yield_benchmarks(lat, lon, crop, country):
    estimate, confidence, note = estimate_yield(
        make(lat=lat, lon=lon, crop=crop)
    )
    assert estimate > 0
    assert confidence in ("Low", "Medium")
    assert f"{country if country == 'USA' else 'China'} national benchmark" in note


@pytest.mark.parametrize(
    ("lat", "lon", "crop"),
    [
        (42.03, -93.62, "date_palm"),
        (34.75, 113.62, "sugarcane"),
    ],
)
def test_country_benchmark_crop_keys_are_mapped(lat, lon, crop):
    estimate, _, note = estimate_yield(make(lat=lat, lon=lon, crop=crop))
    assert estimate > 0
    assert "national benchmark" in note


def test_unmodeled_location_uses_low_confidence_climate_soil_heuristic():
    estimate, confidence, note = estimate_yield(
        make(
            lat=0.0,
            lon=0.0,
            crop="maize",
            avg_temp_c=27.0,
            max_temp_c=35.0,
            total_precip_mm=80.0,
            soil_moisture_root=0.6,
            soil_texture="loam",
            irrigation_availability="limited",
        )
    )
    assert estimate > 0
    assert confidence == "Low"
    assert "heuristic estimate" in note
    assert "not a locally validated model" in note


def test_unmodeled_location_estimate_falls_under_severe_heat_stress():
    normal, _, _ = estimate_yield(make(lat=0.0, lon=0.0, crop="maize"))
    heat_stressed, _, _ = estimate_yield(
        make(lat=0.0, lon=0.0, crop="maize", avg_temp_c=40.0, max_temp_c=50.0)
    )
    assert 0 < heat_stressed < normal


def test_unmodeled_location_without_crop_baseline_is_reported():
    estimate, confidence, note = estimate_yield(
        make(lat=0.0, lon=0.0, crop="berseem_clover")
    )
    assert estimate == 0.0
    assert confidence == "Low"
    assert "no estimate was generated" in note
