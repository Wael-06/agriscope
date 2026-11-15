import requests
import numpy as np
from datetime import datetime, timedelta, timezone
from app.services.cache import get_cached, set_cached

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

def get_power_summary(lat: float, lon: float, history_days: int = 30) -> dict:
    # Round to ~1.1km grid so nearby map clicks hit the same cache entry
    rlat, rlon = round(lat, 2), round(lon, 2)
    cache_key = f"power_vulnerability_v1:{rlat}:{rlon}:{history_days}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # NASA POWER has a ~3-day processing lag; keep the requested daily window.
    end_dt = datetime.now(timezone.utc) - timedelta(days=4)
    start_dt = end_dt - timedelta(days=history_days - 1)

    params = {
        "parameters": "T2M,T2M_MAX,T2M_MIN,PRECTOTCORR,ALLSKY_SFC_SW_DWN,GWETROOT,GWETTOP",
        "community": "AG",
        "longitude": rlon,
        "latitude": rlat,
        "start": start_dt.strftime("%Y%m%d"),
        "end": end_dt.strftime("%Y%m%d"),
        "format": "JSON",
    }

    try:
        resp = requests.get(POWER_URL, params=params, timeout=12)
        resp.raise_for_status()
        raw = resp.json()["properties"]["parameter"]

        def clean_vals(param_name: str, default: float) -> list[float]:
            vals = [
                v for v in raw.get(param_name, {}).values()
                if isinstance(v, (int, float)) and v > -900
            ]
            return vals if vals else [default]

        t2m = clean_vals("T2M", 22.0)
        tmax = clean_vals("T2M_MAX", 28.0)
        precip = clean_vals("PRECTOTCORR", 0.0)
        solar = clean_vals("ALLSKY_SFC_SW_DWN", 18.0)
        gwet_root = clean_vals("GWETROOT", 0.42)
        gwet_top = clean_vals("GWETTOP", 0.35)

        dates = sorted([
            d for d, value in raw.get("T2M", {}).items()
            if isinstance(value, (int, float)) and value > -900
        ])

        def safe_day_val(param_name: str, day_key: str) -> float | None:
            value = raw.get(param_name, {}).get(day_key)
            return round(float(value), 3) if isinstance(value, (int, float)) and value > -900 else None

        result = {
            "avg_temp_c": round(float(np.mean(t2m)), 2),
            "max_temp_c": round(float(np.max(tmax)), 2),
            "total_precip_mm": round(float(np.sum(precip)), 2),
            "avg_solar_rad": round(float(np.mean(solar)), 2),
            "soil_moisture_root": round(float(np.mean(gwet_root)), 3),
            "soil_moisture_top": round(float(np.mean(gwet_top)), 3),
            "series": {
                "dates": [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in dates],
                "temp_c": [safe_day_val("T2M", d) for d in dates],
                "temp_max_c": [safe_day_val("T2M_MAX", d) for d in dates],
                "temp_min_c": [safe_day_val("T2M_MIN", d) for d in dates],
                "precip_mm": [
                    max(0.0, value) if value is not None else None
                    for value in (safe_day_val("PRECTOTCORR", d) for d in dates)
                ],
                "soil_moisture": [safe_day_val("GWETROOT", d) for d in dates],
            }
        }
        set_cached(cache_key, result)
        return result
    except Exception as e:
        import logging
        logging.warning(f"nasa_power fetch failed for {rlat},{rlon}: {e}")
        return {
            "_fallback": True,
            "avg_temp_c": 22.4,
            "max_temp_c": 28.5,
            "total_precip_mm": 3.8,
            "avg_solar_rad": 18.2,
            "soil_moisture_root": 0.44,
            "soil_moisture_top": 0.36,
            "series": {
                "dates": [],
                "temp_c": [],
                "temp_max_c": [],
                "temp_min_c": [],
                "precip_mm": [],
                "soil_moisture": [],
            },
        }
