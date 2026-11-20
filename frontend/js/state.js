const STORAGE_KEY = "agriscope_field_state_v2";
const THEME_KEY = "agriscope_theme_v2";
const BASEMAP_KEY = "agriscope_basemap_v4";

const DEFAULT_FIELD_STATE = {
  regionId: "nile_delta",
  regionName: "Nile Delta (Kafr El-Sheikh)",
  country: "EGYPT",
  lat: 31.11,
  lon: 30.94,
  crop: "wheat",
  previous_crop: "",
  field_size_ha: 2.5,
  planting_date: "2026-11-15",
  soil_texture: "clay",
  irrigation_availability: "limited",
  planning_horizon_seasons: 3,
  weights: { soil: 35, water: 30, climate: 25 },
  use_live_sensor: false,
  device_id: "demo-esp32-01"
};

function getFieldState() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return structuredClone(DEFAULT_FIELD_STATE);
    const parsed = JSON.parse(raw);
    return {
      ...DEFAULT_FIELD_STATE,
      ...parsed,
      weights: { ...DEFAULT_FIELD_STATE.weights, ...(parsed.weights || {}) }
    };
  } catch (_) {
    return structuredClone(DEFAULT_FIELD_STATE);
  }
}

function saveFieldState(partial) {
  const current = getFieldState();
  const next = {
    ...current,
    ...partial,
    weights: partial.weights ? { ...current.weights, ...partial.weights } : current.weights
  };
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch (_) {}
  if (typeof renderContextBar === "function") renderContextBar();
  return next;
}

function applyRegionToState(region) {
  const soilMap = {
    "Alluvial Clay": "clay",
    "Silty Clay": "clay",
    "Sandy Loam": "loam",
    "Sandy": "sandy"
  };
  const updates = {
    regionId: region.id || null,
    regionName: region.name || `${Number(region.lat).toFixed(2)}, ${Number(region.lon).toFixed(2)}`,
    country: region.country || "EGYPT",
    lat: Number(region.lat),
    lon: Number(region.lon)
  };
  if (region.default_crop) updates.crop = region.default_crop;
  if (region.soil && soilMap[region.soil]) updates.soil_texture = soilMap[region.soil];
  return saveFieldState(updates);
}

function computeNormalizedWeights(weights) {
  const rawSoil = Number(weights?.soil ?? 35);
  const rawWater = Number(weights?.water ?? 30);
  const rawClimate = Number(weights?.climate ?? 25);
  const sumThree = rawSoil + rawWater + rawClimate;

  let soil = 0.35;
  let water = 0.30;
  let climate = 0.25;

  if (sumThree > 0) {
    const scale = 0.90 / sumThree;
    soil = Number((rawSoil * scale).toFixed(2));
    water = Number((rawWater * scale).toFixed(2));
    climate = Number((0.90 - soil - water).toFixed(2));
  }

  return {
    soil_health: soil,
    water_demand: water,
    climate_suitability: climate,
    rotation_diversity: 0.10
  };
}

function buildRecommendationPayload(state = getFieldState()) {
  const payload = {
    lat: Number(state.lat),
    lon: Number(state.lon),
    crop: state.crop,
    previous_crop: state.previous_crop || null,
    field_size_ha: Number(state.field_size_ha),
    planting_date: state.planting_date,
    soil_texture: state.soil_texture,
    irrigation_availability: state.irrigation_availability,
    planning_horizon_seasons: parseInt(state.planning_horizon_seasons, 10) || 3,
    rotation_priority_weights: computeNormalizedWeights(state.weights)
  };
  if (state.use_live_sensor && state.device_id) {
    payload.use_live_sensor = true;
    payload.device_id = state.device_id.trim();
  }
  return payload;
}

function getTheme() {
  const saved = localStorage.getItem(THEME_KEY);
  return (saved === "dark" || saved === "light") ? saved : "light";
}

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem(THEME_KEY, theme);
  window.dispatchEvent(new CustomEvent("agriscope:themechange", { detail: { theme } }));
}

function toggleTheme() {
  const next = getTheme() === "dark" ? "light" : "dark";
  applyTheme(next);
  return next;
}

function getPreferredBasemap() {
  const saved = localStorage.getItem(BASEMAP_KEY);
  return saved === "terrain" ? "terrain" : "satellite";
}

function setPreferredBasemap(style) {
  const safeStyle = style === "terrain" ? "terrain" : "satellite";
  localStorage.setItem(BASEMAP_KEY, safeStyle);
}

applyTheme(getTheme());
