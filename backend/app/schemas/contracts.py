# pyright: reportMissingImports=false
from pydantic import BaseModel, Field
from typing import List, Optional

class RecommendationRequest(BaseModel):
    lat: float
    lon: float
    crop: str
    field_size_ha: float
    planting_date: str  # YYYY-MM-DD
    previous_crop: Optional[str] = None
    soil_texture: Optional[str] = None
    irrigation_availability: Optional[str] = None

class RotationOption(BaseModel):
    crop: str
    score: float
    reason: str

class EnvironmentalFeatures(BaseModel):
    lat: float
    lon: float
    crop: str
    field_size_ha: float
    planting_date: str          # "YYYY-MM-DD"
    avg_temp_c: float           # 30-day mean temperature (C)
    max_temp_c: float           # 30-day peak temperature (C)
    total_precip_mm: float      # 30-day cumulative rainfall (mm)
    avg_solar_rad: float        # 30-day solar irradiance (MJ/m2/day)
    soil_moisture_root: float   # NASA GWETROOT, 0.0-1.0
    soil_moisture_top: float    # NASA GWETTOP, 0.0-1.0
    ndvi_current: float         # latest MODIS NDVI, -0.2 to 1.0
    ndvi_trend: float           # change over last 60 days
    forecast_precip_7d_mm: float
    forecast_max_temp_c: float
    forecast_et0_mm_day: float
    soil_texture: str = "clay"
    irrigation_availability: str = "available"  # "available" | "limited" | "none"
    planning_horizon_seasons: int = 3
    rotation_priority_weights: dict = Field(default_factory=lambda: {
        "soil_health": 0.35,
        "water_demand": 0.30,
        "climate_suitability": 0.25,
        "rotation_diversity": 0.10,
    })
    min_temp_c: Optional[float] = None
    rel_humidity_pct: Optional[float] = None


class RecommendationResponse(BaseModel):
    irrigation_mm_per_week: float
    next_irrigation_date: str
    rotation_recommendations: List[RotationOption]
    yield_estimate_kg_ha: float
    confidence: str
    notes: str
    soil_texture: str = "clay"
    irrigation_availability: str = "available"