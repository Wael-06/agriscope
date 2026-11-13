# pyright: reportMissingImports=false
from fastapi import APIRouter

router = APIRouter()

@router.get("/regions")
def get_regions():
    return [
        {"id": "nile_delta", "name": "Nile Delta (Kafr El-Sheikh)", "lat": 31.11, "lon": 30.94, "default_crop": "wheat", "soil": "Alluvial Clay"},
        {"id": "fayoum", "name": "Fayoum Oasis", "lat": 29.31, "lon": 30.84, "default_crop": "tomato", "soil": "Sandy Loam"},
        {"id": "upper_egypt", "name": "Upper Egypt (Minya)", "lat": 28.10, "lon": 30.75, "default_crop": "sugarcane", "soil": "Silty Clay"},
        {"id": "new_valley", "name": "New Valley (Kharga)", "lat": 25.44, "lon": 30.55, "default_crop": "date_palm", "soil": "Sandy"},
    ]