let climateChartInstance = null;
let ndviChartInstance = null;
let forecastChartInstance = null;
let lastRawRotations = [];

document.addEventListener("DOMContentLoaded", async () => {
  await checkBackendHealth();

  initMap((coords) => {
    document.getElementById("lat").value = coords.lat;
    document.getElementById("lon").value = coords.lon;
    runFullAnalysis();
  });

  const regions = await fetchRegions();

  const applyRegionSelection = (region) => {
    document.getElementById("lat").value = region.lat;
    document.getElementById("lon").value = region.lon;
    if (region.default_crop) {
      document.getElementById("crop").value = region.default_crop;
    }
    const soilMap = {
      "Alluvial Clay": "clay",
      "Silty Clay": "clay",
      "Sandy Loam": "loam",
      "Sandy": "sandy"
    };
    if (region.soil && soilMap[region.soil]) {
      document.getElementById("soil_texture").value = soilMap[region.soil];
    }
    setMapMarker(region.lat, region.lon, `<strong>${region.name}</strong><br/>Soil: ${region.soil}`);
    document.querySelectorAll(".preset-btn").forEach((b) => {
      b.classList.toggle("active", b.dataset.regionId === region.id);
    });
    runFullAnalysis();
  };

  renderRegionPresets(regions, applyRegionSelection);
  initLandingGlobe(regions, applyRegionSelection);

  document.getElementById("farmer-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const lat = parseFloat(document.getElementById("lat").value);
    const lon = parseFloat(document.getElementById("lon").value);
    setMapMarker(lat, lon);
    runFullAnalysis();
  });

  setupPrioritySliders();
  runFullAnalysis();
});

function getNormalizedPriorityWeights() {
  const rawSoil = parseFloat(document.getElementById("weight-soil").value) || 0;
  const rawWater = parseFloat(document.getElementById("weight-water").value) || 0;
  const rawClimate = parseFloat(document.getElementById("weight-climate").value) || 0;

  const diversityFixed = 0.10;
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

  document.getElementById("val-soil").textContent = soil.toFixed(2);
  document.getElementById("val-water").textContent = water.toFixed(2);
  document.getElementById("val-climate").textContent = climate.toFixed(2);

  return {
    soil_health: soil,
    water_demand: water,
    climate_suitability: climate,
    rotation_diversity: diversityFixed
  };
}

function setupPrioritySliders() {
  const sliderIds = ["weight-soil", "weight-water", "weight-climate"];
  sliderIds.forEach((id) => {
    document.getElementById(id).addEventListener("input", () => {
      const weights = getNormalizedPriorityWeights();
      const selectedCrop = document.getElementById("crop").value;
      const reRanked = applyClientPriorityWeights(lastRawRotations, weights, selectedCrop);
      renderRotationList(reRanked, selectedCrop);
    });
  });
}

function collectFormPayload() {
  return {
    lat: parseFloat(document.getElementById("lat").value),
    lon: parseFloat(document.getElementById("lon").value),
    crop: document.getElementById("crop").value,
    field_size_ha: parseFloat(document.getElementById("field_size_ha").value),
    planting_date: document.getElementById("planting_date").value,
    soil_texture: document.getElementById("soil_texture").value,
    irrigation_availability: document.getElementById("irrigation_availability").value,
    planning_horizon_seasons: parseInt(document.getElementById("planning_horizon_seasons").value, 10),
    rotation_priority_weights: getNormalizedPriorityWeights()
  };
}

async function runFullAnalysis() {
  const loadingEl = document.getElementById("loading-state");
  const errorEl = document.getElementById("error-state");
  errorEl.classList.add("hidden");
  loadingEl.classList.remove("hidden");

  try {
    const payload = collectFormPayload();
    const [recResult, trendsData] = await Promise.all([
      postRecommendation(payload),
      fetchTrends(payload.lat, payload.lon)
    ]);

    lastRawRotations = recResult.data.rotation_recommendations || [];
    renderRecommendationDashboard(recResult.data, payload, recResult.isLive);
    renderEarthIntelligenceCharts(trendsData);
  } catch (err) {
    errorEl.textContent = `Unable to render analysis: ${err.message}`;
    errorEl.classList.remove("hidden");
  } finally {
    loadingEl.classList.add("hidden");
  }
}

