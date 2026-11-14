from __future__ import annotations

import itertools
from datetime import date

from app.engine._reference import load_crops, load_rules
from app.schemas.contracts import EnvironmentalFeatures, RotationOption

SEP = " → "                    # crop field = "berseem_clover → maize → wheat"
CRITERIA = ("soil_health", "water_demand", "climate_suitability", "rotation_diversity")
DEFAULT_WEIGHTS = {"soil_health": 0.35, "water_demand": 0.30,
                   "climate_suitability": 0.25, "rotation_diversity": 0.10}

# ---- tunable assumptions (documented, not hidden) ---------------------------
SEASONAL_SWING_C = 10.0        # summer-minus-winter temperature gap used to project
HIGH_WATER_MM = 800            # crops above this are excluded when irrigation == "none"
NDVI_STRESS_TREND = -0.05      # ndvi_trend below this => current crop under stress
NDVI_SOIL_BOOST = 1.15         # soil_health weight multiplier under stress (then renormalised)
MAX_GAP_MONTHS = 5             # max months between previous harvest and next planting
LOW_SOIL_MOISTURE = 0.30


def _db() -> dict:
    return load_crops()


# ------------------------------------------------------------------ helpers
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
    """Season the current crop occupies (crop's own season if it has only one)."""
    if cur and len(cur["seasons"]) == 1:
        return cur["seasons"][0]
    month = date.fromisoformat(f.planting_date).month
    return season_of_month(month, f.lat)


# ------------------------------------------------------- hard constraints (B)
def _allowed_in_slot(name: str, crop: dict, season: str, f: EnvironmentalFeatures) -> bool:
    if season not in crop["seasons"]:
        return False
    if f.irrigation_availability == "none" and crop["water_req_mm"] > HIGH_WATER_MM:
        return False
    return True


def _calendar_ok(prev_name: str | None, prev_season: str, name: str, season: str) -> bool:
    """Next crop must be plantable soon enough after the previous one is harvested."""
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
    """chain[0] is the current crop (may be None); seasons aligns with chain."""
    db = _db()
    names = [c for c in chain if c is not None]
    rules = load_rules()
    for a, b in zip(chain, chain[1:]):
        rule = rules.get((a, b)) if a is not None else None
        if rule is not None and not rule["allowed"]:  # e.g. same crop twice in a row
            return False
    for n in set(names):
        if db[n]["no_repeat"] and names.count(n) > 1:  # rice / cotton / tomato
            return False
    for i in range(1, len(chain)):
        if not _calendar_ok(chain[i - 1], seasons[i - 1], chain[i], seasons[i]):
            return False
    return True


# ------------------------------------------------------------- scoring (C)
def _soil_transition(prev: str | None, cur: str) -> float:
    """Soil-health score of prev -> cur, read from rotation_rules.csv (neutral if unknown)."""
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


def score_sequence(chain: list[str | None], seasons: list[str], f: EnvironmentalFeatures,
                   obs_season: str) -> dict:
    """Return the four 0-1 criterion scores for one chain (chain[0] = current crop)."""
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
    """Score the previous-crop -> current-crop practice when both crops are supported."""
    db = _db()
    previous = features.previous_crop
    current = features.crop
    if not previous or previous not in db or current not in db:
        return None

    current_season = _current_season(features, db[current])
    previous_season = _opposite(current_season)
    observed_season = season_of_month(date.fromisoformat(features.planting_date).month,
                                      features.lat)
    chain = [previous, current]
    components = score_sequence(
        chain,
        [previous_season, current_season],
        features,
        observed_season,
    )
    stressed = features.ndvi_trend < NDVI_STRESS_TREND
    weights = _normalised_weights(features, stressed)
    score = sum(weights[key] * components[key] for key in CRITERIA)
    return round(score, 2)


# --------------------------------------------------------------- reasons (D)
def _reason(chain: list[str | None], comps: dict, weights: dict, stressed: bool) -> str:
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
    return msg + "."


# ------------------------------------------------------------------ public
def recommend_rotations(features: EnvironmentalFeatures) -> list[RotationOption]:
    """Top-3 valid rotation sequences. Returns [] if no sequence survives the constraints."""
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

    scored = []
    for combo in itertools.product(*slot_options):
        chain: list[str | None] = [cur_name, *combo]
        if not _valid(chain, seasons):
            continue
        comps = score_sequence(chain, seasons, f, obs_season)
        total = sum(weights[k] * comps[k] for k in CRITERIA)
        scored.append((total, SEP.join(combo), chain, comps))

    scored.sort(key=lambda t: (-t[0], t[1]))
    return [
        RotationOption(crop=seq, score=round(total, 2),
                       reason=_reason(chain, comps, weights, stressed))
        for total, seq, chain, comps in scored[:3]
    ]