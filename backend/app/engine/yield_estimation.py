"""Transparent national yield benchmark with environmental stress risk indicators.

Returns the published national median yield (kg/ha) from yield_baseline.json without
pretending to produce field-level ML predictions from national annual labels.
"""
from __future__ import annotations

from app.engine._reference import load_json
from app.schemas.contracts import EnvironmentalFeatures

_ALIASES = {
    "rice_paddy": "rice",
    "paddy": "rice",
    "tomatoes": "tomato",
    "cotton_seed": "cotton",
}

_HEAT_C = {
    "wheat": 34.0,
    "maize": 35.0,
    "rice": 35.0,
    "tomato": 32.0,
    "cotton": 38.0,
}


def _key(name: str) -> str:
    k = name.strip().lower().replace(" ", "_").replace(",", "")
    return _ALIASES.get(k, k)


def _check_ranges(features: EnvironmentalFeatures) -> list[str]:
    bad: list[str] = []
    if not -1.0 <= features.ndvi_current <= 1.0:
        bad.append(f"ndvi_current ({features.ndvi_current}) outside [-1.0, 1.0]")
    if not 0.0 <= features.soil_moisture_root <= 1.0:
        bad.append(f"soil_moisture_root ({features.soil_moisture_root}) outside [0.0, 1.0]")
    if not 0.0 <= features.soil_moisture_top <= 1.0:
        bad.append(f"soil_moisture_top ({features.soil_moisture_top}) outside [0.0, 1.0]")
    if not -60.0 <= features.avg_temp_c <= 65.0:
        bad.append(f"avg_temp_c ({features.avg_temp_c}) outside [-60, 65]")
    return bad


def estimate_yield_details(features: EnvironmentalFeatures) -> dict:
    base = load_json("yield_baseline.json")
    crop = _key(features.crop)
    b = base.get(crop)
    if not b or b.get("n_years", 0) == 0:
        note = (
            f"No estimate available: no yield history for '{features.crop}' in reference data "
            "(national median benchmark only, not a trained model or field-level prediction)."
        )
        return {
            "estimate_kg_ha": 0.0,
            "confidence": "Low",
            "risk": "Unknown",
            "flags": [],
            "in_range": True,
            "note": note,
        }

    est = float(b.get("median_kg_ha") or b.get("recent_mean_kg_ha") or 0.0)
    range_issues = _check_ranges(features)
    in_range = len(range_issues) == 0

    flags: list[str] = []
    if features.max_temp_c >= _HEAT_C.get(crop, 35.0):
        flags.append("heat stress")
    if features.ndvi_trend < -0.05:
        flags.append("falling NDVI")
    if features.irrigation_availability == "none" and features.soil_moisture_root < 0.30:
        flags.append("dry root zone without irrigation")
    if (
        features.et0_mm_day
        and features.aeti_mm_day is not None
        and features.et0_mm_day > 0
        and (features.aeti_mm_day / features.et0_mm_day) < 0.70
    ):
        flags.append("evapotranspiration deficit")

    risk = "High" if len(flags) >= 2 else "Moderate" if flags else "Low"
    conf = "Low"

    note = (
        f"Based on a national median benchmark ({est:.0f} kg/ha across {b['n_years']} years), "
        "not a trained model and not a field-level prediction. "
        f"Current stress risk: {risk}"
        + (f" ({', '.join(flags)})." if flags else ".")
    )
    if range_issues:
        note += f" Input check warning: {'; '.join(range_issues)}."

    return {
        "estimate_kg_ha": round(est, 1),
        "confidence": conf,
        "risk": risk,
        "flags": flags,
        "in_range": in_range,
        "note": note,
    }


def estimate_yield(features: EnvironmentalFeatures) -> tuple[float, str, str]:
    d = estimate_yield_details(features)
    return d["estimate_kg_ha"], d["confidence"], d["note"]
