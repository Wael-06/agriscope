let climateChartInstance = null;
let ndviChartInstance = null;
let forecastChartInstance = null;
let vulnerabilityTrendChartInstance = null;
let currentEarthTrends = null;
let priorityUpdateTimer = null;

document.addEventListener("DOMContentLoaded", async () => {
  await checkBackendHealth();

  initMap((coords) => {
    updateCropOptions(null, allCropOptions);
    document.getElementById("lat").value = coords.lat;
    document.getElementById("lon").value = coords.lon;
    runFullAnalysis();
  });

  const regions = await fetchRegions();
  const cropSelect = document.getElementById("crop");
  const allCropOptions = Array.from(cropSelect.options, (option) => option.cloneNode(true));
  const previousCropSelect = document.getElementById("previous_crop");
  allCropOptions.forEach((option) => {
    const previousOption = option.cloneNode(true);
    previousOption.selected = false;
    previousOption.defaultSelected = false;
    previousCropSelect.append(previousOption);
  });
  previousCropSelect.value = "";

  const applyRegionSelection = (region) => {
    document.getElementById("lat").value = region.lat;
    document.getElementById("lon").value = region.lon;
    updateCropOptions(region, allCropOptions);
    const soilMap = {
      "Alluvial Clay": "clay",
      "Silty Clay": "clay",
      "Sandy Loam": "loam",
      "Sandy": "sandy"
    };
    if (region.soil && soilMap[region.soil]) {
      document.getElementById("soil_texture").value = soilMap[region.soil];
    }
    const regionLabel = region.country ? `${region.country} · ${region.name}` : region.name;
    const soilNote = region.soil ? `<br/>Soil: ${region.soil}` : "";
    setMapMarker(region.lat, region.lon, `<strong>${regionLabel}</strong>${soilNote}`);
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

  document.getElementById("advisor-btn").addEventListener("click", requestFieldAdvice);

  document.getElementById("use-live-sensor").addEventListener("change", () => {
    updateSensorVisibility();
    runFullAnalysis();
  });
  document.getElementById("irrigate-now-btn").addEventListener("click", async () => {
    const deviceId = document.getElementById("device-id").value.trim();
    const statusEl = document.getElementById("sensor-command-status");
    try {
      await postDeviceCommand(deviceId, true, 5);
      statusEl.textContent = "Irrigation command queued.";
    } catch (err) {
      statusEl.textContent = `Unable to send irrigation command: ${err.message}`;
    }
  });
  updateSensorVisibility();

  setupPrioritySliders();
  runFullAnalysis();
});

async function requestFieldAdvice() {
  const form = document.getElementById("farmer-form");
  if (!form.reportValidity()) return;

  const button = document.getElementById("advisor-btn");
  const response = document.getElementById("advisor-response");
  const status = document.getElementById("advisor-status");
  const advice = document.getElementById("advisor-advice");
  const facts = document.getElementById("advisor-facts");
  const sources = document.getElementById("advisor-sources");
  const sourcesTitle = document.getElementById("advisor-sources-title");

  button.disabled = true;
  button.textContent = "Preparing advice...";
  response.classList.remove("hidden");
  response.setAttribute("aria-busy", "true");
  status.textContent = "Collecting your field data and preparing advice...";
  advice.replaceChildren();
  advice.classList.add("hidden");
  facts.replaceChildren();
  facts.classList.add("hidden");
  sources.replaceChildren();
  sources.classList.add("hidden");
  sourcesTitle.classList.add("hidden");

  try {
    const payload = {
      ...collectFormPayload(),
      language: document.getElementById("advisor-language").value,
      question: document.getElementById("advisor-question").value.trim() || null
    };
    const result = await postAdvisor(payload);
    status.textContent = result.used_llm
      ? "Personalized advice based on your field data."
      : result.error?.includes("GEMINI_API_KEY not set")
        ? "AI is not configured. These are built-in suggestions, not AI-generated advice."
        : "AI is unavailable. Showing built-in suggestions instead.";
    const isArabic = payload.language === "ar";
    advice.dir = isArabic ? "rtl" : "auto";
    renderAdvisorFacts(facts, result.facts, isArabic);
    renderAdvisorSections(advice, result.advice);
    advice.classList.remove("hidden");

    (result.sources || []).forEach((source) => {
      if (!source.url || !source.url.startsWith("https://")) return;
      const item = document.createElement("li");
      const link = document.createElement("a");
      link.href = source.url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = source.title || source.url;
      item.append(link);
      sources.append(item);
    });
    const hasSources = sources.childElementCount > 0;
    sources.classList.toggle("hidden", !hasSources);
    sourcesTitle.classList.toggle("hidden", !hasSources);
  } catch (err) {
    status.textContent = `Unable to get advice: ${err.message}`;
  } finally {
    button.disabled = false;
    button.textContent = "Refresh AI Advice";
    response.setAttribute("aria-busy", "false");
  }
}

function renderAdvisorFacts(container, facts, isArabic) {
  if (!facts) return;
  const numberFormat = new Intl.NumberFormat(isArabic ? "ar" : "en", {
    maximumFractionDigits: 1
  });
  const metrics = [];
  const yieldEstimate = facts.yield?.kg_per_ha;
  if (Number.isFinite(yieldEstimate)) {
    const confidence = facts.yield.confidence
      ? `Confidence: ${facts.yield.confidence}`
      : "";
    metrics.push([
      "Yield estimate",
      `${numberFormat.format(yieldEstimate)} kg/ha`,
      confidence
    ]);
  }

  const waterGap = facts.water?.gap_7d_mm;
  if (Number.isFinite(waterGap)) {
    metrics.push([
      "7-day water gap",
      `${numberFormat.format(waterGap)} mm`,
      facts.water.status || ""
    ]);
  }

  const ndviTrend = facts.ndvi?.trend_60d;
  if (Number.isFinite(ndviTrend)) {
    const change = `${ndviTrend > 0 ? "+" : ""}${ndviTrend.toFixed(2)}`;
    metrics.push(["NDVI trend", change, "60 days"]);
  }

  metrics.forEach(([label, value, detail]) => {
    const metric = document.createElement("div");
    metric.className = "advisor-fact";
    const metricLabel = document.createElement("span");
    metricLabel.className = "advisor-fact-label";
    metricLabel.textContent = label;
    const metricValue = document.createElement("strong");
    metricValue.textContent = value;
    metric.append(metricLabel, metricValue);
    if (detail) {
      const metricDetail = document.createElement("small");
      metricDetail.textContent = detail;
      metric.append(metricDetail);
    }
    container.append(metric);
  });
  container.classList.toggle("hidden", metrics.length === 0);
}

function renderAdvisorSections(container, text) {
  const headings = {
    summary: "Summary",
    "this season": "This season",
    water: "Water",
    "soil and nutrients": "Soil and nutrients",
    "next seasons": "Next seasons",
    "risks to watch": "Risks to watch"
  };
  const headingPattern = /^\s*(?:#{1,3}\s*)?(?:\*\*)?(Summary|This season|Water|Soil and nutrients|Next seasons|Risks to watch)(?:\*\*)?\s*:?\s*(.*?)\s*$/i;
  const sections = [];
  let currentSection = null;

  (text || "").split(/\r?\n/).forEach((line) => {
    const match = line.match(headingPattern);
    if (match) {
      currentSection = {
        title: headings[match[1].toLowerCase()],
        items: []
      };
      sections.push(currentSection);
      if (match[2]) currentSection.items.push(cleanAdvisorLine(match[2]));
    } else if (line.trim()) {
      if (!currentSection) {
        currentSection = { title: "Advice", items: [] };
        sections.push(currentSection);
      }
      currentSection.items.push(cleanAdvisorLine(line));
    }
  });

  sections
    .filter((section) => section.items.length > 0)
    .forEach((section, index) => {
      const card = document.createElement("section");
      card.className = "advisor-card";
      if (section.title === "Summary") card.classList.add("advisor-card-summary");

      const heading = document.createElement("h3");
      const number = document.createElement("span");
      number.className = "advisor-card-number";
      number.textContent = String(index + 1).padStart(2, "0");
      const title = document.createElement("span");
      title.textContent = section.title;
      heading.append(number, title);

      const list = document.createElement("ul");
      section.items.forEach((itemText) => {
        const item = document.createElement("li");
        item.textContent = itemText;
        list.append(item);
      });
      card.append(heading, list);
      container.append(card);
    });
}

function cleanAdvisorLine(line) {
  return line.trim().replace(/^(?:[-*•]|\d+[.)])\s+/, "").replace(/\*\*/g, "");
}

function updateCropOptions(region = null, allCropOptions = null) {
  const cropSelect = document.getElementById("crop");
  const coverageNote = document.getElementById("crop-model-coverage");
  if (!cropSelect || !coverageNote) return;

  if (!Array.isArray(region?.supported_crops) || !allCropOptions) {
    if (allCropOptions) cropSelect.replaceChildren(...allCropOptions);
    coverageNote.textContent = "";
    coverageNote.classList.add("hidden");
    return;
  }

  const supported = new Set(region.supported_crops);
  const options = allCropOptions.filter((option) => supported.has(option.value));
  cropSelect.replaceChildren(...options);
  cropSelect.value = supported.has(region.default_crop)
    ? region.default_crop
    : options[0]?.value || "";

  const suitabilityCrops = region.suitability_crops || [];
  coverageNote.textContent = `Yield benchmarks: ${options.map((option) => option.textContent.trim()).join(", ")}. Validated crop-suitability prior: ${suitabilityCrops.length ? suitabilityCrops.join(", ") : "none"}.`;
  coverageNote.classList.remove("hidden");
}

function updateSensorVisibility() {
  const enabled = document.getElementById("use-live-sensor").checked;
  document.getElementById("sensor-options").classList.toggle("hidden", !enabled);
  document.getElementById("sensor-status-card").classList.toggle("hidden", !enabled);
}

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
      getNormalizedPriorityWeights();
      clearTimeout(priorityUpdateTimer);
      priorityUpdateTimer = setTimeout(runFullAnalysis, 300);
    });
  });
}

