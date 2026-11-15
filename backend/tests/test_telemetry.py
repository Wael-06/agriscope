import sqlite3

import pytest
from fastapi.testclient import TestClient

from app import main
from app.api import recommendation
from app.schemas.telemetry import TelemetryReading
from app.services import telemetry_store


@pytest.fixture
def telemetry_db(monkeypatch, tmp_path):
    monkeypatch.setattr(telemetry_store, "DB_PATH", tmp_path / "farm_cache.db")


def _reading(
    device_id: str = "node-1",
    soil_moisture_top: float = 0.4,
    temp_c: float = 21.0,
    source: str = "simulated",
) -> TelemetryReading:
    return TelemetryReading(
        device_id=device_id,
        lat=31.11,
        lon=30.94,
        soil_moisture_top=soil_moisture_top,
        temp_c=temp_c,
        humidity_pct=55.0,
        source=source,
    )


def test_telemetry_is_upserted_and_stale_rows_fail_closed(telemetry_db):
    telemetry_store.upsert_telemetry(_reading())
    assert telemetry_store.get_fresh_telemetry("node-1").source == "simulated"

    with sqlite3.connect(telemetry_store.DB_PATH) as conn:
        conn.execute(
            "UPDATE device_telemetry SET received_at = datetime('now', '-901 seconds')"
        )

    assert telemetry_store.get_fresh_telemetry("node-1") is None
    status = telemetry_store.get_telemetry_status("node-1")
    assert status["online"] is False
    assert status["last_seen"] is not None
    assert status["reading"] is None


def test_device_commands_are_one_shot_and_auto_trigger_is_debounced(telemetry_db):
    assert telemetry_store.set_command("node-1", True, 5, auto=True)
    assert not telemetry_store.set_command("node-1", True, 5, auto=True)
    assert telemetry_store.consume_command("node-1") == {
        "irrigate": True,
        "duration_sec": 5,
    }
    assert telemetry_store.consume_command("node-1") == {
        "irrigate": False,
        "duration_sec": 0,
    }

    with sqlite3.connect(telemetry_store.DB_PATH) as conn:
        conn.execute(
            """
            UPDATE device_commands
            SET last_auto_triggered_at = datetime('now', '-11 minutes')
            WHERE device_id = 'node-1'
            """
        )
    assert telemetry_store.set_command("node-1", True, 5, auto=True)


def test_telemetry_and_command_routes(telemetry_db):
    client = TestClient(main.app)
    response = client.post(
        "/api/telemetry",
        json={
            "device_id": "node-1",
            "lat": 31.11,
            "lon": 30.94,
            "soil_moisture_top": 0.31,
            "temp_c": 22.0,
            "humidity_pct": 50.0,
        },
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}

    status = client.get("/api/telemetry/node-1/status").json()
    assert status["online"] is True
    assert status["reading"]["source"] == "device"

    queued = client.post(
        "/api/device/command",
        params={"device_id": "node-1", "irrigate": "true", "duration_sec": 5},
    )
    assert queued.status_code == 200
    assert client.get("/api/device/command", params={"device_id": "node-1"}).json() == {
        "irrigate": True,
        "duration_sec": 5,
    }
    assert client.get("/api/device/command", params={"device_id": "node-1"}).json() == {
        "irrigate": False,
        "duration_sec": 0,
    }


def test_recommendation_default_is_unchanged_and_sensor_is_opt_in(monkeypatch):
    power = {
        "avg_temp_c": 20.0,
        "max_temp_c": 26.0,
        "total_precip_mm": 4.0,
        "avg_solar_rad": 15.0,
        "soil_moisture_root": 0.52,
        "soil_moisture_top": 0.4,
        "_fallback": False,
    }
    monkeypatch.setattr(recommendation, "get_power_summary", lambda *_: power)
    monkeypatch.setattr(
        recommendation,
        "get_ndvi_summary",
        lambda *_: {"ndvi_current": 0.5, "ndvi_trend": 0.02, "_fallback": False},
    )
    monkeypatch.setattr(
        recommendation,
        "get_weather_forecast",
        lambda *_: {
            "forecast_precip_7d_mm": 1.0,
            "forecast_max_temp_c": 25.0,
            "forecast_et0_mm_day": 3.0,
            "_fallback": False,
        },
    )
    observed_features = []
    monkeypatch.setattr(
        recommendation,
        "compute_irrigation",
        lambda features: (observed_features.append(features) or (12.0, "2026-11-20")),
    )
    monkeypatch.setattr(recommendation, "recommend_rotations", lambda *_: [])
    monkeypatch.setattr(recommendation, "score_baseline_rotation", lambda *_: None)
    monkeypatch.setattr(recommendation, "estimate_yield", lambda *_: (5000.0, "Medium", ""))
    monkeypatch.setattr(
        recommendation,
        "get_fresh_telemetry",
        lambda *_args, **_kwargs: pytest.fail("sensor lookup must be opt-in"),
    )
    client = TestClient(main.app)
    request = {
        "lat": 31.11,
        "lon": 30.94,
        "crop": "wheat",
        "field_size_ha": 2.5,
        "planting_date": "2026-11-15",
    }

    default_response = client.post("/recommendation", json=request)
    assert default_response.status_code == 200
    assert "satellite_soil_moisture_top" not in default_response.json()
    assert observed_features[-1].soil_moisture_top == 0.4
    assert observed_features[-1].avg_temp_c == 20.0

    auto_commands = []
    monkeypatch.setattr(
        recommendation,
        "get_fresh_telemetry",
        lambda *_args, **_kwargs: _reading(soil_moisture_top=0.2, temp_c=24.0),
    )
    monkeypatch.setattr(
        recommendation,
        "set_command",
        lambda *args, **kwargs: auto_commands.append((args, kwargs)),
    )
    enabled_response = client.post(
        "/recommendation",
        json={**request, "use_live_sensor": True, "device_id": "node-1"},
    )
    assert enabled_response.status_code == 200
    enabled_data = enabled_response.json()
    assert enabled_data["satellite_soil_moisture_top"] == 0.4
    assert "Calibrated with live field sensor." in enabled_data["notes"]
    assert observed_features[-1].soil_moisture_top == 0.2
    assert observed_features[-1].avg_temp_c == 24.0
    assert observed_features[-1].soil_moisture_root == 0.52
    assert len(auto_commands) == 1
    assert auto_commands[0][1] == {
        "irrigate": True,
        "duration_sec": 5,
        "auto": True,
    }
