
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

OUT = Path(__file__).parent / "data"
DEFAULT_CSV = Path(__file__).resolve().parents[3] / "data" / "raw" / "egypt_4loc_5crops.csv"

CROP_NAMES = {"Wheat": "wheat", "Maize": "maize", "Rice, paddy": "rice",
              "Tomatoes": "tomato", "Cotton seed": "cotton"}
REGION_NAMES = {"nile_delta": ("Nile Delta (Kafr El-Sheikh)", "wheat"),
                "fayoum": ("Fayoum Oasis", "wheat"),
                "upper_egypt": ("Upper Egypt", "maize"),
                "new_valley": ("New Valley (Kharga)", "wheat")}
SOIL_TO_TEXTURE = {"Alluvial Clay": "clay", "Silty Clay": "silty_clay",
                   "Sandy Loam": "sandy_loam", "Sandy": "sand"}


def hargreaves_et0(tmean, tmax, tmin, lat_deg, doy):
    """FAO-56 Hargreaves reference ET0 (mm/day) from temperature only."""
    phi = math.radians(lat_deg)
    dr = 1 + 0.033 * np.cos(2 * math.pi * doy / 365)
    delta = 0.409 * np.sin(2 * math.pi * doy / 365 - 1.39)
    ws = np.arccos(np.clip(-math.tan(phi) * np.tan(delta), -1, 1))
    ra = (24 * 60 / math.pi) * 0.0820 * dr * (
        ws * math.sin(phi) * np.sin(delta) + math.cos(phi) * np.cos(delta) * np.sin(ws))
    ra_mm = ra / 2.45
    return np.maximum(0.0, 0.0023 * (tmean + 17.8) * np.sqrt(np.maximum(tmax - tmin, 0)) * ra_mm)


def main(csv_path: Path):
    df = pd.read_csv(csv_path).rename(columns={"hg/ha_yield": "y"})
    OUT.mkdir(parents=True, exist_ok=True)

    # 1. yield history (national, one value per crop-year)
    yh = df.dropna(subset=["y"]).groupby(["Item", "Year"]).y.first().reset_index()
    yh["crop"] = yh.Item.map(CROP_NAMES)
    yh["yield_kg_ha"] = (yh.y / 10).round(0)
    yh[["crop", "Year", "yield_kg_ha"]].rename(columns={"Year": "year"}).to_csv(
        OUT / "yield_history.csv", index=False)

    base = {}
    for crop, g in yh.groupby("crop"):
        g = g.sort_values("Year")
        recent = g.tail(5).yield_kg_ha
        base[crop] = {"n_years": int(len(g)), "first_year": int(g.Year.min()),
                      "last_year": int(g.Year.max()),
                      "recent_mean_kg_ha": round(float(recent.mean()), 0),
                      "recent_std_kg_ha": round(float(recent.std(ddof=0)), 0),
                      "all_mean_kg_ha": round(float(g.yield_kg_ha.mean()), 0),
                      "all_std_kg_ha": round(float(g.yield_kg_ha.std(ddof=0)), 0),
                      "min_kg_ha": float(g.yield_kg_ha.min()),
                      "max_kg_ha": float(g.yield_kg_ha.max()),
                      "source": "national annual yield in supplied CSV (FAOSTAT-style); not field-level"}
    for c in ("cotton",):  # in the CSV but with no yield values
        base.setdefault(c, {"n_years": 0, "source": "no yield values in supplied CSV"})
    (OUT / "yield_baseline.json").write_text(json.dumps(base, indent=2))

    # 2. climatology (weather is duplicated once per crop/rotation row: dedupe first)
    w = df.drop_duplicates(["location_id", "Year", "Month", "Day"]).copy()
    w["doy"] = pd.to_datetime(dict(year=w.Year, month=w.Month, day=w.Day)).dt.dayofyear
    w["et0"] = [hargreaves_et0(t, tx, tn, la, d) for t, tx, tn, la, d in
                zip(w.avg_temp, w.max_temp, w.min_temp, w.lat, w.doy)]
    clim = {}
    for loc, g in w.groupby("location_id"):
        years = g.Year.nunique()
        months = {}
        for m, gm in g.groupby("Month"):
            months[int(m)] = {"tavg_c": round(gm.avg_temp.mean(), 2),
                              "tmax_c": round(gm.max_temp.mean(), 2),
                              "tmin_c": round(gm.min_temp.mean(), 2),
                              "rain_mm_per_week": round(gm.rain_mm_per_day.mean() * 7, 2),
                              "et0_mm_day": round(gm.et0.mean(), 2),
                              "humidity_pct": round(gm.rel_humidity.mean(), 1)}
        clim[loc] = {"lat": float(g.lat.iloc[0]), "lon": float(g.lon.iloc[0]),
                     "soil": g.soil.iloc[0], "years_of_data": int(years),
                     "et0_method": "Hargreaves (temperature-only), approximate", "monthly": months}
    (OUT / "climatology.json").write_text(json.dumps(clim, indent=2))

    # 3. regions for /regions
    regions = []
    for loc, g in w.groupby("location_id"):
        name, crop = REGION_NAMES.get(loc, (loc, "wheat"))
        regions.append({"id": loc, "name": name, "lat": float(g.lat.iloc[0]),
                        "lon": float(g.lon.iloc[0]), "default_crop": crop,
                        "soil": g.soil.iloc[0],
                        "soil_texture": SOIL_TO_TEXTURE.get(g.soil.iloc[0], "clay")})
    (OUT / "regions.json").write_text(json.dumps(regions, indent=2))
    print("wrote", [p.name for p in OUT.iterdir()])


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV)
