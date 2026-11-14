from datetime import date
import pytest
from app.schemas.contracts import EnvironmentalFeatures
from app.engine.irrigation import compute_irrigation, compute_irrigation_detail

def feats(**kw):
    base = dict(lat=31.11, lon=30.94, crop="wheat", field_size_ha=2.5,
                planting_date="2026-11-15", avg_temp_c=20, max_temp_c=27,
                total_precip_mm=10, avg_solar_rad=14, soil_moisture_root=0.5,
                soil_moisture_top=0.4, ndvi_current=0.5, ndvi_trend=0.05,
                forecast_precip_7d_mm=0.0, forecast_max_temp_c=25,
                forecast_et0_mm_day=4.2, irrigation_availability="available")
    base.update(kw); return EnvironmentalFeatures(**base)

def test_midseason_matches_plan_example():
    d = compute_irrigation_detail(feats(), today=date(2027, 1, 20))  # day 66 = mid-season
    assert d.growth_stage == "mid-season" and d.kc == 1.15
    assert d.etc_mm_day == pytest.approx(4.83, abs=0.01)   # UI spec example
    assert d.irrigation_mm_per_week == pytest.approx(7*4.83/0.75, abs=0.2)

def test_initial_stage_low_demand():
    d = compute_irrigation_detail(feats(), today=date(2026, 11, 20))
    assert d.growth_stage == "initial" and d.irrigation_mm_per_week < 40

def test_rain_reduces_need_and_never_negative():
    d = compute_irrigation_detail(feats(forecast_precip_7d_mm=200), today=date(2027, 1, 20))
    assert d.irrigation_mm_per_week == 0.0

def test_limited_needs_more_gross_water():
    a = compute_irrigation_detail(feats(), today=date(2027, 1, 20))
    b = compute_irrigation_detail(feats(irrigation_availability="limited"), today=date(2027, 1, 20))
    assert b.irrigation_mm_per_week > a.irrigation_mm_per_week

def test_rainfed_flag():
    d = compute_irrigation_detail(feats(irrigation_availability="none"), today=date(2027, 1, 20))
    assert d.rainfed and d.irrigation_mm_per_week == 0 and d.next_irrigation_date == ""

def test_dry_soil_means_sooner():
    wet = compute_irrigation_detail(feats(soil_moisture_root=0.9), today=date(2027, 1, 20))
    dry = compute_irrigation_detail(feats(soil_moisture_root=0.2), today=date(2027, 1, 20))
    assert dry.days_to_next <= wet.days_to_next

def test_all_crops_and_unknown():
    for c in ["wheat","maize","rice","cotton","berseem clover","tomato"]:
        out = compute_irrigation(feats(crop=c))
        assert out[0] >= 0 and len(out[1]) == 10
    with pytest.raises(ValueError):
        compute_irrigation(feats(crop="banana"))
