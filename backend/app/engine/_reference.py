"""Loaders for the reference tables in data/reference/ (stdlib only, no pandas).

crop_characteristics.csv + crop_calendars.csv  ->  load_crops()
rotation_rules.csv                             ->  load_rules()
yield_baseline.json                            ->  load_json("yield_baseline.json")

Set AGRISCOPE_REFERENCE_DIR to point somewhere else (e.g. for tests).
"""
import csv
import json
import os
from functools import lru_cache
from pathlib import Path

# .../agriscope/backend/app/engine/_reference.py  ->  parents[3] == .../agriscope
REFERENCE_DIR = Path(os.environ.get(
    "AGRISCOPE_REFERENCE_DIR", Path(__file__).resolve().parents[3] / "data" / "processed" / "reference"))


def _bool(s: str) -> bool:
    return s.strip().lower() in ("true", "1", "yes")


def _rows(name: str) -> list[dict]:
    with open(REFERENCE_DIR / name, encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _months(s: str) -> list[int]:
    return [int(x) for x in s.split("|") if x.strip()]


@lru_cache(maxsize=None)
def load_json(name: str) -> dict:
    with open(REFERENCE_DIR / name, encoding="utf-8") as fh:
        return json.load(fh)


@lru_cache(maxsize=None)
def load_crops() -> dict:
    """crop -> dict(family, seasons, windows{season:{plant,harvest}}, water_req_mm, ...)."""
    crops: dict = {}
    for r in _rows("crop_characteristics.csv"):
        crops[r["crop"]] = {
            "family": r["family"],
            "n_fixing": _bool(r["n_fixing"]),
            "heavy_feeder": _bool(r["heavy_feeder"]),
            "no_repeat": _bool(r["no_repeat"]),
            "water_req_mm": float(r["water_req_mm"]),
            "season_days": int(r["season_days"]),
            "temp_opt_c": [float(r["temp_opt_min_c"]), float(r["temp_opt_max_c"])],
            "temp_max_c": float(r["temp_max_c"]),
            "ky": float(r["ky"]),
            "source": r["source"],
            "reliability": r["reliability"],
            "seasons": [],
            "windows": {},
        }
    for r in _rows("crop_calendars.csv"):
        crop = crops[r["crop"]]            # KeyError here = calendar row for unknown crop
        crop["seasons"].append(r["season"])
        crop["windows"][r["season"]] = {"plant": _months(r["plant_months"]),
                                        "harvest": _months(r["harvest_months"])}
    missing = [c for c, v in crops.items() if not v["seasons"]]
    if missing:
        raise ValueError(f"crops without a calendar row: {missing}")
    return crops


@lru_cache(maxsize=None)
def load_rules() -> dict:
    """(prev_crop, next_crop) -> dict(allowed, soil_score, reason)."""
    return {
        (r["prev_crop"], r["next_crop"]): {
            "allowed": _bool(r["allowed"]),
            "soil_score": float(r["soil_score"]),
            "reason": r["reason"],
        }
        for r in _rows("rotation_rules.csv")
    }


def validate_reference() -> list[str]:
    """Return a list of problems in the reference tables (empty list = all good)."""
    problems: list[str] = []
    crops, rules = load_crops(), load_rules()
    for name, c in crops.items():
        for season, win in c["windows"].items():
            if season not in ("winter", "summer"):
                problems.append(f"{name}: unknown season '{season}'")
            for key in ("plant", "harvest"):
                if not win[key] or any(not 1 <= m <= 12 for m in win[key]):
                    problems.append(f"{name}/{season}: bad {key} months {win[key]}")
        if c["temp_opt_c"][0] >= c["temp_opt_c"][1]:
            problems.append(f"{name}: temp_opt min must be below max")
        if c["water_req_mm"] <= 0 or c["season_days"] <= 0:
            problems.append(f"{name}: water_req_mm and season_days must be positive")
    for a in crops:
        for b in crops:
            rule = rules.get((a, b))
            if rule is None:
                problems.append(f"missing rule {a} -> {b}")
            elif not 0.0 <= rule["soil_score"] <= 1.0:
                problems.append(f"rule {a} -> {b}: soil_score outside 0-1")
    for a, b in rules:
        if a not in crops or b not in crops:
            problems.append(f"rule {a} -> {b} refers to an unknown crop")
    return problems
