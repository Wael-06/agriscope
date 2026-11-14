import requests
from app.services.cache import get_cached, set_cached

METEO_URL = "https://api.open-meteo.com/v1/forecast"

def get_weather_forecast(lat: float, lon: float) -> dict:
    rlat, rlon = round(lat, 2), round(lon, 2)
    cache_key = f"meteo:{rlat}:{rlon}"
    cached = get_cached(cache_key)
    if cached:
        return cached

    params = {
        "latitude": rlat,
        "longitude": rlon,
        "daily": "temperature_2m_max,precipitation_sum,et0_fao_evapotranspiration",
        "forecast_days": 7,
        "timezone": "auto",
    }
    try:
        resp = requests.get(METEO_URL, params=params, timeout=8)
        resp.raise_for_status()
        daily = resp.json()["daily"]
        et0_values = daily.get("et0_fao_evapotranspiration") or [4.2]
        result = {
            "forecast_et0_mm_day": round(sum(et0_values) / len(et0_values), 2),
            "forecast_precip_7d_mm": round(sum(daily["precipitation_sum"]), 2),
            "forecast_max_temp_c": round(max(daily["temperature_2m_max"]), 2),
            "series": {
                "dates": daily["time"],
                "max_temp_c": daily["temperature_2m_max"],
                "precip_mm": daily["precipitation_sum"],
            }
        }
        set_cached(cache_key, result)
        return result
    except Exception as e:
        import logging
        logging.warning(f"open_meteo fetch failed for {rlat},{rlon}: {e}")
        return {
            "forecast_et0_mm_day": 4.2,
            "forecast_precip_7d_mm": 0.0,
            "forecast_max_temp_c": 26.0,
            "series": {},
        }
