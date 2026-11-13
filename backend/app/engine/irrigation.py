from datetime import datetime, timedelta
from app.schemas.contracts import EnvironmentalFeatures

def compute_irrigation(features: EnvironmentalFeatures) -> tuple[float, str]:
    # Stub logic: Persons 3 & 4 replace with FAO-56 ETc / soil water balance
    base_need = 35.0
    deficit_factor = max(0.5, 1.2 - features.soil_moisture_root)
    mm_per_week = round(max(0.0, (base_need * deficit_factor) - features.forecast_precip_7d_mm), 1)
    days_until = 2 if features.soil_moisture_top < 0.35 else 5
    next_date = (datetime.utcnow() + timedelta(days=days_until)).strftime("%Y-%m-%d")
    return mm_per_week, next_date