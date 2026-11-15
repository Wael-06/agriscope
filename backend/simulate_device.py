import json
import math
import random
import time
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


TELEMETRY_URL = "http://127.0.0.1:8000/api/telemetry"
DEVICE_ID = "demo-esp32-01"


def _reading(soil_moisture: float) -> tuple[dict, float]:
    now = datetime.now()
    hour_angle = 2 * math.pi * (now.hour + now.minute / 60 - 9) / 24
    temp_c = 20 + 6 * math.sin(hour_angle) + random.uniform(-0.3, 0.3)
    humidity_pct = max(25, min(90, 58 - (temp_c - 20) * 1.3 + random.uniform(-3, 3)))
    soil_moisture = max(0.2, min(0.5, soil_moisture + random.uniform(-0.015, 0.015)))
    return (
        {
            "device_id": DEVICE_ID,
            "lat": 31.11,
            "lon": 30.94,
            "soil_moisture_top": round(soil_moisture, 3),
            "temp_c": round(temp_c, 1),
            "humidity_pct": round(humidity_pct, 1),
            "source": "simulated",
        },
        soil_moisture,
    )


def main() -> None:
    soil_moisture = 0.35
    print(f"Simulated field node {DEVICE_ID} posting to {TELEMETRY_URL}; Ctrl+C to stop.")
    while True:
        payload, soil_moisture = _reading(soil_moisture)
        request = Request(
            TELEMETRY_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                response.read()
            print(
                f"Posted soil={payload['soil_moisture_top']:.3f}, "
                f"temp={payload['temp_c']:.1f} C, humidity={payload['humidity_pct']:.1f}%"
            )
        except HTTPError as exc:
            print(f"Telemetry API returned HTTP {exc.code}: {exc.reason}")
        except URLError as exc:
            print(f"Telemetry API unavailable: {exc.reason}")
        time.sleep(random.uniform(5, 10))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nSimulator stopped.")