function collectFormPayload() {
  const payload = {
    lat: parseFloat(document.getElementById("lat").value),
    lon: parseFloat(document.getElementById("lon").value),
    crop: document.getElementById("crop").value,
    previous_crop: document.getElementById("previous_crop").value || null,
    field_size_ha: parseFloat(document.getElementById("field_size_ha").value),
    planting_date: document.getElementById("planting_date").value,
    soil_texture: document.getElementById("soil_texture").value,
    irrigation_availability: document.getElementById("irrigation_availability").value,
    planning_horizon_seasons: parseInt(document.getElementById("planning_horizon_seasons").value, 10),
    rotation_priority_weights: getNormalizedPriorityWeights()
  };
  if (document.getElementById("use-live-sensor").checked) {
    payload.use_live_sensor = true;
    payload.device_id = document.getElementById("device-id").value.trim();
  }
  return payload;
}

async function runFullAnalysis() {
  const loadingEl = document.getElementById("loading-state");
  const errorEl = document.getElementById("error-state");
  errorEl.classList.add("hidden");
  loadingEl.classList.remove("hidden");

  try {
    const payload = collectFormPayload();
    const recResult = await postRecommendation(payload);
    const [trendsData, sensorStatus] = await Promise.all([
      fetchTrends(payload.lat, payload.lon, 365),
      payload.use_live_sensor
        ? fetchTelemetryStatus(payload.device_id)
        : Promise.resolve(null)
    ]);

    renderRecommendationDashboard(recResult.data, payload, recResult.isLive);
    renderEarthIntelligenceCharts(trendsData);
    setHistoricalMapData(payload.lat, payload.lon, trendsData);
    if (sensorStatus) renderSensorStatus(recResult.data, sensorStatus);
  } catch (err) {
    errorEl.textContent = `Unable to render analysis: ${err.message}`;
    errorEl.classList.remove("hidden");
  } finally {
    loadingEl.classList.add("hidden");
  }
}

