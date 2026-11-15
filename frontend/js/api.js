const API_BASE_URL = (
  window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost"
) ? "http://127.0.0.1:8000" : "";

const KC_TABLE = {
  wheat: { kc: 1.15, stage: "Mid-season" },
  maize: { kc: 1.20, stage: "Mid-season" },
  cotton: { kc: 1.15, stage: "Mid-season" },
  tomato: { kc: 1.15, stage: "Mid-season" },
  sugarcane: { kc: 1.25, stage: "Mid-season" },
  date_palm: { kc: 0.95, stage: "Mature" },
  rice: { kc: 1.20, stage: "Mid-season" }
};

const FALLBACK_REGIONS = [
  { id: "nile_delta", name: "Nile Delta (Kafr El-Sheikh)", lat: 31.11, lon: 30.94, default_crop: "wheat", soil: "Alluvial Clay" },
  { id: "fayoum", name: "Fayoum Oasis", lat: 29.31, lon: 30.84, default_crop: "tomato", soil: "Sandy Loam" },
  { id: "upper_egypt", name: "Upper Egypt (Minya)", lat: 28.10, lon: 30.75, default_crop: "sugarcane", soil: "Silty Clay" },
  { id: "new_valley", name: "New Valley (Kharga)", lat: 25.44, lon: 30.55, default_crop: "date_palm", soil: "Sandy" },
  { id: "iowa", name: "Ames, Iowa", lat: 42.03, lon: -93.62, country: "USA", default_crop: "maize", supported_crops: ["wheat", "maize", "rice", "tomato", "cotton", "sugarcane", "date_palm"], suitability_crops: ["maize", "cotton"] },
  { id: "henan", name: "Zhengzhou, Henan", lat: 34.75, lon: 113.62, country: "CHINA", default_crop: "wheat", supported_crops: ["wheat", "maize", "rice", "tomato", "cotton", "sugarcane"], suitability_crops: ["wheat", "maize", "rice"] }
];

function setApiStatus(isLive) {
  const badge = document.getElementById("api-status");
  if (!badge) return;
  if (isLive) {
    badge.textContent = "Backend Connected (127.0.0.1:8000)";
    badge.className = "status-badge status-live";
  } else {
    badge.textContent = "Contract Stub Mode (Local Fallback)";
    badge.className = "status-badge status-mock";
  }
}

async function checkBackendHealth() {
  try {
    const res = await fetch(`${API_BASE_URL}/health`);
    if (res.ok) setApiStatus(true);
  } catch (_) {
    setApiStatus(false);
  }
}

async function fetchRegions() {
  try {
    const res = await fetch(`${API_BASE_URL}/regions`);
    if (!res.ok) throw new Error("Backend /regions not ready");
    const data = await res.json();
    setApiStatus(true);
    return data;
  } catch (err) {
    setApiStatus(false);
    try {
      const localRes = await fetch("../data/reference/regions.json");
      if (localRes.ok) return await localRes.json();
    } catch (_) {}
    return FALLBACK_REGIONS;
  }
}

