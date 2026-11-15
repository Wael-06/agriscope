# AgriScope

## Optional field sensor demo

The field-sensor feature is off by default. Enable **“I have a connected field sensor (ESP32)”** in the dashboard to include a fresh sensor reading in the recommendation. NASA POWER, Open-Meteo, and MODIS continue to provide the remaining environmental inputs.

To demo without hardware, start the FastAPI backend and run the simulator in a separate terminal:

```bash
cd backend
python simulate_device.py
```

The simulator posts to the same `/api/telemetry` endpoint as a device and identifies its readings with `source: "simulated"`. A real ESP32 can use that endpoint with `source: "device"`.