from fastapi import APIRouter
from app.schemas.contracts import RecommendationRequest, RecommendationResponse, EnvironmentalFeatures
from app.services.nasa_power import get_power_summary
from app.services.modis import get_ndvi_summary
from app.services.open_meteo import get_weather_forecast
from app.services.telemetry_store import get_fresh_telemetry, set_command
from app.engine.irrigation import compute_irrigation
from app.engine.rotation import recommend_rotations, score_baseline_rotation
from app.engine.yield_estimation import estimate_yield
from app.engine.climatology import fallback_forecast

router = APIRouter()

_FALLBACK_SOIL_MOISTURE = {
    "sand": (0.32, 0.25),
    "loam": (0.50, 0.42),
    "clay": (0.65, 0.58),
}
_FALLBACK_IRRIGATION_ADJUSTMENT = {
    "available": 0.08,
    "limited": 0.0,
    "none": -0.12,
}


def _fallback_soil_moisture(soil_texture: str | None,
                            irrigation_availability: str | None) -> tuple[float, float]:
    soil_key = (soil_texture or "clay").strip().lower().replace("-", "_").replace(" ", "_")
    soil_key = {
        "sandy": "sand",
        "sandy_loam": "loam",
        "clay_loam": "loam",
        "alluvial_clay": "clay",
        "silty_clay": "clay",
    }.get(soil_key, soil_key)
    root, top = _FALLBACK_SOIL_MOISTURE.get(soil_key, _FALLBACK_SOIL_MOISTURE["clay"])
    adjustment = _FALLBACK_IRRIGATION_ADJUSTMENT.get(
        (irrigation_availability or "limited").strip().lower(),
        _FALLBACK_IRRIGATION_ADJUSTMENT["limited"],
    )
    return round(min(1.0, max(0.0, root + adjustment)), 3), round(
        min(1.0, max(0.0, top + adjustment)), 3
    )


@router.post(
    "/recommendation",
    response_model=RecommendationResponse,
    response_model_exclude_unset=True,
)
def create_recommendation(req: RecommendationRequest):
    month = int(req.planting_date[5:7])
    source_note = ""
    fallback_sources = []

    try:
        power = get_power_summary(req.lat, req.lon)
        modis = get_ndvi_summary(req.lat, req.lon)
        meteo = get_weather_forecast(req.lat, req.lon)
        fallback_sources = [
            source
            for source, data in (
                ("NASA POWER", power),
                ("MODIS NDVI", modis),
                ("Open-Meteo", meteo),
            )
            if data.get("_fallback")
        ]

        env = {
            "avg_temp_c": power["avg_temp_c"],
            "max_temp_c": power["max_temp_c"],
            "total_precip_mm": power["total_precip_mm"],
            "avg_solar_rad": power["avg_solar_rad"],
            "soil_moisture_root": power["soil_moisture_root"],
            "soil_moisture_top": power["soil_moisture_top"],
            "ndvi_current": modis["ndvi_current"],
            "ndvi_trend": modis["ndvi_trend"],
            "forecast_precip_7d_mm": meteo["forecast_precip_7d_mm"],
            "forecast_max_temp_c": meteo["forecast_max_temp_c"],
            "forecast_et0_mm_day": meteo["forecast_et0_mm_day"],
        }
    except Exception as e:
        import logging
        logging.warning(
            "Recommendation data fetch failed for %s,%s; using fallback: %s",
            req.lat, req.lon, e,
        )
        fallback_sources = ["NASA POWER", "MODIS NDVI", "Open-Meteo"]
        clim = fallback_forecast(req.lat, req.lon, month)
        source_note = f" Weather is {clim['_source']}, not live data."
        source_note += " Soil moisture is estimated from soil texture and irrigation access."
        env = {k: v for k, v in clim.items() if not k.startswith("_")}
        soil_moisture_root, soil_moisture_top = _fallback_soil_moisture(
            req.soil_texture, req.irrigation_availability
        )
        env.update(
            ndvi_current=0.4,
            ndvi_trend=0.0,
            avg_solar_rad=15.0,
            soil_moisture_root=soil_moisture_root,
            soil_moisture_top=soil_moisture_top,
        )

    sensor_note = ""
    satellite_soil_moisture_top = None
    if req.use_live_sensor and req.device_id:
        fresh = get_fresh_telemetry(req.device_id, max_age_seconds=900)
        satellite_soil_moisture_top = env["soil_moisture_top"]
        if fresh:
            env["soil_moisture_top"] = fresh.soil_moisture_top
            env["avg_temp_c"] = fresh.temp_c
            sensor_note = " Calibrated with live field sensor."
            if fresh.soil_moisture_top < 0.25:
                set_command(req.device_id, irrigate=True, duration_sec=5, auto=True)

    feature_kwargs = dict(
        lat=req.lat,
        lon=req.lon,
        crop=req.crop,
        previous_crop=req.previous_crop,
        field_size_ha=req.field_size_ha,
        planting_date=req.planting_date,
        soil_texture=req.soil_texture or "clay",
        irrigation_availability=req.irrigation_availability or "available",
        planning_horizon_seasons=req.planning_horizon_seasons,
        **env,
    )
    if req.rotation_priority_weights:
        feature_kwargs["rotation_priority_weights"] = req.rotation_priority_weights

    features = EnvironmentalFeatures(**feature_kwargs)

    irrigation_mm, next_date = compute_irrigation(features)
    rotations = recommend_rotations(features)
    baseline_score = score_baseline_rotation(features)
    yield_kg, confidence, y_note = estimate_yield(features)

    return RecommendationResponse(
        irrigation_mm_per_week=irrigation_mm,
        next_irrigation_date=next_date,
        rotation_recommendations=rotations,
        baseline_score=baseline_score,
        fallback_sources=fallback_sources,
        yield_estimate_kg_ha=yield_kg,
        confidence=confidence,
        notes=(y_note + source_note + sensor_note).strip(),
        soil_texture=features.soil_texture,
        irrigation_availability=features.irrigation_availability,
        **(
            {"satellite_soil_moisture_top": satellite_soil_moisture_top}
            if satellite_soil_moisture_top is not None
            else {}
        ),
    )
