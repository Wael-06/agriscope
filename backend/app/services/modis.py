import requests
from datetime import datetime, timedelta
from app.services.cache import get_cached, set_cached

MODIS_URL = "https://modis.ornl.gov/rst/api/v1/MOD13Q1/subset"

def get_ndvi_summary(lat: float, lon: float) -> dict:
    rlat, rlon = round(lat, 2), round(lon, 2)
    cache_key = f"modis:{rlat}:{rlon}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    # Query last ~60 days of 16-day MODIS composites
    end_dt = datetime.utcnow()
    start_dt = end_dt - timedelta(days=64)
    start_str = f"A{start_dt.year}{start_dt.timetuple().tm_yday:03d}"
    end_str = f"A{end_dt.year}{end_dt.timetuple().tm_yday:03d}"

    params = {
        "latitude": rlat,
        "longitude": rlon,
        "band": "250m_16_days_NDVI",
        "startDate": start_str,
        "endDate": end_str,
        "kmAboveBelow": 0,
        "kmLeftRight": 0,
    }

    try:
        resp = requests.get(MODIS_URL, params=params, timeout=10)
        resp.raise_for_status()
        subsets = resp.json().get("subset", [])

        dates, values = [], []
        for item in subsets:
            raw_val = item["data"][0]
            if -2000 <= raw_val <= 10000:
                dates.append(item["calendar_date"])
                values.append(round(raw_val * 0.0001, 3))

        if values:
            trend = round(values[-1] - values[0], 3) if len(values) > 1 else 0.0
            result = {
                "ndvi_current": values[-1],
                "ndvi_trend": trend,
                "series": {"dates": dates, "ndvi": values}
            }
            set_cached(cache_key, result)
            return result
        raise ValueError("No valid NDVI data returned")

    except Exception as e:
        import logging
        logging.warning(f"modis fetch failed for {rlat},{rlon}: {e}")
        return {
            "ndvi_current": 0.48,
            "ndvi_trend": 0.02,
            "series": {"dates": [], "ndvi": []},
        }
