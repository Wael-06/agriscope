let mapInstance = null;
let activeMarker = null;
let loadedRegions = [];
const regionalTrendData = new Map();
const regionalTrendMarkers = new Map();
let selectedHistoryMarker = null;
let selectedHistoryTrends = null;
let selectedHistoryIndex = 0;
let selectedHistoryMetric = "water_stress";

function initMap(onLocationSelected) {
  const s = getFieldState();
  mapInstance = L.map("map", { zoomControl: false }).setView([s.lat || 28, s.lon || 30], 7);
  L.control.zoom({ position: "bottomright" }).addTo(mapInstance);

  wireBasemapSwitcher("vuln-basemap-switcher", mapInstance, getPreferredBasemap());

  activeMarker = L.marker([s.lat, s.lon], { icon: createPulsingPinIcon(), zIndexOffset: 500 }).addTo(mapInstance);
  updateMapHudCoords(s.regionName, s.lat, s.lon);

  mapInstance.on("click", (e) => {
    const lat = Number(e.latlng.lat.toFixed(4));
    const lon = Number(e.latlng.lng.toFixed(4));
    setMapMarker(lat, lon, null, false);
    updateMapHudCoords("Custom Field Pin", lat, lon);
    if (onLocationSelected) onLocationSelected({ lat, lon });
  });

  document.getElementById("center-pin-btn").addEventListener("click", () => {
    const cur = getFieldState();
    mapInstance.flyTo([cur.lat, cur.lon], 9, { duration: 0.9 });
  });

  document.getElementById("fit-regions-btn").addEventListener("click", () => {
    if (!loadedRegions.length) return;
    const bounds = L.latLngBounds(loadedRegions.map((r) => [r.lat, r.lon]));
    mapInstance.flyToBounds(bounds.pad(0.25), { duration: 1.0 });
  });

  const fullscreenBtn = document.getElementById("fullscreen-map-btn");
  const shell = document.getElementById("vuln-map-shell");
  fullscreenBtn.addEventListener("click", () => {
    const isFull = shell.classList.toggle("is-fullscreen");
    fullscreenBtn.textContent = isFull ? "Exit Fullscreen" : "Fullscreen";
    setTimeout(() => mapInstance.invalidateSize(), 180);
  });

  document.getElementById("historical-map-date").addEventListener("input", (event) => {
    selectedHistoryIndex = Number(event.target.value);
    updateHistoricalMap();
  });
  document.getElementById("historical-map-metric").addEventListener("change", (event) => {
    selectedHistoryMetric = event.target.value;
    updateHistoricalMap();
  });
}

function updateMapHudCoords(label, lat, lon) {
  const nameEl = document.getElementById("map-hud-location");
  const coordEl = document.getElementById("map-hud-coords");
  if (nameEl) nameEl.textContent = label || "Selected Pin";
  if (coordEl) coordEl.textContent = `${Number(lat).toFixed(3)}°, ${Number(lon).toFixed(3)}°`;
}

function setMapMarker(lat, lon, popupText = null, fly = true) {
  if (!mapInstance) return;
  if (activeMarker) activeMarker.setLatLng([lat, lon]);
  else activeMarker = L.marker([lat, lon], { icon: createPulsingPinIcon(), zIndexOffset: 500 }).addTo(mapInstance);
  if (popupText) activeMarker.bindPopup(popupText).openPopup();
  if (fly) {
    mapInstance.flyTo([lat, lon], Math.max(mapInstance.getZoom(), 8), { duration: 0.9 });
  } else {
    mapInstance.panTo([lat, lon]);
  }
}

function renderMapRegions(regions, onRegionPicked) {
  loadedRegions = regions;
  const container = document.getElementById("map-region-chips");
  if (container) container.innerHTML = "";
  const activeId = getFieldState().regionId;

  regions.forEach((reg) => {
    const country = reg.country || "EGYPT";
    const stroke = country === "USA" ? "#38bdf8" : country === "CHINA" ? "#f59e0b" : "#34d399";
    const circle = L.circleMarker([reg.lat, reg.lon], {
      radius: 8,
      weight: 2.5,
      color: stroke,
      fillColor: "#94a3b8",
      fillOpacity: 0.9
    }).addTo(mapInstance);

    circle.bindTooltip(createRegionTooltip(reg.name, "Click to load climate vulnerability history."));
    regionalTrendMarkers.set(reg.id, circle);

    const pick = () => {
      document.querySelectorAll("#map-region-chips .preset-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.regionId === reg.id);
      });
      updateMapHudCoords(reg.name, reg.lat, reg.lon);
      setMapMarker(reg.lat, reg.lon, `<strong>${reg.name}</strong>${reg.soil ? `<br/>Soil: ${reg.soil}` : ""}`, true);
      onRegionPicked(reg);
    };

    circle.on("click", pick);

    if (container) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "preset-btn" + (reg.id === activeId ? " active" : "");
      btn.dataset.regionId = reg.id;
      btn.textContent = reg.name;
      btn.addEventListener("click", pick);
      container.appendChild(btn);
    }
  });
}

