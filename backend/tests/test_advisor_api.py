from fastapi.testclient import TestClient

from app.api import recommendation
from app.main import app
from app.schemas.contracts import EnvironmentalFeatures


def test_advisor_endpoint_returns_advice_for_field_inputs(monkeypatch):
    features = EnvironmentalFeatures(
        lat=31.11,
        lon=30.94,
        crop="wheat",
        field_size_ha=2.5,
        planting_date="2026-11-15",
        avg_temp_c=20.5,
        max_temp_c=28.5,
        total_precip_mm=3.0,
        avg_solar_rad=14.0,
        soil_moisture_root=0.55,
        soil_moisture_top=0.4,
        ndvi_current=0.55,
        ndvi_trend=0.02,
        forecast_precip_7d_mm=0.0,
        forecast_max_temp_c=25.0,
        forecast_et0_mm_day=3.1,
        soil_texture="clay",
        irrigation_availability="limited",
    )
    monkeypatch.setattr(
        recommendation,
        "_build_environmental_features",
        lambda req, auto_irrigate=True: (features, [], "", "", None),
    )
    received = {}

    def fake_advise(field_features, language, question):
        received.update(features=field_features, language=language, question=question)
        return {
            "advice": "Check soil moisture before irrigation.",
            "used_llm": True,
            "sources": [{"title": "Source", "url": "https://example.com"}],
            "error": None,
            "model": "test-model",
            "facts": {"crop_now": "wheat"},
        }

    monkeypatch.setattr(recommendation, "advise", fake_advise)
    response = TestClient(app).post(
        "/advisor",
        json={
            "lat": 31.11,
            "lon": 30.94,
            "crop": "wheat",
            "field_size_ha": 2.5,
            "planting_date": "2026-11-15",
            "soil_texture": "clay",
            "irrigation_availability": "limited",
            "language": "ar",
            "question": "When should I irrigate?",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "advice": "Check soil moisture before irrigation.",
        "used_llm": True,
        "sources": [{"title": "Source", "url": "https://example.com"}],
        "error": None,
        "model": "test-model",
        "facts": {"crop_now": "wheat"},
    }
    assert received == {
        "features": features,
        "language": "ar",
        "question": "When should I irrigate?",
    }
