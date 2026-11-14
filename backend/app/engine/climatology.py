
import json
import math
from pathlib import Path

_CLIM = json.loads((Path(__file__).parent / "data" / "climatology.json").read_text())


def _km(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2 +
         math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371 * 2 * math.asin(math.sqrt(a))


def fallback_forecast(lat: float, lon: float, month: int) -> dict:
    """Nearest of the 4 reference locations -> typical month values for EnvironmentalFeatures."""
    loc_id, loc = min(_CLIM.items(), key=lambda kv: _km(lat, lon, kv[1]["lat"], kv[1]["lon"]))
    m = loc["monthly"][str(month)]
    return {"forecast_precip_7d_mm": m["rain_mm_per_week"],
            "forecast_max_temp_c": m["tmax_c"],
            "forecast_et0_mm_day": m["et0_mm_day"],
            "avg_temp_c": m["tavg_c"], "max_temp_c": m["tmax_c"],
            "total_precip_mm": round(m["rain_mm_per_week"] * 30 / 7, 1),
            "_source": f"climatological average, nearest reference site: {loc_id}",
            "_km_to_site": round(_km(lat, lon, loc["lat"], loc["lon"]), 0)}
