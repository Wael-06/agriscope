from app.schemas.contracts import EnvironmentalFeatures

def estimate_yield(features: EnvironmentalFeatures) -> tuple[float, str, str]:
    # Stub logic: Persons 3 & 4 replace with FAO Ky yield response formula
    ref_yields = {"wheat": 6200.0, "maize": 7800.0, "tomato": 38000.0, "sugarcane": 110000.0, "date_palm": 14000.0}
    base = ref_yields.get(features.crop.lower(), 4500.0)
    ndvi_modifier = 0.7 + (features.ndvi_current * 0.6)
    est = round(base * ndvi_modifier, 0)
    note = "Prototype estimate combining NASA POWER soil moisture, MODIS NDVI, and regional baseline; subject to local cultivar variance."
    return est, "Medium", note