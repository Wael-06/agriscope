"""USA / China models (yield benchmark + crop-suitability prior). Standard library only.

Artifacts (made by notebooks/train_country_models.ipynb) live in engine/models/:
  yield_country.json, suitability_country.json, country_sites.json
Nothing here needs scikit-learn, so a version mismatch cannot break loading.
"""
from __future__ import annotations

import json
import math
from statistics import median
from datetime import date
from functools import lru_cache
from pathlib import Path

_DIR = Path(__file__).resolve().parent / "models"
MAX_SITE_KM = 1500.0     # farther than this from every reference site -> no country model
_EGYPT = [("EGYPT", "nile_delta", 31.11, 30.94), ("EGYPT", "fayoum", 29.31, 30.84),
          ("EGYPT", "upper_egypt", 25.69, 32.64), ("EGYPT", "new_valley", 25.45, 30.55)]
_CROP = {"wheat": "Wheat", "maize": "Maize", "rice": "Rice", "rice_paddy": "Rice",
         "tomato": "Tomatoes", "tomatoes": "Tomatoes", "cotton": "Cotton", "cotton_seed": "Cotton"}
_CROP.update({"sugarcane": "Sugarcane", "date_palm": "Date Palm"})
_CROP_KEYS = {
    "Wheat": "wheat",
    "Maize": "maize",
    "Rice": "rice",
    "Tomatoes": "tomato",
    "Cotton": "cotton",
    "Sugarcane": "sugarcane",
    "Date Palm": "date_palm",
}


def _load(name: str):
    p = _DIR / name
    return json.loads(p.read_text()) if p.exists() else None


@lru_cache(maxsize=1)
def _sites() -> list[tuple[str, str, float, float]]:
    s = _load("country_sites.json") or []
    return _EGYPT + [(r["country"], r["id"], r["lat"], r["lon"]) for r in s]


def _km(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def country_of(lat: float, lon: float) -> tuple[str | None, float]:
    """('USA' | 'CHINA' | 'EGYPT' | None, km to the nearest reference site)."""
    c, _, la, lo = min(_sites(), key=lambda s: _km(lat, lon, s[2], s[3]))
    km = _km(lat, lon, la, lo)
    return (c, km) if km <= MAX_SITE_KM else (None, km)


def crop_name(key: str) -> str | None:
    return _CROP.get(key.strip().lower().replace(" ", "_"))


def supported_yield_crops(country: str) -> list[str]:
    models = (_load("yield_country.json") or {}).get("models", {})
    return [
        crop_key
        for crop_name, crop_key in _CROP_KEYS.items()
        if f"{country}|{crop_name}" in models
    ]


def supported_suitability_crops(country: str) -> list[str]:
    models = (_load("suitability_country.json") or {}).get("models", {})
    return [
        crop_key
        for crop_name, crop_key in _CROP_KEYS.items()
        if (model := models.get(f"{country}|{crop_name}")) and model["enabled"]
    ]


# ---------------------------------------------------------------- yield
def yield_benchmark(country: str, crop_key: str, year: int) -> dict | None:
    art, name = _load("yield_country.json"), crop_name(crop_key)
    m = (art or {}).get("models", {}).get(f"{country}|{name}")
    if not m:
        return None
    if m["benchmark"] == "trend":
        kg = m["trend_slope_kg_ha_per_year"] * min(year, m["last_year"] + 2) + m["trend_intercept"]
    else:
        kg = m["median8_kg_ha"]
    sd = m["resid_sd_kg_ha"]
    return {"kg_ha": max(0.0, kg), "low": max(0.0, kg - 1.28 * sd), "high": kg + 1.28 * sd,
            "method": m["benchmark"], "n_years": m["n_years"], "last_year": m["last_year"],
            "relative_sd": sd / kg if kg > 0 else 1.0}


def fallback_yield_benchmark(crop_key: str, year: int) -> dict | None:
    """Return a broad baseline from available USA/China benchmarks for heuristic use."""
    benchmarks = [
        benchmark
        for country in ("USA", "CHINA")
        if (benchmark := yield_benchmark(country, crop_key, year)) is not None
    ]
    if not benchmarks:
        return None
    return {
        "kg_ha": median(benchmark["kg_ha"] for benchmark in benchmarks),
        "countries": [country for country in ("USA", "CHINA")
                      if yield_benchmark(country, crop_key, year) is not None],
    }


# ----------------------------------------------------------- suitability
def _design(avg, mx, mn, rain, hum, lat, month) -> list[float]:
    return [avg, mx, mn, rain, hum, lat, math.sin(2 * math.pi * month / 12), math.cos(2 * math.pi * month / 12),
            avg ** 2, mx ** 2, lat ** 2]


def suitability(country: str, f, month: int | None = None) -> dict[str, float]:
    """{crop_key: probability this crop is grown near here}, only for crops whose model passed the gate."""
    art = _load("suitability_country.json")
    if not art:
        return {}
    month = month or date.fromisoformat(f.planting_date).month
    min_t = f.min_temp_c if getattr(f, "min_temp_c", None) is not None else f.avg_temp_c - 6.0
    hum = f.rel_humidity_pct if getattr(f, "rel_humidity_pct", None) is not None else 55.0
    x = _design(f.avg_temp_c, f.max_temp_c, min_t, f.total_precip_mm / 30.0, hum, f.lat, month)
    out = {}
    for key, m in art["models"].items():
        c, crop = key.split("|")
        if c != country or not m["enabled"]:
            continue
        z = m["intercept"] + sum(w * (v - mu) / sd for w, v, mu, sd in zip(m["coef"], x, m["mean"], m["std"]))
        out[{"Wheat": "wheat", "Maize": "maize", "Rice": "rice", "Tomatoes": "tomato", "Cotton": "cotton"}[crop]] = 1 / (1 + math.exp(-z))
    return out
