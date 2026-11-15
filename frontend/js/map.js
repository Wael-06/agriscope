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
  mapInstance = L.map("map").setView([25, 0], 2);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 18,
    attribution: "&copy; OpenStreetMap contributors"
  }).addTo(mapInstance);

  activeMarker = L.marker([31.11, 30.94]).addTo(mapInstance);

  mapInstance.on("click", (e) => {
    const lat = Number(e.latlng.lat.toFixed(4));
    const lon = Number(e.latlng.lng.toFixed(4));
    setMapMarker(lat, lon);
    clearActivePresetButtons();
    if (onLocationSelected) {
      onLocationSelected({ lat, lon });
    }
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

function setMapMarker(lat, lon, popupText = null) {
  if (!mapInstance) return;
  if (activeMarker) {
    activeMarker.setLatLng([lat, lon]);
  } else {
    activeMarker = L.marker([lat, lon]).addTo(mapInstance);
  }
  if (popupText) {
    activeMarker.bindPopup(popupText).openPopup();
  }
  mapInstance.panTo([lat, lon]);
}

function clearActivePresetButtons() {
  document.querySelectorAll(".preset-btn").forEach((btn) => btn.classList.remove("active"));
}

function renderRegionPresets(regions, onRegionPicked) {
  loadedRegions = regions;
  const container = document.getElementById("region-presets");
  container.innerHTML = "";

  const groupedRegions = regions.reduce((groups, region) => {
    const country = region.country || "EGYPT";
    (groups[country] ||= []).push(region);
    return groups;
  }, {});
  let first = true;
  Object.entries(groupedRegions).forEach(([country, countryRegions]) => {
    const group = document.createElement("div");
    group.className = "region-group";
    const heading = document.createElement("h3");
    heading.textContent = { EGYPT: "Egypt", USA: "United States", CHINA: "China" }[country] || country;
    group.appendChild(heading);
    const buttons = document.createElement("div");
    buttons.className = "region-group-buttons";

    countryRegions.forEach((reg) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.dataset.regionId = reg.id;
      btn.className = "preset-btn" + (first ? " active" : "");
      btn.textContent = reg.name;
      first = false;

      btn.addEventListener("click", () => {
        clearActivePresetButtons();
        btn.classList.add("active");
        const label = reg.country ? `${heading.textContent} · ${reg.name}` : reg.name;
        const soil = reg.soil ? `<br/>Soil: ${reg.soil}` : "";
        setMapMarker(reg.lat, reg.lon, `<strong>${label}</strong>${soil}`);
        onRegionPicked(reg);
      });

      buttons.appendChild(btn);
      const circle = L.circleMarker([reg.lat, reg.lon], {
        radius: 7,
        color: country === "USA" ? "#1d4ed8" : country === "CHINA" ? "#dc2626" : "#1b5e20",
        fillColor: "#94a3b8",
        fillOpacity: 0.8
      }).addTo(mapInstance);

      circle.bindTooltip(createRegionTooltip(reg.name, "Select this region to load its vulnerability history."));
      regionalTrendMarkers.set(reg.id, circle);
      circle.on("click", () => btn.click());
    });
    group.appendChild(buttons);
    container.appendChild(group);
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
      ? { color: "#dc2626", text: `Low root-zone wetness index: ${value.toFixed(2)} (<0.30)` }
      : { color: "#22c55e", text: `Root-zone wetness index: ${value.toFixed(2)} (≥0.30)` };
  }
  if (metric === "heat") {
    return value >= 35
      ? { color: "#dc2626", text: `Hot day: ${value.toFixed(1)}°C daily maximum (≥35°C)` }
      : { color: "#22c55e", text: `${value.toFixed(1)}°C daily maximum (<35°C)` };
  }
  return value <= 0
    ? { color: "#dc2626", text: `Frost exposure: ${value.toFixed(1)}°C daily minimum (≤0°C)` }
    : { color: "#22c55e", text: `${value.toFixed(1)}°C daily minimum (>0°C)` };
}

function updateHistoricalMap() {
  const selectedDates = getHistoryDates(selectedHistoryTrends);
  const selectedHistoryAvailable = hasHistoryMetric(selectedHistoryTrends, selectedHistoryMetric);
  const dates = selectedDates.length && selectedHistoryAvailable
    ? selectedDates
    : getHistoryDates(Array.from(regionalTrendData.values()).find(
      (trends) => !trends.offline && !(trends.fallback_sources || []).includes("NASA POWER")
    ));
  const statusEl = document.getElementById("historical-map-status");
  if (!dates.length) {
    const metricName = {
      water_stress: "root-zone wetness",
      heat: "daily maximum temperature",
      frost: "daily minimum temperature"
    }[selectedHistoryMetric];
    statusEl.textContent = `Daily ${metricName} history is unavailable. The map will show gray markers until the required NASA POWER series is available.`;
    for (const [regionId, marker] of regionalTrendMarkers) {
      marker.setStyle({ fillColor: "#94a3b8" });
      marker.setTooltipContent(createRegionTooltip(
        loadedRegions.find((region) => region.id === regionId)?.name || "Region",
        "No daily NASA POWER history available."
      ));
    }
    updateSelectedHistorySummary(null, null);
    return;
  }
  const regionalHistoryAvailable = loadedRegions.some((region) =>
    hasHistoryMetric(regionalTrendData.get(region.id), selectedHistoryMetric)
  );
  const statusDate = dates[Math.max(0, Math.min(selectedHistoryIndex, dates.length - 1))];
  const regionalDateCount = loadedRegions.filter((region) =>
    getHistoryValue(regionalTrendData.get(region.id), selectedHistoryMetric, statusDate) !== null
  ).length;
  const metricName = {
    water_stress: "root-zone wetness",
    heat: "daily maximum temperature",
    frost: "daily minimum temperature"
  }[selectedHistoryMetric];
  statusEl.textContent = selectedHistoryAvailable
    ? `Selected-point history loaded. ${regionalDateCount} regional comparison point(s) have data for this date; select another region to load its history.`
    : regionalHistoryAvailable
      ? `The selected point has no ${metricName} series; comparison markers show only locations with that daily data.`
      : `No ${metricName} series was returned by /trends. Restart the backend if it has not been refreshed; unavailable markers stay gray.`;

  const slider = document.getElementById("historical-map-date");
  slider.max = String(dates.length - 1);
  selectedHistoryIndex = Math.max(0, Math.min(selectedHistoryIndex, dates.length - 1));
  slider.value = String(selectedHistoryIndex);
  const selectedDate = dates[selectedHistoryIndex];
  document.getElementById("historical-map-date-label").textContent = selectedDate;
  const metricLabel = {
    water_stress: "Root-zone wetness",
    heat: "Heat exposure",
    frost: "Frost exposure"
  }[selectedHistoryMetric];
  document.getElementById("historical-map-layer-label").textContent = metricLabel;

  for (const region of loadedRegions) {
    const marker = regionalTrendMarkers.get(region.id);
    if (!marker) continue;
    const trends = regionalTrendData.get(region.id);
    const value = getHistoryValue(trends, selectedHistoryMetric, selectedDate);
    const status = getHistoryStatus(selectedHistoryMetric, value);
    marker.setStyle({ fillColor: status.color });
    marker.setTooltipContent(createRegionTooltip(
      `${region.name} · ${selectedDate}`,
      status.text
    ));
  }

  const selectedValue = getHistoryValue(selectedHistoryTrends, selectedHistoryMetric, selectedDate);
  const selectedStatus = getHistoryStatus(selectedHistoryMetric, selectedValue);
  if (selectedHistoryMarker) {
    selectedHistoryMarker.setStyle({ color: "#0f172a", fillColor: selectedStatus.color });
    selectedHistoryMarker.setTooltipContent(createRegionTooltip(
      `Selected point · ${selectedDate}`,
      selectedStatus.text
    ));
  }
  updateSelectedHistorySummary(selectedHistoryTrends, selectedHistoryMetric);
  if (typeof updateVulnerabilityTrendSelection === "function") {
    updateVulnerabilityTrendSelection(selectedHistoryMetric, selectedHistoryIndex);
  }
}

function updateSelectedHistorySummary(trends, metric) {
  const locationLabel = document.getElementById("selected-screening-location");
  const metricLabel = document.getElementById("selected-screening-metric");
  const readingLabel = document.getElementById("selected-screening-reading");
  const wetnessTrend = document.getElementById("selected-screening-wetness-trend");
  const heatDays = document.getElementById("selected-screening-heat-days");
  const frostDays = document.getElementById("selected-screening-frost-days");
  if (!locationLabel) return;

  const lat = Number(document.getElementById("lat").value);
  const lon = Number(document.getElementById("lon").value);
  const region = loadedRegions.find((item) => Math.abs(item.lat - lat) < 0.001 && Math.abs(item.lon - lon) < 0.001);
  locationLabel.textContent = region?.name || `${lat.toFixed(4)}, ${lon.toFixed(4)}`;
  metricLabel.textContent = {
    water_stress: "Root-zone wetness index",
    heat: "Daily maximum temperature",
    frost: "Daily minimum temperature"
  }[metric] || "—";

  const dates = getHistoryDates(trends);
  const date = dates[selectedHistoryIndex];
  const value = getHistoryValue(trends, metric, date);
  readingLabel.textContent = value === null
    ? "Unavailable for this date"
    : metric === "water_stress" ? `${value.toFixed(2)} index` : `${value.toFixed(1)}°C`;

  const sourceAvailable = trends && !trends.offline && !(trends.fallback_sources || []).includes("NASA POWER");
  const climate = sourceAvailable ? trends.climate_history : {};
  const wetness = climate.soil_moisture;
  const validWetness = Array.isArray(wetness) ? wetness.filter(Number.isFinite) : [];
  wetnessTrend.textContent = validWetness.length > 1
    ? `${(validWetness[validWetness.length - 1] - validWetness[0]).toFixed(2)} index over ${dates.length} days`
    : "Unavailable";
  const maxTemps = Array.isArray(climate.temp_max_c) ? climate.temp_max_c : [];
  heatDays.textContent = maxTemps.some(Number.isFinite)
    ? `${maxTemps.filter((temp) => Number.isFinite(temp) && temp >= 35).length} days ≥35°C`
    : "Unavailable";
  const minTemps = Array.isArray(climate.temp_min_c) ? climate.temp_min_c : [];
  frostDays.textContent = minTemps.some(Number.isFinite)
    ? `${minTemps.filter((temp) => Number.isFinite(temp) && temp <= 0).length} days ≤0°C`
    : "Unavailable";
}

function setHistoricalMapData(lat, lon, trends) {
  selectedHistoryTrends = trends;
  const selectedRegion = loadedRegions.find(
    (region) => Math.abs(region.lat - lat) < 0.001 && Math.abs(region.lon - lon) < 0.001
  );
  if (selectedRegion) regionalTrendData.set(selectedRegion.id, trends);
  const dates = getHistoryDates(trends);
  selectedHistoryIndex = Math.max(0, dates.length - 1);
  const selectedDate = dates[selectedHistoryIndex];
  const value = getHistoryValue(trends, selectedHistoryMetric, selectedDate);
  const status = getHistoryStatus(selectedHistoryMetric, value);
  if (selectedHistoryMarker) selectedHistoryMarker.remove();
  selectedHistoryMarker = L.circleMarker([lat, lon], {
    radius: 11,
    color: "#0f172a",
    weight: 3,
    fillColor: status.color,
    fillOpacity: 0.95
  }).addTo(mapInstance);
  updateHistoricalMap();
}
