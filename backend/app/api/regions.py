# pyright: reportMissingImports=false
import json
from pathlib import Path

from fastapi import APIRouter

from app.engine import country_models

router = APIRouter()

_EGYPT_REGIONS = [
    {"id": "nile_delta", "name": "Nile Delta (Kafr El-Sheikh)", "lat": 31.11, "lon": 30.94, "default_crop": "wheat", "soil": "Alluvial Clay", "country": "EGYPT"},
    {"id": "fayoum", "name": "Fayoum Oasis", "lat": 29.31, "lon": 30.84, "default_crop": "tomato", "soil": "Sandy Loam", "country": "EGYPT"},
    {"id": "upper_egypt", "name": "Upper Egypt (Minya)", "lat": 28.10, "lon": 30.75, "default_crop": "sugarcane", "soil": "Silty Clay", "country": "EGYPT"},
    {"id": "new_valley", "name": "New Valley (Kharga)", "lat": 25.44, "lon": 30.55, "default_crop": "date_palm", "soil": "Sandy", "country": "EGYPT"},
]
_COUNTRY_SITES_PATH = Path(__file__).resolve().parents[1] / "engine" / "models" / "country_sites.json"
_COUNTRY_DEFAULT_CROPS = {"USA": "maize", "CHINA": "wheat"}


@router.get("/regions")
def get_regions():
    country_sites = json.loads(_COUNTRY_SITES_PATH.read_text(encoding="utf-8"))
    country_regions = [
        {
            **site,
            "default_crop": _COUNTRY_DEFAULT_CROPS[site["country"]],
            "supported_crops": country_models.supported_yield_crops(site["country"]),
            "suitability_crops": country_models.supported_suitability_crops(site["country"]),
        }
        for site in country_sites
    ]
    return [*_EGYPT_REGIONS, *country_regions]