function createRegionTooltip(regionName, summary) {
  const content = document.createElement("div");
  const name = document.createElement("strong");
  name.textContent = regionName;
  const details = document.createElement("div");
  details.textContent = summary;
  content.append(name, details);
  return content;
}

function getHistoryDates(trends) {
  const climate = trends?.climate_history;
  return Array.isArray(climate?.dates) ? climate.dates : [];
}

function getHistoryValue(trends, metric, date) {
  const climate = trends?.climate_history;
  if (!climate || trends.offline || (trends.fallback_sources || []).includes("NASA POWER")) return null;
  const seriesByMetric = {
    water_stress: climate.soil_moisture,
    heat: climate.temp_max_c,
    frost: climate.temp_min_c
  };
  const values = seriesByMetric[metric];
  const dates = getHistoryDates(trends);
  const index = dates.indexOf(date);
  return Array.isArray(values) && index >= 0 && Number.isFinite(values[index]) ? values[index] : null;
}

function hasHistoryMetric(trends, metric) {
  const climate = trends?.climate_history;
  if (!climate || trends.offline || (trends.fallback_sources || []).includes("NASA POWER")) return false;
  const seriesByMetric = {
    water_stress: climate.soil_moisture,
    heat: climate.temp_max_c,
    frost: climate.temp_min_c
  };
  return Array.isArray(seriesByMetric[metric]) && seriesByMetric[metric].some(Number.isFinite);
}

function getHistoryStatus(metric, value) {
  if (value === null) return { color: "#94a3b8", text: "No source data for this date" };
  if (metric === "water_stress") {
    return value < 0.30
      ? { color: "#ef4444", text: `Low root-zone wetness: ${value.toFixed(2)} (<0.30)` }
      : { color: "#22c55e", text: `Root-zone wetness: ${value.toFixed(2)} (≥0.30)` };
  }
  if (metric === "heat") {
    return value >= 35
      ? { color: "#ef4444", text: `Hot day: ${value.toFixed(1)}°C max (≥35°C)` }
      : { color: "#22c55e", text: `${value.toFixed(1)}°C max (<35°C)` };
  }
  return value <= 0
    ? { color: "#ef4444", text: `Frost exposure: ${value.toFixed(1)}°C min (≤0°C)` }
    : { color: "#22c55e", text: `${value.toFixed(1)}°C min (>0°C)` };
}