function renderSensorStatus(recommendation, status) {
  const online = Boolean(status.online);
  const dot = document.getElementById("sensor-online-dot");
  dot.classList.toggle("sensor-online", online);
  dot.classList.toggle("sensor-offline", !online);
  document.getElementById("sensor-online-label").textContent =
    online ? "Live Node Online" : "Live Node Offline";

  const satelliteMoisture = recommendation.satellite_soil_moisture_top;
  document.getElementById("satellite-soil-moisture").textContent =
    Number.isFinite(satelliteMoisture)
      ? `${(satelliteMoisture * 100).toFixed(1)}%`
      : "Unavailable";

  const liveMoisture = status.reading?.soil_moisture_top;
  document.getElementById("live-soil-moisture").textContent =
    Number.isFinite(liveMoisture) ? `${(liveMoisture * 100).toFixed(1)}%` : "—";

  const receivedAt = status.last_seen ? Date.parse(status.last_seen) : NaN;
  document.getElementById("sensor-last-seen").textContent = Number.isFinite(receivedAt)
    ? `Last seen ${Math.max(0, Math.floor((Date.now() - receivedAt) / 1000))}s ago`
    : "No telemetry received yet";
}

function renderRecommendationDashboard(data, payload, isLive) {
  document.getElementById("res-irrig-mm").textContent = `${Number(data.irrigation_mm_per_week).toFixed(1)} mm/wk`;
  document.getElementById("res-irrig-date").textContent = data.next_irrigation_date;

  const badgeEl = document.getElementById("irrig-mode-badge");
  const rotationBadgeEl = document.getElementById("rotation-mode-badge");
  const fallbackSources = data.fallback_sources || [];
  const fallbackMessage = !isLive
    ? "Offline demo results; values are placeholders, not field recommendations."
    : fallbackSources.length
      ? `Using fallback data for: ${fallbackSources.join(", ")}. Verify before acting.`
      : "";
  for (const badge of [badgeEl, rotationBadgeEl]) {
    badge.textContent = fallbackMessage;
    badge.classList.toggle("hidden", !fallbackMessage);
  }

  const cropMeta = KC_TABLE[payload.crop] || { kc: 1.15, stage: "Mid-season" };
  const et0 = 4.2;
  const etc = Number((et0 * cropMeta.kc).toFixed(2));

  document.getElementById("spec-crop").textContent = formatCropName(payload.crop);
  document.getElementById("spec-stage").textContent = cropMeta.stage;
  document.getElementById("spec-et0").textContent = `${et0} mm/day`;
  document.getElementById("spec-kc").textContent = cropMeta.kc.toFixed(2);
  document.getElementById("spec-etc").textContent = `${etc} mm/day`;

  renderRotationList(data.rotation_recommendations);
  renderRotationBaseline(data.baseline_score, payload.previous_crop, payload.crop, isLive);

  document.getElementById("res-yield").textContent = Number(data.yield_estimate_kg_ha).toLocaleString();

  const confEl = document.getElementById("res-confidence");
  const confLevel = (data.confidence || "Medium").toLowerCase();
  confEl.textContent = `Confidence: ${data.confidence || "Medium"}`;
  confEl.className = `confidence-badge confidence-${confLevel}`;

  document.getElementById("res-notes").textContent =
    data.notes || "Baseline estimate from documented environmental variables and FAOSTAT history; not a trained model.";
}

