from __future__ import annotations
"""Irrigation advisor (Abdo). Transparent FAO-56 formulas, not a trained model.

ETc = Kc * ET0                      (ET0 straight from Open-Meteo, never recomputed)
I_net   = max(0, 7*ETc - P_eff)     (weekly, mm)
I_gross = I_net / E                 (E from irrigation_availability)

Public contract (frozen):
    compute_irrigation(features) -> (irrigation_mm_per_week, next_irrigation_date "YYYY-MM-DD")
"""

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from app.schemas.contracts import EnvironmentalFeatures

_KC_PATH = Path(__file__).resolve().parents[3] / "data" / "kc_table.json"
if not _KC_PATH.exists():
    _KC_PATH = Path(__file__).parent / "data" / "kc_table.json"
_KC = {k: v for k, v in json.loads(_KC_PATH.read_text()).items() if not k.startswith("_")}
# Efficiency by irrigation_availability. "none" = rainfed.
_EFFICIENCY = {"available": 0.75, "limited": 0.60}

# Total available water, mm per metre of root zone (FAO-56 Table 19 ranges, mid-values).
_TAW_MM_PER_M = {"sand": 70, "loamy_sand": 90, "sandy_loam": 110, "loam": 140,
                 "silt_loam": 160, "clay_loam": 150, "silty_clay": 160, "clay": 150}

_RAIN_EFFECTIVE_FRACTION = 0.8   # simple assumption: 20% lost to runoff/evaporation
_MAX_DAYS_TO_NEXT = 14


@dataclass
class IrrigationDetail:
    """Everything the Irrigation Advisor card needs (Gheno can show these)."""
    irrigation_mm_per_week: float
    next_irrigation_date: str          # "" when rainfed
    crop: str
    growth_stage: str
    kc: float
    et0_mm_day: float
    etc_mm_day: float
    net_mm_week: float
    efficiency: float | None
    rainfed: bool
    days_to_next: int | None
    notes: list[str] = field(default_factory=list)


def _norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_").replace("-", "_")


def _soil_key(name: str) -> str:
    """Accept farmer text and /regions soil labels: 'Alluvial Clay' -> clay, 'Sandy' -> sand."""
    k = _norm(name)
    aliases = {"alluvial_clay": "clay", "sandy": "sand"}
    return aliases.get(k, k)


def _growth_stage(crop_cfg: dict, days_since_planting: int) -> tuple[str, float, float]:
    """Return (stage name, Kc, root-depth fraction 0-1) via FAO-56 piecewise-linear Kc curve."""
    ini, dev, mid, late = crop_cfg["stage_days"]
    k_ini, k_mid, k_end = crop_cfg["kc_ini"], crop_cfg["kc_mid"], crop_cfg["kc_end"]
    d = max(0, days_since_planting)
    if d < ini:
        return "initial", k_ini, 0.2
    if d < ini + dev:
        f = (d - ini) / dev
        return "development", k_ini + f * (k_mid - k_ini), 0.2 + 0.8 * f
    if d < ini + dev + mid:
        return "mid-season", k_mid, 1.0
    if d < ini + dev + mid + late:
        f = (d - ini - dev - mid) / late
        return "late-season", k_mid + f * (k_end - k_mid), 1.0
    return "post-season", k_end, 1.0


def compute_irrigation_detail(features: EnvironmentalFeatures,
                              today: date | None = None) -> IrrigationDetail:
    today = today or date.today()
    crop = _norm(features.crop)
    if crop not in _KC:
        raise ValueError(f"No Kc data for crop '{features.crop}'. Known: {sorted(_KC)}")
    cfg = _KC[crop]

    planting = datetime.strptime(features.planting_date, "%Y-%m-%d").date()
    days_since = (today - planting).days
    notes: list[str] = []
    if days_since < 0:
        notes.append(f"Planting is {-days_since} day(s) away; using initial-stage Kc.")
    stage, kc, root_frac = _growth_stage(cfg, days_since)
    if stage == "post-season":
        notes.append("Crop is past its typical season length; using end-season Kc.")

    et0 = max(0.0, features.forecast_et0_mm_day)
    etc = kc * et0                                            # mm/day
    weekly_etc = 7 * etc
    p_eff = max(0.0, features.forecast_precip_7d_mm) * _RAIN_EFFECTIVE_FRACTION
    net = max(0.0, weekly_etc - p_eff)                        # mm/week

    avail = features.irrigation_availability.lower()
    rainfed = avail == "none"
    if rainfed:
        eff, gross = None, 0.0
        notes.append(f"Rainfed field: no irrigation scheduled. Estimated weekly shortfall "
                     f"is about {net:.0f} mm, which may stress the crop.")
    else:
        eff = _EFFICIENCY.get(avail)
        if eff is None:
            eff = _EFFICIENCY["limited"]
            notes.append(f"Unknown irrigation_availability '{avail}'; assumed 'limited'.")
        gross = net / eff

    # Timing: days until root-zone depletion reaches the readily available water (RAW).
    days_to_next, next_date = None, ""
    if not rainfed:
        taw = _TAW_MM_PER_M.get(_soil_key(features.soil_texture))
        if taw is None:
            taw = _TAW_MM_PER_M["clay"]
            notes.append(f"Unknown soil_texture '{features.soil_texture}'; assumed clay.")
        root_m = 0.3 + (cfg["root_max_m"] - 0.3) * root_frac
        raw = cfg["p"] * taw * root_m
        wetness = min(1.0, max(0.0, features.soil_moisture_root))
        depletion = (1.0 - wetness) * taw * root_m            # GWETROOT used as relative wetness
        if etc <= 0:
            days_to_next = _MAX_DAYS_TO_NEXT
        else:
            days_to_next = int((raw - depletion + p_eff) // etc)
            days_to_next = max(0, min(_MAX_DAYS_TO_NEXT, days_to_next))
        next_date = (today + timedelta(days=days_to_next)).isoformat()

    notes.append("Simplified water-requirement estimate, not a full scheduling model: "
                 "ignores measured field moisture, irrigation method and rooting detail. "
                 "Treat the next-irrigation date as a prompt to check the field.")
    return IrrigationDetail(round(gross, 1), next_date, crop, stage, round(kc, 3),
                            round(et0, 2), round(etc, 2), round(net, 1), eff,
                            rainfed, days_to_next, notes)


def compute_irrigation(features: EnvironmentalFeatures) -> tuple[float, str]:
    """Frozen contract: (irrigation_mm_per_week, next_irrigation_date 'YYYY-MM-DD').
    next date is '' for rainfed fields (irrigation_availability == 'none')."""
    d = compute_irrigation_detail(features)
    return d.irrigation_mm_per_week, d.next_irrigation_date
