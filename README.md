# AgriScope

## Vulnerability and trend map

The Earth Intelligence view charts up to 365 days of NASA POWER daily temperature and root-zone wetness data for the selected point. The map timeline compares the selected point with preset regional points where data is available; click a chart date or use the slider to inspect daily heat, frost, or low-wetness screening flags. The standard `/trends` response remains 30 days unless requested with `history_days=365`.

These are coarse point samples, not field-boundary measurements. NASA POWER root-zone wetness is not reservoir or groundwater storage, and the app does not currently have the soil and terrain inputs needed to map erosion risk.

## Optional field sensor demo

The field-sensor feature is off by default. Enable **“I have a connected field sensor (ESP32)”** in the dashboard to include a fresh sensor reading in the recommendation. NASA POWER, Open-Meteo, and MODIS continue to provide the remaining environmental inputs.

To demo without hardware, start the FastAPI backend and run the simulator in a separate terminal:

```bash
cd backend
python simulate_device.py
```

The simulator posts to the same `/api/telemetry` endpoint as a device and identifies its readings with `source: "simulated"`. A real ESP32 can use that endpoint with `source: "device"`.