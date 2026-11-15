from __future__ import annotations

import itertools
import os
from datetime import date
from pathlib import Path

import joblib
import pandas as pd

from app.engine._model_compat import ensure_legacy_sklearn_pickle_compat
from app.engine._reference import load_crops, load_rules
from app.schemas.contracts import EnvironmentalFeatures, RotationOption

ensure_legacy_sklearn_pickle_compat()

SEP = " → "
CRITERIA = ("soil_health", "water_demand", "climate_suitability", "rotation_diversity")
DEFAULT_WEIGHTS = {
    "soil_health": 0.35,
    "water_demand": 0.30,
    "climate_suitability": 0.25,
    "rotation_diversity": 0.10,
}

SEASONAL_SWING_C = 10.0
HIGH_WATER_MM = 800
NDVI_STRESS_TREND = -0.05
NDVI_SOIL_BOOST = 1.15
MAX_GAP_MONTHS = 5
LOW_SOIL_MOISTURE = 0.30

_MODELS_DIR = Path(__file__).resolve().parent / "models"
_ITEM_TO_KEY = {
    "wheat": "wheat",
    "maize": "maize",
    "rice, paddy": "rice",
    "rice": "rice",
    "tomatoes": "tomato",
    "tomato": "tomato",
    "seed cotton": "cotton",
    "cotton": "cotton",
}
_KEY_TO_ITEM = {
    "wheat": "Wheat",
    "maize": "Maize",
    "rice": "Rice, paddy",
    "tomato": "Tomatoes",
    "cotton": "Seed cotton",
}
_TEXTURE_TO_SOIL = {
    "clay": "Alluvial Clay",
    "silty_clay": "Silty Clay",
    "clay_loam": "Alluvial Clay",
    "sandy_loam": "Sandy Loam",
    "loam": "Sandy Loam",
    "silt_loam": "Sandy Loam",
    "loamy_sand": "Sandy",
    "sand": "Sandy",
}


class OptimalHybridRotationEngine:
    def __init__(
        self,
        ml_model_path: str | Path | None = None,
        preprocessor_path: str | Path | None = None,
        encoder_path: str | Path | None = None,
        dataset_path: str | Path | None = None,
    ):
        ml_model_path = Path(ml_model_path) if ml_model_path else _MODELS_DIR / "rotation_model.pkl"
        preprocessor_path = Path(preprocessor_path) if preprocessor_path else _MODELS_DIR / "rotation_preprocessor.pkl"
        encoder_path = Path(encoder_path) if encoder_path else _MODELS_DIR / "xgboost_label_encoder.pkl"
        dataset_path = Path(dataset_path) if dataset_path else _MODELS_DIR / "egypt_4loc_5crops_dataset (1).csv"

        self.has_ml = False
        if ml_model_path.exists() and preprocessor_path.exists() and encoder_path.exists():
            try:
                self.model = joblib.load(ml_model_path)
                self.preprocessor = joblib.load(preprocessor_path)
                self.label_encoder = joblib.load(encoder_path)
                self.has_ml = True
            except Exception as e:
                print(f"ML loading skipped: {e}")

        self.crop_stats: dict = {}
        if dataset_path.exists():
            self.df = pd.read_csv(dataset_path)
            mask = self.df["hg/ha_yield"].isnull() & self.df["production_tonnes"].notnull()
            self.df.loc[mask, "hg/ha_yield"] = self.df.loc[mask, "production_tonnes"] * 10000 / 102650
            self.crop_stats = (
                self.df.groupby("Item")
                .agg(avg_yield=("hg/ha_yield", "mean"), avg_water=("rain_mm_per_day", "mean"))
                .to_dict(orient="index")
            )
        else:
            self.df = pd.DataFrame(columns=["Item"])

    def _engineer_features(self, input_dict: dict) -> pd.DataFrame:
        df = pd.DataFrame([input_dict])
        date_series = pd.to_datetime({"year": 2024, "month": df["Month"], "day": df["Day"]})
        df["DayOfYear"] = date_series.dt.dayofyear
        df["Season"] = df["Month"].apply(
            lambda m: "Winter"
            if m in [12, 1, 2]
            else ("Spring" if m in [3, 4, 5] else ("Summer" if m in [6, 7, 8] else "Autumn"))
        )
        df["temp_range"] = df["max_temp"] - df["min_temp"]
        df["temp_humidity_interaction"] = df["avg_temp"] * (df["rel_humidity"] / 100.0)
        return df

    def predict_crop_probs(self, farm_input: dict) -> dict[str, float]:
        if not self.has_ml:
            return {}
        try:
            processed_df = self._engineer_features(farm_input)
            cat_cols = ["location_name", "soil", "Item", "previous_crop", "Season"]
            num_cols = [
                "lat",
                "lon",
                "avg_temp",
                "max_temp",
                "min_temp",
                "rain_mm_per_day",
                "rel_humidity",
                "Month",
                "Day",
                "DayOfYear",
                "temp_range",
                "temp_humidity_interaction",
                "hg/ha_yield",
            ]
            X_trans = self.preprocessor.transform(processed_df[cat_cols + num_cols])
            if hasattr(self.model, "predict_proba"):
                probs = self.model.predict_proba(X_trans)[0]
                classes_decoded = self.label_encoder.inverse_transform(self.model.classes_)
                mapped: dict[str, float] = {}
                for raw_label, prob in zip(classes_decoded, probs):
                    key = _ITEM_TO_KEY.get(str(raw_label).strip().lower(), str(raw_label).strip().lower())
                    mapped[key] = float(prob)
                return mapped
        except Exception as e:
            print(f"ML inference exception: {e}")
        return {}