function updateHistoricalMap() {
  const selectedDates = getHistoryDates(selectedHistoryTrends);
  const selectedHistoryAvailable = hasHistoryMetric(selectedHistoryTrends, selectedHistoryMetric);
  const dates = selectedDates.length && selectedHistoryAvailable
    ? selectedDates
    : getHistoryDates(Array.from(regionalTrendData.values()).find(
      (t) => !t.offline && !(t.fallback_sources || []).includes("NASA POWER")
    ));

  const statusEl = document.getElementById("historical-map-status");
  if (!dates.length) {
    statusEl.textContent = "Daily NASA POWER history unavailable — markers stay gray until live observations return.";
    for (const [, marker] of regionalTrendMarkers) marker.setStyle({ fillColor: "#94a3b8" });
    updateSelectedHistorySummary(null, selectedHistoryMetric);
    return;
  }

  const slider = document.getElementById("historical-map-date");
  slider.max = String(dates.length - 1);
  selectedHistoryIndex = Math.max(0, Math.min(selectedHistoryIndex, dates.length - 1));
  slider.value = String(selectedHistoryIndex);
  const selectedDate = dates[selectedHistoryIndex];

  document.getElementById("historical-map-date-label").textContent = selectedDate;

  const regionalDateCount = loadedRegions.filter((r) =>
    getHistoryValue(regionalTrendData.get(r.id), selectedHistoryMetric, selectedDate) !== null
  ).length;
  statusEl.textContent = selectedHistoryAvailable
    ? `Observation date ${selectedDate} · ${regionalDateCount} regional point(s) loaded.`
    : "Selected point lacks this series; comparison markers reflect available regions.";

  for (const region of loadedRegions) {
    const marker = regionalTrendMarkers.get(region.id);
    if (!marker) continue;
    const value = getHistoryValue(regionalTrendData.get(region.id), selectedHistoryMetric, selectedDate);
    const status = getHistoryStatus(selectedHistoryMetric, value);
    marker.setStyle({ fillColor: status.color });
    marker.setTooltipContent(createRegionTooltip(`${region.name} · ${selectedDate}`, status.text));
  }

  const selectedValue = getHistoryValue(selectedHistoryTrends, selectedHistoryMetric, selectedDate);
  const selectedStatus = getHistoryStatus(selectedHistoryMetric, selectedValue);
  if (selectedHistoryMarker) {
    selectedHistoryMarker.setStyle({ color: "#ffffff", fillColor: selectedStatus.color });
    selectedHistoryMarker.setTooltipContent(createRegionTooltip(`Selected point · ${selectedDate}`, selectedStatus.text));
  }

  updateSelectedHistorySummary(selectedHistoryTrends, selectedHistoryMetric);
  if (typeof updateVulnerabilityTrendSelection === "function") {
    updateVulnerabilityTrendSelection(selectedHistoryMetric, selectedHistoryIndex);
  }
}

function updateSelectedHistorySummary(trends, metric) {
  const state = getFieldState();
  document.getElementById("selected-screening-location").textContent =
    state.regionName || `${Number(state.lat).toFixed(4)}, ${Number(state.lon).toFixed(4)}`;
  document.getElementById("selected-screening-metric").textContent = {
    water_stress: "Root-zone wetness index",
    heat: "Daily maximum temperature",
    frost: "Daily minimum temperature"
  }[metric] || "—";

  const dates = getHistoryDates(trends);
  const date = dates[selectedHistoryIndex];
  const value = getHistoryValue(trends, metric, date);
  document.getElementById("selected-screening-reading").textContent = value === null
    ? "Unavailable for this date"
    : metric === "water_stress" ? `${value.toFixed(2)} index` : `${value.toFixed(1)}°C`;

  const ok = trends && !trends.offline && !(trends.fallback_sources || []).includes("NASA POWER");
  const climate = ok ? trends.climate_history : {};
  const validWet = Array.isArray(climate.soil_moisture) ? climate.soil_moisture.filter(Number.isFinite) : [];
  document.getElementById("selected-screening-wetness-trend").textContent = validWet.length > 1
    ? `${(validWet[validWet.length - 1] - validWet[0]).toFixed(2)} over ${dates.length}d`
    : "Unavailable";

  const maxT = Array.isArray(climate.temp_max_c) ? climate.temp_max_c : [];
  document.getElementById("selected-screening-heat-days").textContent = maxT.some(Number.isFinite)
    ? `${maxT.filter((v) => Number.isFinite(v) && v >= 35).length} days ≥35°C`
    : "Unavailable";

  const minT = Array.isArray(climate.temp_min_c) ? climate.temp_min_c : [];
  document.getElementById("selected-screening-frost-days").textContent = minT.some(Number.isFinite)
    ? `${minT.filter((v) => Number.isFinite(v) && v <= 0).length} days ≤0°C`
    : "Unavailable";
}

function setHistoricalMapData(lat, lon, trends) {
  selectedHistoryTrends = trends;
  const matched = loadedRegions.find(
    (r) => Math.abs(r.lat - lat) < 0.001 && Math.abs(r.lon - lon) < 0.001
  );
  if (matched) regionalTrendData.set(matched.id, trends);

  const dates = getHistoryDates(trends);
  selectedHistoryIndex = Math.max(0, dates.length - 1);
  const selectedDate = dates[selectedHistoryIndex];
  const value = getHistoryValue(trends, selectedHistoryMetric, selectedDate);
  const status = getHistoryStatus(selectedHistoryMetric, value);

  if (selectedHistoryMarker) selectedHistoryMarker.remove();
  selectedHistoryMarker = L.circleMarker([lat, lon], {
    radius: 14,
    color: "#ffffff",
    weight: 2.5,
    fillColor: status.color,
    fillOpacity: 0.45
  }).addTo(mapInstance);

  updateHistoricalMap();
}
