from fastapi import APIRouter, Query

from app.schemas.telemetry import TelemetryReading
from app.services.telemetry_store import (
    consume_command,
    get_telemetry_status,
    set_command as store_set_command,
    upsert_telemetry,
)

router = APIRouter()


@router.post("/api/telemetry")
def ingest_telemetry(reading: TelemetryReading):
    upsert_telemetry(reading)
    return {"ok": True}


@router.get("/api/telemetry/{device_id}/status")
def telemetry_status(device_id: str):
    return get_telemetry_status(device_id)


@router.get("/api/device/command")
def poll_command(device_id: str):
    return consume_command(device_id)


@router.post("/api/device/command")
def set_command(
    device_id: str,
    irrigate: bool,
    duration_sec: int = Query(default=5, ge=0),
):
    store_set_command(device_id, irrigate, duration_sec)
    return {"ok": True}