function renderRecommendationDashboard(data, payload, isLive) {
  document.getElementById("res-irrig-mm").textContent = `${Number(data.irrigation_mm_per_week).toFixed(1)} mm/wk`;
  document.getElementById("res-irrig-date").textContent = data.next_irrigation_date;

  const badgeEl = document.getElementById("irrig-mode-badge");
  badgeEl.textContent = isLive
    ? "Illustrative example / Prototype advisory (verify field moisture)"
    : "Illustrative example only; not a live recommendation";

  const cropMeta = KC_TABLE[payload.crop] || { kc: 1.15, stage: "Mid-season" };
  const et0 = 4.2;
  const etc = Number((et0 * cropMeta.kc).toFixed(2));

  document.getElementById("spec-crop").textContent = formatCropName(payload.crop);
  document.getElementById("spec-stage").textContent = cropMeta.stage;
  document.getElementById("spec-et0").textContent = `${et0} mm/day`;
  document.getElementById("spec-kc").textContent = cropMeta.kc.toFixed(2);
  document.getElementById("spec-etc").textContent = `${etc} mm/day`;

  const weightedRotations = applyClientPriorityWeights(
    data.rotation_recommendations,
    payload.rotation_priority_weights,
    payload.crop
  );
  renderRotationList(weightedRotations, payload.crop);

  document.getElementById("res-yield").textContent = Number(data.yield_estimate_kg_ha).toLocaleString();

  const confEl = document.getElementById("res-confidence");
  const confLevel = (data.confidence || "Medium").toLowerCase();
  confEl.textContent = `Confidence: ${data.confidence || "Medium"}`;
  confEl.className = `confidence-badge confidence-${confLevel}`;

  document.getElementById("res-notes").textContent =
    data.notes || "Baseline estimate from documented environmental variables and FAOSTAT history; not a trained model.";
}

function renderRotationList(recommendations, selectedCrop) {
  const listEl = document.getElementById("rotation-list");
  listEl.innerHTML = "";

  const defaultSequences = [
    `${formatCropName(selectedCrop)} → Cotton → Wheat`,
    `Maize → Faba Bean → ${formatCropName(selectedCrop)}`,
    `${formatCropName(selectedCrop)} → Sorghum → Wheat`
  ];

  (recommendations || []).slice(0, 3).forEach((item, index) => {
    const li = document.createElement("li");
    const seqTitle = item.sequence_label || `${defaultSequences[index]} (${formatCropName(item.crop)})`;
    li.innerHTML = `
      <span class="rotation-item-title">${seqTitle}</span>
      <span class="rotation-score">Score: ${Number(item.score).toFixed(2)}</span>
      <span class="rotation-reason">${item.reason}</span>
    `;
    listEl.appendChild(li);
  });
}

function renderEarthIntelligenceCharts(trends) {
  const climateCtx = document.getElementById("climateChart").getContext("2d");
  const ndviCtx = document.getElementById("ndviChart").getContext("2d");
  const forecastCtx = document.getElementById("forecastChart").getContext("2d");

  if (climateChartInstance) climateChartInstance.destroy();
  if (ndviChartInstance) ndviChartInstance.destroy();
  if (forecastChartInstance) forecastChartInstance.destroy();

  climateChartInstance = new Chart(climateCtx, {
    type: "bar",
    data: {
      labels: trends.climate_history.dates,
      datasets: [
        {
          type: "line",
          label: "Temp (°C)",
          data: trends.climate_history.temp_c,
          borderColor: "#dc2626",
          backgroundColor: "#dc2626",
          yAxisID: "yTemp",
          tension: 0.3
        },
        {
          type: "bar",
          label: "Precip (mm)",
          data: trends.climate_history.precip_mm,
          backgroundColor: "#0284c7",
          yAxisID: "yPrecip"
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        yTemp: { type: "linear", position: "left", title: { display: true, text: "°C" } },
        yPrecip: { type: "linear", position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "mm" } }
      }
    }
  });

  ndviChartInstance = new Chart(ndviCtx, {
    type: "line",
    data: {
      labels: trends.ndvi_history.dates,
      datasets: [
        {
          label: "MODIS NDVI",
          data: trends.ndvi_history.ndvi,
          borderColor: "#16a34a",
          backgroundColor: "rgba(22, 163, 74, 0.15)",
          fill: true,
          tension: 0.3
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        y: { min: 0, max: 1.0, title: { display: true, text: "NDVI" } }
      }
    }
  });

  forecastChartInstance = new Chart(forecastCtx, {
    type: "bar",
    data: {
      labels: trends.forecast_7d.dates,
      datasets: [
        {
          type: "line",
          label: "Max Temp (°C)",
          data: trends.forecast_7d.max_temp_c,
          borderColor: "#ea580c",
          backgroundColor: "#ea580c",
          yAxisID: "yTemp",
          tension: 0.3
        },
        {
          type: "bar",
          label: "Forecast Precip (mm)",
          data: trends.forecast_7d.precip_mm,
          backgroundColor: "#38bdf8",
          yAxisID: "yPrecip"
        }
      ]
    },
    options: {
      responsive: true,
      scales: {
        yTemp: { type: "linear", position: "left", title: { display: true, text: "°C" } },
        yPrecip: { type: "linear", position: "right", grid: { drawOnChartArea: false }, title: { display: true, text: "mm" } }
      }
    }
  });
}