function renderRotationList(recommendations) {
  const listEl = document.getElementById("rotation-list");
  listEl.innerHTML = "";

  (recommendations || []).slice(0, 3).forEach((item) => {
    const li = document.createElement("li");
    const seqTitle = item.sequence_label || item.crop
      .split(" → ")
      .map(formatCropName)
      .join(" → ");
    li.innerHTML = `
      <span class="rotation-item-title">${seqTitle}</span>
      <span class="rotation-score">Score: ${Number(item.score).toFixed(2)}</span>
      <span class="rotation-reason">${item.reason}</span>
    `;
    listEl.appendChild(li);
  });
}

function renderRotationBaseline(score, previousCrop, currentCrop, isLive) {
  const baselineEl = document.getElementById("rotation-baseline");
  if (!previousCrop) {
    baselineEl.classList.add("hidden");
    baselineEl.textContent = "";
    return;
  }

  baselineEl.textContent = Number.isFinite(score)
    ? `Existing practice (${formatCropName(previousCrop)} → ${formatCropName(currentCrop)}): ${Number(score).toFixed(2)} / 1.00`
    : isLive
      ? "Existing-practice score unavailable: a selected crop is not in the rotation reference data."
      : "Existing-practice score unavailable in offline demo mode.";
  baselineEl.classList.remove("hidden");
}

