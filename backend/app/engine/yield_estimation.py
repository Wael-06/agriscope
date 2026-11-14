"""DRAFT for Yassin: transparent baseline yield, built from the supplied national yield history.

estimate = mean of the last 5 years of national yield for that crop (kg/ha).
The weather-based flags below do NOT change the number; they only feed a risk indicator.
Why: in leave-one-year-out tests on this data, adding temperature/rain to a trend or a plain
mean gave no improvement (see build_reference.py), so a weather-adjusted number would be fake precision.
"""
import json
from pathlib import Path

from app.schemas.contracts import EnvironmentalFeatures

_BASE = json.loads((Path(__file__).parent / "data" / "yield_baseline.json").read_text())
_ALIASES = {"rice_paddy": "rice", "paddy": "rice", "tomatoes": "tomato", "cotton_seed": "cotton"}

# Heuristic heat thresholds (deg C, 30-day max temp). Approximate; verify with an agronomy source.
_HEAT_C = {"wheat": 34.0, "maize": 35.0, "rice": 35.0, "tomato": 32.0, "cotton": 38.0}


def _key(name: str) -> str:
    k = name.strip().lower().replace(" ", "_").replace(",", "")
    return _ALIASES.get(k, k)


def estimate_yield(features: EnvironmentalFeatures) -> tuple[float, str, str]:
    crop = _key(features.crop)
    b = _BASE.get(crop)
    if not b or b["n_years"] == 0:
        return 0.0, "Not available", (f"No yield history for '{features.crop}' in the reference data, "
                                      "so no estimate is given. Add FAOSTAT yields for this crop.")
    est = b["recent_mean_kg_ha"]
    lo, hi = est - 2 * b["recent_std_kg_ha"], est + 2 * b["recent_std_kg_ha"]
    hist_lo, hist_hi = b["min_kg_ha"], b["max_kg_ha"]

    conf = "Medium" if b["n_years"] >= 15 else "Low"   # never "High": labels are national, not field-level

    flags = []
    if features.max_temp_c >= _HEAT_C.get(crop, 35.0):
        flags.append("recent heat stress")
    if features.ndvi_trend < -0.05:
        flags.append("falling NDVI (possible crop stress)")
    if features.irrigation_availability == "none" and features.soil_moisture_root < 0.3:
        flags.append("dry root zone with no irrigation")
    risk = "Elevated" if len(flags) >= 2 else "Moderate" if flags else "Low"
    if len(flags) >= 2 and conf == "Medium":
        conf = "Low"

    note = (f"Baseline, not a trained model: mean national {crop} yield over "
            f"{b['last_year'] - 4}-{b['last_year']} (about {est:.0f} kg/ha, typical range "
            f"{lo:.0f}-{hi:.0f}; {b['first_year']}-{b['last_year']} extremes {hist_lo:.0f}-{hist_hi:.0f}). "
            f"Based on {b['n_years']} years of national figures, so it ignores your field, soil and management. "
            f"Current-season risk: {risk}" + (f" ({', '.join(flags)})." if flags else "."))
    return round(est, 0), conf, note
