import json
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "farm_cache.db"

DEMO_REGIONS = [
    {"id": "nile_delta", "lat": 31.11, "lon": 30.94, "temp_base": 22.0, "precip_scale": 1.2, "ndvi_base": 0.56, "sm_root": 0.48, "sm_top": 0.40},
    {"id": "fayoum", "lat": 29.31, "lon": 30.84, "temp_base": 23.8, "precip_scale": 0.5, "ndvi_base": 0.49, "sm_root": 0.42, "sm_top": 0.34},
    {"id": "upper_egypt", "lat": 28.10, "lon": 30.75, "temp_base": 25.4, "precip_scale": 0.2, "ndvi_base": 0.52, "sm_root": 0.44, "sm_top": 0.35},
    {"id": "new_valley", "lat": 25.44, "lon": 30.55, "temp_base": 27.6, "precip_scale": 0.0, "ndvi_base": 0.36, "sm_root": 0.31, "sm_top": 0.24},
]

def build_power_payload(reg: dict) -> dict:
    tb = reg["temp_base"]
    ps = reg["precip_scale"]
    dates = [
        "2026-10-15", "2026-10-18", "2026-10-21", "2026-10-24", "2026-10-27",
        "2026-10-30", "2026-11-02", "2026-11-05", "2026-11-08", "2026-11-11"
    ]
    temps = [round(tb + d, 1) for d in [2.1, 1.8, 1.4, 0.9, 0.5, 0.1, -0.4, -0.8, -1.2, -1.5]]
    precips = [round(p * ps, 1) for p in [0.0, 0.5, 0.0, 1.2, 0.0, 0.0, 2.0, 0.0, 0.4, 0.0]]
    return {
        "avg_temp_c": round(sum(temps) / len(temps), 2),
        "max_temp_c": round(max(temps) + 4.5, 2),
        "total_precip_mm": round(sum(precips), 2),
        "avg_solar_rad": 18.6,
        "soil_moisture_root": reg["sm_root"],
        "soil_moisture_top": reg["sm_top"],
        "series": {
            "dates": dates,
            "temp_c": temps,
            "precip_mm": precips,
        },
    }

def build_modis_payload(reg: dict) -> dict:
    nb = reg["ndvi_base"]
    dates = ["2026-09-14", "2026-09-30", "2026-10-16", "2026-11-01", "2026-11-12"]
    values = [round(nb - 0.08, 3), round(nb - 0.05, 3), round(nb - 0.02, 3), round(nb, 3), round(nb + 0.02, 3)]
    return {
        "ndvi_current": values[-1],
        "ndvi_trend": round(values[-1] - values[0], 3),
        "series": {
            "dates": dates,
            "ndvi": values,
        },
    }

def build_meteo_payload(reg: dict) -> dict:
    tb = reg["temp_base"]
    ps = reg["precip_scale"]
    dates = ["2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"]
    max_temps = [round(tb + d, 1) for d in [3.0, 2.6, 2.1, 1.8, 2.2, 2.7, 3.1]]
    precips = [round(p * ps, 1) for p in [0.0, 0.0, 1.5, 0.5, 0.0, 0.0, 0.0]]
    return {
        "forecast_precip_7d_mm": round(sum(precips), 2),
        "forecast_max_temp_c": round(max(max_temps), 2),
        "series": {
            "dates": dates,
            "max_temp_c": max_temps,
            "precip_mm": precips,
        },
    }

def seed_farm_cache() -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_cache (
                cache_key TEXT PRIMARY KEY,
                payload TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        for reg in DEMO_REGIONS:
            rlat, rlon = round(reg["lat"], 2), round(reg["lon"], 2)
            entries = {
                f"power:{rlat}:{rlon}": build_power_payload(reg),
                f"modis:{rlat}:{rlon}": build_modis_payload(reg),
                f"meteo:{rlat}:{rlon}": build_meteo_payload(reg),
            }
            for key, payload in entries.items():
                conn.execute(
                    "INSERT OR REPLACE INTO api_cache (cache_key, payload) VALUES (?, ?)",
                    (key, json.dumps(payload)),
                )
        conn.commit()
    print(f"Pre-warmed 12 cache entries into: {DB_PATH}")

if __name__ == "__main__":
    seed_farm_cache()
