from pydantic import BaseModel


class TelemetryReading(BaseModel):
    device_id: str
    lat: float
    lon: float
    soil_moisture_top: float
    temp_c: float
    humidity_pct: float
    source: str = "device"


class DeviceCommand(BaseModel):
    irrigate: bool
    duration_sec: int = 0