_HYBRID_ENGINE: OptimalHybridRotationEngine | None = None


def _get_hybrid_engine() -> OptimalHybridRotationEngine:
    global _HYBRID_ENGINE
    if _HYBRID_ENGINE is None:
        _HYBRID_ENGINE = OptimalHybridRotationEngine()
    return _HYBRID_ENGINE


def _ml_probs_for_features(f: EnvironmentalFeatures) -> dict[str, float]:
    dt = date.fromisoformat(f.planting_date)
    item_name = _KEY_TO_ITEM.get(f.crop.lower(), f.crop.capitalize())
    prev_raw = getattr(f, "previous_crop", None) or "Wheat"
    prev_name = _KEY_TO_ITEM.get(prev_raw.lower(), prev_raw.capitalize())
    soil_name = _TEXTURE_TO_SOIL.get(f.soil_texture.lower(), "Alluvial Clay")
    min_temp = f.min_temp_c if f.min_temp_c is not None else max(0.0, f.avg_temp_c - 6.0)
    humidity = f.rel_humidity_pct if f.rel_humidity_pct is not None else 55.0

    farm_input = {
        "location_name": "Nile Delta" if f.lat >= 30.0 else ("Fayoum" if f.lat >= 28.0 else "Upper Egypt"),
        "soil": soil_name,
        "Item": item_name,
        "previous_crop": prev_name,
        "lat": f.lat,
        "lon": f.lon,
        "avg_temp": f.avg_temp_c,
        "max_temp": f.max_temp_c,
        "min_temp": min_temp,
        "rain_mm_per_day": f.total_precip_mm / 30.0,
        "rel_humidity": humidity,
        "Month": dt.month,
        "Day": dt.day,
        "hg/ha_yield": 65000.0,
    }
    return _get_hybrid_engine().predict_crop_probs(farm_input)


def _db() -> dict:
    return load_crops()