async function postRecommendation(payload) {
  try {
    const res = await fetch(`${API_BASE_URL}/recommendation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error("Backend /recommendation error");
    const data = await res.json();
    setApiStatus(true);
    return { data, isLive: true };
  } catch (err) {
    setApiStatus(false);
    return { data: buildFallbackRecommendation(payload), isLive: false };
  }
}

async function postAdvisor(payload) {
  try {
    const res = await fetch(`${API_BASE_URL}/advisor`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });
    if (!res.ok) {
      const error = await res.json().catch(() => ({}));
      throw new Error(error.detail || `Backend /advisor error (${res.status})`);
    }
    const data = await res.json();
    setApiStatus(true);
    return data;
  } catch (err) {
    setApiStatus(false);
    throw err;
  }
}

async function fetchTelemetryStatus(deviceId) {
  try {
    const res = await fetch(
      `${API_BASE_URL}/api/telemetry/${encodeURIComponent(deviceId)}/status`
    );
    if (!res.ok) throw new Error("Backend telemetry status error");
    return await res.json();
  } catch (_) {
    return { online: false, last_seen: null, reading: null };
  }
}

async function postDeviceCommand(deviceId, irrigate, durationSec = 5) {
  const query = new URLSearchParams({
    device_id: deviceId,
    irrigate: String(irrigate),
    duration_sec: String(durationSec)
  });
  const res = await fetch(`${API_BASE_URL}/api/device/command?${query}`, {
    method: "POST"
  });
  if (!res.ok) throw new Error("Backend device command error");
  return await res.json();
}

async function fetchTrends(lat, lon, historyDays = 30) {
  const fallback = buildFallbackTrends(lat, lon);
  try {
    const res = await fetch(
      `${API_BASE_URL}/trends?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}&history_days=${encodeURIComponent(historyDays)}`
    );
    if (!res.ok) throw new Error("Backend /trends error");
    const data = await res.json();
    setApiStatus(true);

    const climate =
      data.climate_history && Array.isArray(data.climate_history.dates) && data.climate_history.dates.length > 0
        ? data.climate_history
        : fallback.climate_history;

    const ndvi =
      data.ndvi_history && Array.isArray(data.ndvi_history.dates) && data.ndvi_history.dates.length > 0
        ? data.ndvi_history
        : fallback.ndvi_history;

    const forecast =
      data.forecast_7d && Array.isArray(data.forecast_7d.dates) && data.forecast_7d.dates.length > 0
        ? data.forecast_7d
        : fallback.forecast_7d;

    return {
      climate_history: climate,
      ndvi_history: ndvi,
      forecast_7d: forecast,
      fallback_sources: [
        ...new Set([
          ...(data.fallback_sources || []),
          ...(!data.climate_history?.dates?.length ? ["NASA POWER"] : []),
          ...(!data.ndvi_history?.dates?.length ? ["MODIS NDVI"] : []),
          ...(!data.forecast_7d?.dates?.length ? ["Open-Meteo"] : [])
        ])
      ],
      offline: false
    };
  } catch (err) {
    setApiStatus(false);
    return {
      ...fallback,
      fallback_sources: ["NASA POWER", "MODIS NDVI", "Open-Meteo"],
      offline: true
    };
  }
}

function buildFallbackRecommendation(payload) {
  const refYields = {
    wheat: 6200.0,
    maize: 7800.0,
    cotton: 3400.0,
    tomato: 38000.0,
    sugarcane: 110000.0,
    date_palm: 14000.0
  };
  const base = refYields[(payload.crop || "wheat").toLowerCase()] || 4500.0;
  const estYield = Math.round(base * (0.7 + 0.48 * 0.6));

  const baseRotations = [
    { crop: "cotton", sequence_label: `${formatCropName(payload.crop)} → Cotton → Wheat`, score: 0.84, reason: "Offline illustrative example; not scored from field data." },
    { crop: "faba_bean", sequence_label: `Maize → Faba Bean → ${formatCropName(payload.crop)}`, score: 0.77, reason: "Offline illustrative example; not scored from field data." },
    { crop: "sorghum", sequence_label: `${formatCropName(payload.crop)} → Sorghum → Wheat`, score: 0.69, reason: "Offline illustrative example; not scored from field data." }
  ];

  return {
    irrigation_mm_per_week: 32.0,
    next_irrigation_date: "2026-11-20",
    rotation_recommendations: baseRotations,
    yield_estimate_kg_ha: estYield,
    confidence: "Medium",
    notes: "Offline demo only: values and rotation examples are fixed placeholders, not generated from NASA observations or field conditions."
  };
}

function buildFallbackTrends(lat, lon) {
  const tempOffset = (31 - Number(lat || 30)) * 1.3;
  return {
    climate_history: {
      dates: ["2026-10-15", "2026-10-20", "2026-10-25", "2026-10-30", "2026-11-04", "2026-11-09"],
      temp_c: [25.8, 24.9, 24.1, 23.2, 22.5, 21.8].map((t) => Number((t + tempOffset).toFixed(1))),
      precip_mm: [0.0, 0.4, 0.0, 1.2, 0.0, 2.1]
    },
    ndvi_history: {
      dates: ["2026-09-14", "2026-09-30", "2026-10-16", "2026-11-01"],
      ndvi: [0.41, 0.45, 0.47, 0.48]
    },
    forecast_7d: {
      dates: ["2026-11-14", "2026-11-15", "2026-11-16", "2026-11-17", "2026-11-18", "2026-11-19", "2026-11-20"],
      max_temp_c: [25.0, 24.5, 24.0, 23.2, 22.8, 23.5, 24.1].map((t) => Number((t + tempOffset).toFixed(1))),
      precip_mm: [0.0, 0.0, 1.2, 0.3, 0.0, 0.0, 0.0]
    }
  };
}

function formatCropName(cropKey) {
  const names = {
    wheat: "Wheat",
    maize: "Maize",
    cotton: "Cotton",
    tomato: "Tomato",
    sugarcane: "Sugarcane",
    date_palm: "Date Palm",
    faba_bean: "Faba Bean",
    berseem_clover: "Berseem Clover",
    sorghum: "Sorghum",
    rice: "Rice"
  };
  return names[cropKey] || cropKey;
}
