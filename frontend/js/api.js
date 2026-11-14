const API_BASE_URL = "";

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
  { id: "new_valley", name: "New Valley (Kharga)", lat: 25.44, lon: 30.55, default_crop: "date_palm", soil: "Sandy" }
];

function setApiStatus(isLive) {
  const badge = document.getElementById("api-status");
  if (!badge) return;
  if (isLive) {
    badge.textContent = "Backend Live (127.0.0.1:8000)";
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

async function fetchTrends(lat, lon) {
  const fallback = buildFallbackTrends(lat, lon);
  try {
    const res = await fetch(`${API_BASE_URL}/trends?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`);
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
      forecast_7d: forecast
    };
  } catch (err) {
    setApiStatus(false);
    return fallback;
  }
}

function applyClientPriorityWeights(rotations, weights, selectedCrop) {
  const profileScores = {
    cotton: { soil: 0.86, water: 0.78, climate: 0.88, div: 0.92 },
    faba_bean: { soil: 0.92, water: 0.82, climate: 0.76, div: 0.85 },
    sorghum: { soil: 0.65, water: 0.86, climate: 0.94, div: 0.72 },
    maize: { soil: 0.72, water: 0.68, climate: 0.82, div: 0.78 },
    wheat: { soil: 0.70, water: 0.84, climate: 0.88, div: 0.70 }
  };

  const seqTemplates = [
    `${formatCropName(selectedCrop)} → Cotton → Wheat`,
    `Maize → Faba Bean → ${formatCropName(selectedCrop)}`,
    `${formatCropName(selectedCrop)} → Sorghum → Wheat`
  ];

  return (rotations || [])
    .map((item, idx) => {
      const normalizedCrop = item.crop === "berseem_clover" ? "cotton" : item.crop;
      const p = profileScores[normalizedCrop] || { soil: item.score || 0.75, water: 0.75, climate: 0.75, div: 0.75 };
      const weightedScore =
        weights.soil_health * p.soil +
        weights.water_demand * p.water +
        weights.climate_suitability * p.climate +
        (weights.rotation_diversity || 0.1) * p.div;

      return {
        crop: normalizedCrop,
        sequence_label: item.sequence_label || `${seqTemplates[idx % 3]} (${formatCropName(normalizedCrop)})`,
        score: Number(weightedScore.toFixed(2)),
        reason: normalizedCrop === "cotton" && item.crop === "berseem_clover"
          ? "Deep-rooted fiber crop; breaks cereal pest cycles and improves soil tilth."
          : item.reason
      };
    })
    .sort((a, b) => b.score - a.score);
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
    { crop: "cotton", score: 0.84, reason: "Deep-rooted fiber crop; breaks cereal pest cycles and improves soil tilth." },
    { crop: "faba_bean", score: 0.77, reason: "Moderate water demand suited to current root moisture." },
    { crop: "sorghum", score: 0.69, reason: "High heat tolerance if peak temperatures rise." }
  ];

  return {
    irrigation_mm_per_week: 32.0,
    next_irrigation_date: "2026-11-20",
    rotation_recommendations: applyClientPriorityWeights(
      baseRotations,
      payload.rotation_priority_weights,
      payload.crop
    ),
    yield_estimate_kg_ha: estYield,
    confidence: "Medium",
    notes: "Prototype estimate combining NASA POWER soil moisture, MODIS NDVI, and regional baseline; subject to local cultivar variance."
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
    sorghum: "Sorghum",
    rice: "Rice"
  };
  return names[cropKey] || cropKey;
}