def _clip(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def season_of_month(month: int, lat: float = 30.0) -> str:
    north_winter = month in (11, 12, 1, 2, 3, 4)
    is_winter = north_winter if lat >= 0 else not north_winter
    return "winter" if is_winter else "summer"


def _opposite(season: str) -> str:
    return "summer" if season == "winter" else "winter"


def _normalised_weights(f: EnvironmentalFeatures, stressed: bool) -> dict:
    raw = {k: max(0.0, float(f.rotation_priority_weights.get(k, 0.0))) for k in CRITERIA}
    if sum(raw.values()) <= 0:
        raw = dict(DEFAULT_WEIGHTS)
    if stressed:
        raw["soil_health"] *= NDVI_SOIL_BOOST
    total = sum(raw.values())
    return {k: v / total for k, v in raw.items()}


def _current_season(f: EnvironmentalFeatures, cur: dict | None) -> str:
    if cur and len(cur["seasons"]) == 1:
        return cur["seasons"][0]
    month = date.fromisoformat(f.planting_date).month
    return season_of_month(month, f.lat)


def _allowed_in_slot(name: str, crop: dict, season: str, f: EnvironmentalFeatures) -> bool:
    if season not in crop["seasons"]:
        return False
    if f.irrigation_availability == "none" and crop["water_req_mm"] > HIGH_WATER_MM:
        return False
    return True


def _calendar_ok(prev_name: str | None, prev_season: str, name: str, season: str) -> bool:
    db = _db()
    if prev_name is None or prev_name not in db:
        return True
    prev_win = db[prev_name]["windows"].get(prev_season)
    win = db[name]["windows"].get(season)
    if not prev_win or not win:
        return False
    gap = (max(win["plant"]) - max(prev_win["harvest"])) % 12
    return gap <= MAX_GAP_MONTHS


def _valid(chain: list[str | None], seasons: list[str]) -> bool:
    db = _db()
    names = [c for c in chain if c is not None]
    rules = load_rules()
    for a, b in zip(chain, chain[1:]):
        rule = rules.get((a, b)) if a is not None else None
        if rule is not None and not rule["allowed"]:
            return False
    for n in set(names):
        if db[n]["no_repeat"] and names.count(n) > 1:
            return False
    for i in range(1, len(chain)):
        if not _calendar_ok(chain[i - 1], seasons[i - 1], chain[i], seasons[i]):
            return False
    return True


def _soil_transition(prev: str | None, cur: str) -> float:
    rule = load_rules().get((prev, cur)) if prev else None
    return rule["soil_score"] if rule else 0.55


def _water_score(crop: dict, f: EnvironmentalFeatures) -> float:
    max_req = max(c["water_req_mm"] for c in _db().values())
    rel = crop["water_req_mm"] / max_req
    s = 1.0 - rel
    if f.irrigation_availability == "limited":
        s -= 0.10 * rel
    elif f.irrigation_availability == "none":
        s -= 0.20 * rel
    if f.soil_moisture_root < LOW_SOIL_MOISTURE:
        s -= 0.10 * rel
    return _clip(s)


def _climate_score(crop: dict, slot_season: str, obs_season: str, f: EnvironmentalFeatures) -> float:
    shift = 0.0
    if slot_season != obs_season:
        shift = SEASONAL_SWING_C if slot_season == "summer" else -SEASONAL_SWING_C
    t_avg, t_max = f.avg_temp_c + shift, f.max_temp_c + shift
    lo, hi = crop["temp_opt_c"]
    d = max(lo - t_avg, t_avg - hi, 0.0)
    s_avg = _clip(1.0 - d / 10.0)
    excess = max(0.0, t_max - crop["temp_max_c"])
    s_max = _clip(1.0 - 0.10 * excess)
    return 0.6 * s_avg + 0.4 * s_max


def score_sequence(
    chain: list[str | None], seasons: list[str], f: EnvironmentalFeatures, obs_season: str
) -> dict:
    db = _db()
    soil = [_soil_transition(chain[i - 1], chain[i]) for i in range(1, len(chain))]
    future = chain[1:]
    water = [_water_score(db[c], f) for c in future]
    climate = [_climate_score(db[c], seasons[i + 1], obs_season, f) for i, c in enumerate(future)]
    families = {db[c]["family"] for c in chain if c is not None}
    n_crops = len([c for c in chain if c is not None])
    return {
        "soil_health": sum(soil) / len(soil),
        "water_demand": sum(water) / len(water),
        "climate_suitability": sum(climate) / len(climate),
        "rotation_diversity": len(families) / n_crops,
    }


def score_baseline_rotation(features: EnvironmentalFeatures) -> float | None:
    db = _db()
    previous = getattr(features, "previous_crop", None)
    current = features.crop
    if not previous or previous not in db or current not in db:
        return None

    current_season = _current_season(features, db[current])
    previous_season = _opposite(current_season)
    observed_season = season_of_month(date.fromisoformat(features.planting_date).month, features.lat)
    chain = [previous, current]
    components = score_sequence(chain, [previous_season, current_season], features, observed_season)
    stressed = features.ndvi_trend < NDVI_STRESS_TREND
    weights = _normalised_weights(features, stressed)
    score = sum(weights[key] * components[key] for key in CRITERIA)
    return round(score, 2)


def _reason(
    chain: list[str | None], comps: dict, weights: dict, stressed: bool, has_ml: bool = False
) -> str:
    db = _db()
    top = max(CRITERIA, key=lambda k: weights[k] * comps[k])
    pretty = lambda n: n.replace("_", " ")
    legume_msg = None
    for i in range(1, len(chain)):
        cur, prev = chain[i], chain[i - 1]
        if db[cur]["n_fixing"]:
            if prev and db[prev]["heavy_feeder"]:
                legume_msg = f"{pretty(cur)} (legume) after {pretty(prev)} rebuilds soil nitrogen"
            else:
                legume_msg = f"{pretty(cur)} (legume) fixes nitrogen"
            break
    if top == "soil_health":
        msg = legume_msg or "Low-conflict crop transitions protect soil health"
        msg = msg[0].upper() + msg[1:]
    elif top == "water_demand":
        avg = sum(db[c]["water_req_mm"] for c in chain[1:]) / (len(chain) - 1)
        msg = f"Low water demand (about {avg:.0f} mm per season on average)"
    elif top == "climate_suitability":
        msg = "Crops fit the local temperature range"
    else:
        n = len({db[c]["family"] for c in chain if c})
        msg = f"Diverse rotation ({n} crop families) breaks pest and disease cycles"
    if legume_msg and top != "soil_health":
        msg += f"; {legume_msg}"
    if stressed:
        msg += "; current NDVI is falling, so soil health was weighted up"
    if has_ml:
        msg += "; ranked with hybrid XGBoost + agronomic scoring"
    return msg + "."


def recommend_rotations(features: EnvironmentalFeatures) -> list[RotationOption]:
    db = _db()
    f = features
    cur_name = f.crop if f.crop in db else None
    cur = db.get(cur_name) if cur_name else None

    cur_season = _current_season(f, cur)
    obs_season = season_of_month(date.fromisoformat(f.planting_date).month, f.lat)
    horizon = max(1, int(f.planning_horizon_seasons))

    seasons = [cur_season]
    for _ in range(horizon):
        seasons.append(_opposite(seasons[-1]))

    slot_options = [
        [n for n, c in db.items() if _allowed_in_slot(n, c, s, f)] for s in seasons[1:]
    ]

    stressed = f.ndvi_trend < NDVI_STRESS_TREND
    weights = _normalised_weights(f, stressed)
    ml_probs = _ml_probs_for_features(f)
    has_ml = bool(ml_probs)

    scored = []
    for combo in itertools.product(*slot_options):
        chain: list[str | None] = [cur_name, *combo]
        if not _valid(chain, seasons):
            continue
        comps = score_sequence(chain, seasons, f, obs_season)
        agronomic = sum(weights[k] * comps[k] for k in CRITERIA)
        if cur_name and db.get(cur_name, {}).get("heavy_feeder") and "berseem_clover" in combo:
            agronomic += 0.07
        if has_ml:
            ml_bonus = sum(ml_probs.get(c, 0.2) for c in combo) / len(combo)
            total = _clip(0.85 * agronomic + 0.15 * ml_bonus)
        else:
            total = agronomic
        scored.append((total, SEP.join(combo), chain, comps))

    scored.sort(key=lambda t: (-t[0], t[1]))
    return [
        RotationOption(
            crop=seq,
            score=round(total, 2),
            reason=_reason(chain, comps, weights, stressed, has_ml=has_ml),
        )
        for total, seq, chain, comps in scored[:3]
    ]
