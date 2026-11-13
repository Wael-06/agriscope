# pyright: reportMissingImports=false
from fastapi import APIRouter
from app.services.nasa_power import get_power_summary
from app.services.modis import get_ndvi_summary
from app.services.open_meteo import get_weather_forecast

router = APIRouter()

@router.get("/trends")
def get_trends(lat: float, lon: float):
    power = get_power_summary(lat, lon)
    modis = get_ndvi_summary(lat, lon)
    meteo = get_weather_forecast(lat, lon)
    return {
        "climate_history": power["series"],
        "ndvi_history": modis["series"],
        "forecast_7d": meteo["series"],
    }