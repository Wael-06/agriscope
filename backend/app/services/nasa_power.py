import requests
import numpy as np
from datetime import datetime, timedelta
from app.services.cache import get_cached, set_cached

POWER_URL = "https://power.larc.nasa.gov/api/temporal/daily/point"

def get_power_summary(lat: float, lon: float) -> dict:
    # Round to ~1.1km grid so nearby map clicks hit the same cache entry
    rlat, rlon = round(lat, 2), round(lon, 2)
    cache_key = f"power:{rlat}:{rlon}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # NASA POWER has a ~3-day processing lag; pull the last 30 valid days
    end_dt = datetime.utcnow() - timedelta(days=4)
    start_dt = end_dt - timedelta(days=30)

    params = {
        "parameters": "T2M,T2M_MAX,PRECTOTCORR,ALLSKY_SFC_SW_DWN,GWETROOT,GWETTOP",
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
            vals = [v for v in raw.get(param_name, {}).values() if v is not None and v > -900]
            return vals if vals else [default]

        t2m = clean_vals("T2M", 22.0)
        tmax = clean_vals("T2M_MAX", 28.0)
        precip = clean_vals("PRECTOTCORR", 0.0)
        solar = clean_vals("ALLSKY_SFC_SW_DWN", 18.0)
        gwet_root = clean_vals("GWETROOT", 0.42)
        gwet_top = clean_vals("GWETTOP", 0.35)

        dates = sorted([d for d, v in raw.get("T2M", {}).items() if v > -900])
        result = {
            "avg_temp_c": round(float(np.mean(t2m)), 2),
            "max_temp_c": round(float(np.max(tmax)), 2),
            "total_precip_mm": round(float(np.sum(precip)), 2),
            "avg_solar_rad": round(float(np.mean(solar)), 2),
            "soil_moisture_root": round(float(np.mean(gwet_root)), 3),
            "soil_moisture_top": round(float(np.mean(gwet_top)), 3),
            "series": {
                "dates": [f"{d[:4]}-{d[4:6]}-{d[6:]}" for d in dates],
                "temp_c": [raw["T2M"][d] for d in dates],
                "precip_mm": [max(0.0, raw["PRECTOTCORR"][d]) for d in dates],
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
            "series": {"dates": [], "temp_c": [], "precip_mm": []},
        }
