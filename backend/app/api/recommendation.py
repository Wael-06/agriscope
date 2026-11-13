# pyright: reportMissingImports=false
from fastapi import APIRouter
from app.schemas.contracts import RecommendationRequest, RecommendationResponse, EnvironmentalFeatures
from app.services.nasa_power import get_power_summary
from app.services.modis import get_ndvi_summary
from app.services.open_meteo import get_weather_forecast
from app.engine.irrigation import compute_irrigation
from app.engine.rotation import recommend_rotations
from app.engine.yield_estimation import estimate_yield

router = APIRouter()

@router.post("/recommendation", response_model=RecommendationResponse)
def create_recommendation(req: RecommendationRequest):
    power = get_power_summary(req.lat, req.lon)
    modis = get_ndvi_summary(req.lat, req.lon)
    meteo = get_weather_forecast(req.lat, req.lon)

    features = EnvironmentalFeatures(
        lat=req.lat,
        lon=req.lon,
        crop=req.crop,
        field_size_ha=req.field_size_ha,
        planting_date=req.planting_date,
        avg_temp_c=power["avg_temp_c"],
        max_temp_c=power["max_temp_c"],
        total_precip_mm=power["total_precip_mm"],
        avg_solar_rad=power["avg_solar_rad"],
        soil_moisture_root=power["soil_moisture_root"],
        soil_moisture_top=power["soil_moisture_top"],
        ndvi_current=modis["ndvi_current"],
        ndvi_trend=modis["ndvi_trend"],
        forecast_precip_7d_mm=meteo["forecast_precip_7d_mm"],
        forecast_max_temp_c=meteo["forecast_max_temp_c"],
    )

    irrigation_mm, next_date = compute_irrigation(features)
    rotations = recommend_rotations(features)
    yield_kg, confidence, notes = estimate_yield(features)

    return RecommendationResponse(
        irrigation_mm_per_week=irrigation_mm,
        next_irrigation_date=next_date,
        rotation_recommendations=rotations,
        yield_estimate_kg_ha=yield_kg,
        confidence=confidence,
        notes=notes,
    )