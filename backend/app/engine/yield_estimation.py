import math
from datetime import date
from functools import lru_cache
from pathlib import Path

import pandas as pd
import numpy as np
import joblib

from app.engine import country_models
from app.engine._reference import load_crops
from app.engine._model_compat import ensure_legacy_sklearn_pickle_compat
from app.schemas.contracts import EnvironmentalFeatures

ensure_legacy_sklearn_pickle_compat()


class CropYieldPredictor:
    def __init__(self, model_path='yield_model.pkl', preprocessor_path='preprocessor.pkl'):
        """Load the trained Random Forest model and preprocessor pipeline."""
        models_dir = Path(__file__).resolve().parent / "models"
        self.model = joblib.load(models_dir / model_path)
        self.preprocessor = joblib.load(models_dir / preprocessor_path)

        # Define expected categorical and numerical feature columns matching training
        self.categorical_features = ['location_name', 'soil', 'Item', 'Season']
        self.numerical_features = [
            'lat', 'lon', 'avg_temp', 'max_temp', 'min_temp',
            'rain_mm_per_day', 'rel_humidity', 'Month', 'Day',
            'DayOfYear', 'temp_range', 'temp_humidity_interaction'
        ]

    def _engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply the same feature engineering steps used during training."""
        df = df.copy()

        # Create Date and DayOfYear from Month and Day (using placeholder year 2024)
        date_series = pd.to_datetime({'year': 2024, 'month': df['Month'], 'day': df['Day']})
        df['DayOfYear'] = date_series.dt.dayofyear

        # Determine Season
        df['Season'] = df['Month'].apply(
            lambda m: 'Winter' if m in [12, 1, 2] else
                     ('Spring' if m in [3, 4, 5] else
                     ('Summer' if m in [6, 7, 8] else 'Autumn'))
        )

        # Temperature Range and Interaction
        df['temp_range'] = df['max_temp'] - df['min_temp']
        df['temp_humidity_interaction'] = df['avg_temp'] * (df['rel_humidity'] / 100.0)

        return df

    def predict(self, input_data: dict | pd.DataFrame) -> np.ndarray:
        """
        Takes raw dictionary or DataFrame input, processes features,
        and returns the model's predicted yield (hg/ha).
        """
        if isinstance(input_data, dict):
            input_df = pd.DataFrame([input_data])
        elif isinstance(input_data, pd.DataFrame):
            input_df = input_data.copy()
        else:
            raise ValueError("Input data must be a dictionary or a pandas DataFrame.")

        # 1. Engineer features
        processed_df = self._engineer_features(input_df)

        # 2. Extract required features in exact order
        X_input = processed_df[self.categorical_features + self.numerical_features]

        # 3. Transform features using saved preprocessor
        X_transformed = self.preprocessor.transform(X_input)

        # 4. Predict yield
        predictions = self.model.predict(X_transformed)

        return predictions


_CROP_TO_ITEM = {
    "wheat": "Wheat",
    "maize": "Maize",
    "rice": "Rice, paddy",
    "rice_paddy": "Rice, paddy",
    "tomato": "Tomatoes",
    "tomatoes": "Tomatoes",
    "cotton": "Cotton seed",
    "cotton_seed": "Cotton seed",
}

_SOIL_TO_LABEL = {
    "clay": "Alluvial Clay",
    "alluvial_clay": "Alluvial Clay",
    "silty_clay": "Silty Clay",
    "sandy_loam": "Sandy Loam",
    "sand": "Sandy",
    "sandy": "Sandy",
}

_REF_LOCATIONS = [
    ("nile_delta", "Nile Delta (Kafr El-Sheikh)", 31.11, 30.94),
    ("fayoum", "Fayoum Oasis", 29.31, 30.84),
    ("upper_egypt", "Upper Egypt (Minya)", 25.69, 32.64),
    ("new_valley", "New Valley (Kharga)", 25.45, 30.55),
]


@lru_cache(maxsize=1)
def _get_predictor() -> CropYieldPredictor:
    return CropYieldPredictor()


@lru_cache(maxsize=1)
def _known_categories() -> dict[str, list[str]]:
    """Read fitted OneHotEncoder categories directly from preprocessor.pkl."""
    prep = _get_predictor().preprocessor
    cats: dict[str, list[str]] = {}
    for _, trans, cols in getattr(prep, "transformers_", []):
        enc = trans
        if hasattr(trans, "named_steps"):
            for step in trans.named_steps.values():
                if hasattr(step, "categories_"):
                    enc = step
                    break
        if hasattr(enc, "categories_"):
            for col, values in zip(cols, enc.categories_):
                cats[col] = [str(v) for v in values]
    return cats


def _match_category(col: str, candidates: list[str], fallback_first: bool = True) -> str | None:
    known = _known_categories().get(col, [])
    if not known:
        return candidates[0] if candidates else None
    by_lower = {k.lower(): k for k in known}
    for cand in candidates:
        if cand in known:
            return cand
        if cand.lower() in by_lower:
            return by_lower[cand.lower()]
    return known[0] if fallback_first else None


def _nearest_location(lat: float, lon: float) -> tuple[str, float]:
    def dist_km(la: float, lo: float) -> float:
        p1, p2 = math.radians(lat), math.radians(la)
        a = (
            math.sin((p2 - p1) / 2) ** 2
            + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon - lo) / 2) ** 2
        )
        return 6371.0 * 2.0 * math.asin(math.sqrt(a))

    loc_id, display_name, r_lat, r_lon = min(_REF_LOCATIONS, key=lambda r: dist_km(r[2], r[3]))
    matched = _match_category("location_name", [display_name, loc_id]) or display_name
    return matched, dist_km(r_lat, r_lon)


def estimate_yield(features: EnvironmentalFeatures) -> tuple[float, str, str]:
    """Frozen contract wrapper -> (yield_kg_ha, confidence, note).

    Egypt: the trained Random Forest. USA / China: a national-yield benchmark.
    Elsewhere: a low-confidence climate-and-soil heuristic anchored to available country benchmarks.
    """
    country, dist = country_models.country_of(features.lat, features.lon)
    if country in ("USA", "CHINA"):
        return _country_yield(features, country, dist)
    if country is None:
        return _fallback_yield(features)
    crop_key = features.crop.strip().lower().replace(" ", "_")
    raw_item = _CROP_TO_ITEM.get(crop_key, features.crop)
    item = _match_category("Item", [raw_item, crop_key], fallback_first=False)
    if item is None:
        return (
            0.0,
            "Low",
            f"Crop '{features.crop}' was not in the trained yield model's crop list.",
        )

    soil_key = features.soil_texture.strip().lower().replace(" ", "_")
    raw_soil = _SOIL_TO_LABEL.get(soil_key, features.soil_texture)
    soil_label = _match_category("soil", [raw_soil, soil_key, "Alluvial Clay", "clay"]) or raw_soil

    dt = date.fromisoformat(features.planting_date)
    min_temp = (
        features.min_temp_c
        if features.min_temp_c is not None
        else round(2.0 * features.avg_temp_c - features.max_temp_c, 2)
    )
    rel_humidity = features.rel_humidity_pct if features.rel_humidity_pct is not None else 55.0
    loc_name, km = _nearest_location(features.lat, features.lon)

    row = {
        "location_name": loc_name,
        "soil": soil_label,
        "Item": item,
        "lat": features.lat,
        "lon": features.lon,
        "avg_temp": features.avg_temp_c,
        "max_temp": features.max_temp_c,
        "min_temp": min_temp,
        "rain_mm_per_day": features.total_precip_mm / 30.0,
        "rel_humidity": rel_humidity,
        "Month": dt.month,
        "Day": dt.day,
    }

    pred_hg_ha = float(_get_predictor().predict(row)[0])
    yield_kg_ha = round(max(0.0, pred_hg_ha / 10.0), 1)
    confidence = "Medium" if km <= 75.0 else "Low"
    note = (
        f"Predicted by Random Forest yield model ({yield_kg_ha:.0f} kg/ha; nearest training site: "
        f"{loc_name}, {km:.0f} km away)."
    )
    return yield_kg_ha, confidence, note


def _fallback_yield(features: EnvironmentalFeatures) -> tuple[float, str, str]:
    crop_key = features.crop.strip().lower().replace(" ", "_")
    benchmark = country_models.fallback_yield_benchmark(
        crop_key, date.fromisoformat(features.planting_date).year
    )
    crop = load_crops().get(crop_key)
    if benchmark is None or crop is None:
        return 0.0, "Low", (
            f"No reference yield baseline is available for {features.crop} outside Egypt, "
            "the USA, and China; no estimate was generated."
        )

    temperature = features.avg_temp_c
    optimal_min, optimal_max = crop["temp_opt_c"]
    if temperature < optimal_min:
        temp_stress = max(0.0, optimal_min - temperature)
    elif temperature > optimal_max:
        temp_stress = max(0.0, temperature - optimal_max)
    else:
        temp_stress = 0.0
    heat_stress = max(0.0, features.max_temp_c - crop["temp_max_c"])
    temperature_factor = max(0.2, 1.0 - 0.025 * temp_stress - 0.04 * heat_stress)

    monthly_water_need = crop["water_req_mm"] * 30.0 / crop["season_days"]
    rainfall_coverage = min(1.0, max(0.0, features.total_precip_mm / monthly_water_need))
    soil_moisture = min(1.0, max(0.0, features.soil_moisture_root))
    water_supply = 0.6 * soil_moisture + 0.4 * rainfall_coverage
    irrigation_bonus = {
        "available": 0.25,
        "limited": 0.12,
        "none": 0.0,
    }.get(features.irrigation_availability, 0.0)
    water_factor = min(1.0, max(0.2, water_supply + irrigation_bonus))

    soil_texture = features.soil_texture.strip().lower().replace(" ", "_")
    soil_factor = {
        "clay": 1.0,
        "alluvial_clay": 1.0,
        "silty_clay": 1.0,
        "loam": 0.95,
        "sandy_loam": 0.95,
        "sandy": 0.85,
        "sand": 0.85,
    }.get(soil_texture, 0.9)
    estimate = round(
        benchmark["kg_ha"] * temperature_factor * water_factor * soil_factor,
        1,
    )
    source_countries = " and ".join(benchmark["countries"])
    note = (
        f"Low-confidence heuristic estimate ({estimate:.0f} kg/ha), anchored to "
        f"{source_countries} national yield benchmark(s) and adjusted for temperature, "
        "rainfall, soil moisture, irrigation access, and soil texture. This is not a "
        "locally validated model; verify with local agricultural guidance."
    )
    return estimate, "Low", note


def _country_yield(features: EnvironmentalFeatures, country: str, dist_km: float) -> tuple[float, str, str]:
    year = date.fromisoformat(features.planting_date).year
    b = country_models.yield_benchmark(country, features.crop, year)
    if b is None:
        return 0.0, "Low", f"{features.crop} has no {country} yield benchmark (crops: wheat, maize, rice, tomato, cotton)."
    conf = "Medium" if b["relative_sd"] < 0.10 and dist_km <= 500 else "Low"
    how = "linear trend of recent years" if b["method"] == "trend" else "median of the last 8 years"
    label = {"USA": "USA", "CHINA": "China"}[country]
    note = (f"{label} national benchmark ({how}, FAOSTAT {b['last_year'] - b['n_years'] + 1}-{b['last_year']}): "
            f"{b['kg_ha']:.0f} kg/ha, 80% range {b['low']:.0f}-{b['high']:.0f}. Country-level average, not this "
            f"field; weather does not change it because no weather model passed validation.")
    return round(b["kg_ha"], 1), conf, note
