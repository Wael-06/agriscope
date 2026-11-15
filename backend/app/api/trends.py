# pyright: reportMissingImports=false
from fastapi import APIRouter, Query
from app.services.nasa_power import get_power_summary
from app.services.modis import get_ndvi_summary
from app.services.open_meteo import get_weather_forecast

router = APIRouter()

@router.get("/trends")
def get_trends(
    lat: float,
    lon: float,
    history_days: int = Query(30, ge=30, le=365, description="NASA POWER daily history length"),
):
    power = get_power_summary(lat, lon, history_days=history_days)
    modis = get_ndvi_summary(lat, lon)
    meteo = get_weather_forecast(lat, lon)
    return {
        "climate_history": power["series"],
        "ndvi_history": modis["series"],
        "forecast_7d": meteo["series"],
        "fallback_sources": [
            source
            for source, data in (
                ("NASA POWER", power),
                ("MODIS NDVI", modis),
                ("Open-Meteo", meteo),
            )
            if data.get("_fallback")
        ],
    }