function renderEarthIntelligenceCharts(trends) {
  currentEarthTrends = trends;
  const fallbackNote = document.getElementById("trends-fallback-note");
  const sources = trends.fallback_sources || [];
  fallbackNote.textContent = trends.offline
    ? "Offline demo charts are placeholders, not live satellite or weather observations."
    : sources.length
      ? `Fallback chart data used for: ${sources.join(", ")}.`
      : "";
  fallbackNote.classList.toggle("hidden", !fallbackNote.textContent);

  const climateCtx = document.getElementById("climateChart").getContext("2d");
  const ndviCtx = document.getElementById("ndviChart").getContext("2d");
  const forecastCtx = document.getElementById("forecastChart").getContext("2d");

  if (climateChartInstance) climateChartInstance.destroy();
  if (ndviChartInstance) ndviChartInstance.destroy();
  if (forecastChartInstance) forecastChartInstance.destroy();
  if (vulnerabilityTrendChartInstance) vulnerabilityTrendChartInstance.destroy();

  const recentClimate = {
    dates: trends.climate_history.dates.slice(-30),
    temp_c: trends.climate_history.temp_c.slice(-30),
    precip_mm: trends.climate_history.precip_mm.slice(-30)
  };
  climateChartInstance = new Chart(climateCtx, {
    type: "bar",
    data: {
      labels: recentClimate.dates,
      datasets: [
        {
          type: "line",
          label: "Temp (°C)",
          data: recentClimate.temp_c,
          borderColor: "#dc2626",
          backgroundColor: "#dc2626",
          yAxisID: "yTemp",
          tension: 0.3
        },
        {
          type: "bar",
          label: "Precip (mm)",
          data: recentClimate.precip_mm,
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

  const vulnerabilityCtx = document.getElementById("vulnerabilityTrendChart").getContext("2d");
  vulnerabilityTrendChartInstance = new Chart(vulnerabilityCtx, {
    type: "line",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      onClick: (event) => {
        const chart = vulnerabilityTrendChartInstance;
        const area = chart.chartArea;
        if (event.x < area.left || event.x > area.right || event.y < area.top || event.y > area.bottom) return;
        let index = Math.round(chart.scales.x.getValueForPixel(event.x));
        const values = chart.data.datasets[0]?.data || [];
        if (!Number.isFinite(values[index])) {
          index = values.reduce((nearest, value, candidate) =>
            Number.isFinite(value) &&
            (!Number.isFinite(values[nearest]) || Math.abs(candidate - index) < Math.abs(nearest - index))
              ? candidate
              : nearest, -1
          );
        }
        if (index < 0) return;
        const slider = document.getElementById("historical-map-date");
        slider.value = String(index);
        slider.dispatchEvent(new Event("input", { bubbles: true }));
      },
      scales: {
        y: { title: { display: true, text: "" } }
      },
      plugins: {
        legend: { display: false },
        thresholdLine: { value: null, label: "" }
      }
    },
    plugins: [{
      id: "thresholdLine",
      afterDraw(chart, _args, options) {
        if (!Number.isFinite(options.value)) return;
        const y = chart.scales.y.getPixelForValue(options.value);
        if (y < chart.chartArea.top || y > chart.chartArea.bottom) return;
        const { ctx, chartArea } = chart;
        ctx.save();
        ctx.strokeStyle = "#dc2626";
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(chartArea.left, y);
        ctx.lineTo(chartArea.right, y);
        ctx.stroke();
        ctx.fillStyle = "#b91c1c";
        ctx.font = "12px system-ui";
        ctx.fillText(options.label, chartArea.left + 6, y - 6);
        ctx.restore();
      }
    }]
  });
  updateVulnerabilityTrendSelection(
    document.getElementById("historical-map-metric").value,
    Number(document.getElementById("historical-map-date").value)
  );
}

function updateVulnerabilityTrendSelection(metric, selectedIndex) {
  if (!vulnerabilityTrendChartInstance) return;
  const trends = currentEarthTrends;
  const climate = trends?.climate_history;
  const dates = Array.isArray(climate?.dates) ? climate.dates : [];
  const seriesByMetric = {
    water_stress: {
      key: "soil_moisture",
      label: "NASA POWER root-zone wetness index",
      color: "#0284c7",
      threshold: 0.30,
      thresholdLabel: "Low-wetness screening threshold (0.30)",
      min: 0,
      max: 1
    },
    heat: {
      key: "temp_max_c",
      label: "NASA POWER daily maximum temperature (°C)",
      color: "#ea580c",
      threshold: 35,
      thresholdLabel: "Heat screening threshold (35°C)"
    },
    frost: {
      key: "temp_min_c",
      label: "NASA POWER daily minimum temperature (°C)",
      color: "#2563eb",
      threshold: 0,
      thresholdLabel: "Frost screening threshold (0°C)"
    }
  };
  const config = seriesByMetric[metric] || seriesByMetric.water_stress;
  const sourceAvailable = !trends?.offline && !(trends?.fallback_sources || []).includes("NASA POWER");
  const values = sourceAvailable && Array.isArray(climate?.[config.key])
    ? climate[config.key]
    : [];
  const data = dates.map((_date, index) => Number.isFinite(values[index]) ? values[index] : null);
  const availableCount = data.filter(Number.isFinite).length;
  const chartStatus = document.getElementById("vulnerability-chart-status");
  chartStatus.textContent = availableCount
    ? ""
    : trends?.offline || (trends?.fallback_sources || []).includes("NASA POWER")
      ? "NASA POWER daily data is unavailable. Check the backend connection; fallback demo values are intentionally not plotted as observations."
      : `This /trends response contains no daily ${config.label.toLowerCase()} series. Restart the backend after updating it to include T2M_MAX, T2M_MIN, and GWETROOT.`;
  chartStatus.classList.toggle("hidden", availableCount > 0);

  const colorAt = (value) => {
    if (!Number.isFinite(value)) return "#94a3b8";
    if (metric === "water_stress") return value < config.threshold ? "#dc2626" : config.color;
    if (metric === "heat") return value >= config.threshold ? "#dc2626" : config.color;
    return value <= config.threshold ? "#dc2626" : config.color;
  };

  vulnerabilityTrendChartInstance.data.labels = dates;
  vulnerabilityTrendChartInstance.data.datasets = [{
    label: config.label,
    data,
    borderColor: config.color,
    backgroundColor: `${config.color}22`,
    pointBackgroundColor: data.map(colorAt),
    pointRadius: data.map((_value, index) => index === selectedIndex ? 6 : 3),
    pointHoverRadius: 7,
    fill: true,
    tension: 0.2,
    spanGaps: false
  }];
  vulnerabilityTrendChartInstance.options.scales.y.title.text = config.label;
  if (Number.isFinite(config.min)) vulnerabilityTrendChartInstance.options.scales.y.min = config.min;
  else delete vulnerabilityTrendChartInstance.options.scales.y.min;
  if (Number.isFinite(config.max)) vulnerabilityTrendChartInstance.options.scales.y.max = config.max;
  else delete vulnerabilityTrendChartInstance.options.scales.y.max;
  vulnerabilityTrendChartInstance.options.plugins.thresholdLine.value = config.threshold;
  vulnerabilityTrendChartInstance.options.plugins.thresholdLine.label = config.thresholdLabel;
  vulnerabilityTrendChartInstance.update("none");
}
