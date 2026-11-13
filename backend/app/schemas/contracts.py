# pyright: reportMissingImports=false
from pydantic import BaseModel
from typing import List, Optional

class RecommendationRequest(BaseModel):
    lat: float
    lon: float
    crop: str
    field_size_ha: float
    planting_date: str  # YYYY-MM-DD

class EnvironmentalFeatures(BaseModel):
    lat: float
    lon: float
    crop: str
    field_size_ha: float
    planting_date: str
    avg_temp_c: float
    max_temp_c: float
    total_precip_mm: float
    avg_solar_rad: float
    soil_moisture_root: float
    soil_moisture_top: float
    ndvi_current: float
    ndvi_trend: float
    forecast_precip_7d_mm: float
    forecast_max_temp_c: float

class RotationOption(BaseModel):
    crop: str
    score: float
    reason: str

class RecommendationResponse(BaseModel):
    irrigation_mm_per_week: float
    next_irrigation_date: str
    rotation_recommendations: List[RotationOption]
    yield_estimate_kg_ha: float
    confidence: str
    notes: str
