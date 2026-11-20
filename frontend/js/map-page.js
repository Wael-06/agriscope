let climateChartInstance = null;
let ndviChartInstance = null;
let forecastChartInstance = null;
let vulnerabilityTrendChartInstance = null;
let currentEarthTrends = null;
let playbackInterval = null;

function applyChartDefaults() {
  if (typeof Chart === "undefined") return;
  const dark = getTheme() === "dark";
  Chart.defaults.font.family = '"Public Sans", system-ui, sans-serif';
  Chart.defaults.font.size = 12;
  Chart.defaults.color = dark ? "#9ab0ab" : "#5d716e";
  Chart.defaults.borderColor = dark ? "#1e353d" : "#e3e9e5";
  Chart.defaults.plugins.legend.labels.usePointStyle = true;
  Chart.defaults.plugins.legend.labels.boxHeight = 8;
}

document.addEventListener("DOMContentLoaded", async () => {
  initAppShell("map", { showContextBar: true });
  applyChartDefaults();

  initMap((coords) => {
    saveFieldState({
      regionId: null,
      regionName: `${coords.lat.toFixed(3)}, ${coords.lon.toFixed(3)}`,
      country: "CUSTOM",
      lat: coords.lat,
      lon: coords.lon
    });
    document.querySelectorAll("#map-region-chips .preset-btn").forEach((b) => b.classList.remove("active"));
    loadMapTrends(coords.lat, coords.lon);
  });

  const regions = await fetchRegions();
  renderMapRegions(regions, (reg) => {
    applyRegionToState(reg);
    loadMapTrends(reg.lat, reg.lon);
  });

  document.getElementById("play-timeline-btn").addEventListener("click", toggleTimelinePlayback);

  window.addEventListener("agriscope:themechange", () => {
    applyChartDefaults();
    if (currentEarthTrends) renderEarthIntelligenceCharts(currentEarthTrends);
  });

  const s = getFieldState();
  setMapMarker(s.lat, s.lon, null, false);
  await loadMapTrends(s.lat, s.lon);
});

function toggleTimelinePlayback() {
  const btn = document.getElementById("play-timeline-btn");
  const slider = document.getElementById("historical-map-date");
  if (playbackInterval) {
    clearInterval(playbackInterval);
    playbackInterval = null;
    btn.textContent = "Play";
    return;
  }
  const max = Number(slider.max) || 0;
  if (max <= 0) return;
  if (Number(slider.value) >= max) slider.value = "0";
  btn.textContent = "Pause";
  playbackInterval = setInterval(() => {
    const next = Number(slider.value) + 1;
    if (next > max) {
      clearInterval(playbackInterval);
      playbackInterval = null;
      btn.textContent = "Play";
      return;
    }
    slider.value = String(next);
    slider.dispatchEvent(new Event("input", { bubbles: true }));
  }, 150);
}

async function loadMapTrends(lat, lon) {
  const loading = document.getElementById("map-loading");
  loading.classList.remove("hidden");
  try {
    const trends = await fetchTrends(lat, lon, 365);
    renderEarthIntelligenceCharts(trends);
    setHistoricalMapData(lat, lon, trends);
  } finally {
    loading.classList.add("hidden");
  }
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

  if (climateChartInstance) climateChartInstance.destroy();
  if (ndviChartInstance) ndviChartInstance.destroy();
  if (forecastChartInstance) forecastChartInstance.destroy();
  if (vulnerabilityTrendChartInstance) vulnerabilityTrendChartInstance.destroy();

  const recentClimate = {
    dates: trends.climate_history.dates.slice(-30),
    temp_c: trends.climate_history.temp_c.slice(-30),
    precip_mm: trends.climate_history.precip_mm.slice(-30)
  };

  climateChartInstance = new Chart(document.getElementById("climateChart").getContext("2d"), {
    type: "bar",
    data: {
      labels: recentClimate.dates,
      datasets: [
        { type: "line", label: "Temp (°C)", data: recentClimate.temp_c, borderColor: "#c83e2b", backgroundColor: "#c83e2b", yAxisID: "yTemp", tension: 0.3 },
        { type: "bar", label: "Precip (mm)", data: recentClimate.precip_mm, backgroundColor: "#0277bd", yAxisID: "yPrecip" }
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

  ndviChartInstance = new Chart(document.getElementById("ndviChart").getContext("2d"), {
    type: "line",
    data: {
      labels: trends.ndvi_history.dates,
      datasets: [
        { label: "MODIS NDVI", data: trends.ndvi_history.ndvi, borderColor: "#1f8a52", backgroundColor: "rgba(31, 138, 82, 0.16)", fill: true, tension: 0.3 }
      ]
    },
    options: { responsive: true, scales: { y: { min: 0, max: 1.0, title: { display: true, text: "NDVI" } } } }
  });

  forecastChartInstance = new Chart(document.getElementById("forecastChart").getContext("2d"), {
    type: "bar",
    data: {
      labels: trends.forecast_7d.dates,
      datasets: [
        { type: "line", label: "Max Temp (°C)", data: trends.forecast_7d.max_temp_c, borderColor: "#c98a16", backgroundColor: "#c98a16", yAxisID: "yTemp", tension: 0.3 },
        { type: "bar", label: "Forecast Precip (mm)", data: trends.forecast_7d.precip_mm, backgroundColor: "#38bdf8", yAxisID: "yPrecip" }
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

  vulnerabilityTrendChartInstance = new Chart(document.getElementById("vulnerabilityTrendChart").getContext("2d"), {
    type: "line",
    data: { labels: [], datasets: [] },
    options: {
      responsive: true,
      interaction: { mode: "index", intersect: false },
      onClick: (event) => {
        const chart = vulnerabilityTrendChartInstance;
        const area = chart.chartArea;
        if (event.x < area.left || event.x > area.right || event.y < area.top || event.y > area.bottom) return;
        const index = Math.round(chart.scales.x.getValueForPixel(event.x));
        const values = chart.data.datasets[0]?.data || [];
        if (!Number.isFinite(values[index])) return;
        const slider = document.getElementById("historical-map-date");
        slider.value = String(index);
        slider.dispatchEvent(new Event("input", { bubbles: true }));
      },
      scales: { y: { title: { display: true, text: "" } } },
      plugins: { legend: { display: false }, thresholdLine: { value: null, label: "" } }
    },
    plugins: [{
      id: "thresholdLine",
      afterDraw(chart, _args, options) {
        if (!Number.isFinite(options.value)) return;
        const y = chart.scales.y.getPixelForValue(options.value);
        if (y < chart.chartArea.top || y > chart.chartArea.bottom) return;
        const { ctx, chartArea } = chart;
        ctx.save();
        ctx.strokeStyle = "#ef4444";
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(chartArea.left, y);
        ctx.lineTo(chartArea.right, y);
        ctx.stroke();
        ctx.fillStyle = "#ef4444";
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
  const cfgMap = {
    water_stress: { key: "soil_moisture", label: "Root-zone wetness index", color: "#0277bd", threshold: 0.30, thresholdLabel: "Low-wetness threshold (0.30)", min: 0, max: 1 },
    heat: { key: "temp_max_c", label: "Daily maximum temperature (°C)", color: "#c98a16", threshold: 35, thresholdLabel: "Heat threshold (35°C)" },
    frost: { key: "temp_min_c", label: "Daily minimum temperature (°C)", color: "#2563eb", threshold: 0, thresholdLabel: "Frost threshold (0°C)" }
  };
  const cfg = cfgMap[metric] || cfgMap.water_stress;
  const ok = !trends?.offline && !(trends?.fallback_sources || []).includes("NASA POWER");
  const values = ok && Array.isArray(climate?.[cfg.key]) ? climate[cfg.key] : [];
  const data = dates.map((_d, i) => Number.isFinite(values[i]) ? values[i] : null);
  const count = data.filter(Number.isFinite).length;

  const status = document.getElementById("vulnerability-chart-status");
  status.textContent = count
    ? ""
    : "NASA POWER daily data is unavailable for this metric. Fallback values are intentionally not plotted as observations.";
  status.classList.toggle("hidden", count > 0);

  const colorAt = (v) => {
    if (!Number.isFinite(v)) return "#94a3b8";
    if (metric === "water_stress") return v < cfg.threshold ? "#ef4444" : cfg.color;
    if (metric === "heat") return v >= cfg.threshold ? "#ef4444" : cfg.color;
    return v <= cfg.threshold ? "#ef4444" : cfg.color;
  };

  vulnerabilityTrendChartInstance.data.labels = dates;
  vulnerabilityTrendChartInstance.data.datasets = [{
    label: cfg.label,
    data,
    borderColor: cfg.color,
    backgroundColor: `${cfg.color}22`,
    pointBackgroundColor: data.map(colorAt),
    pointRadius: data.map((_v, i) => i === selectedIndex ? 6 : 2.5),
    pointHoverRadius: 7,
    fill: true,
    tension: 0.2,
    spanGaps: false
  }];
  vulnerabilityTrendChartInstance.options.scales.y.title.text = cfg.label;
  if (Number.isFinite(cfg.min)) vulnerabilityTrendChartInstance.options.scales.y.min = cfg.min;
  else delete vulnerabilityTrendChartInstance.options.scales.y.min;
  if (Number.isFinite(cfg.max)) vulnerabilityTrendChartInstance.options.scales.y.max = cfg.max;
  else delete vulnerabilityTrendChartInstance.options.scales.y.max;
  vulnerabilityTrendChartInstance.options.plugins.thresholdLine.value = cfg.threshold;
  vulnerabilityTrendChartInstance.options.plugins.thresholdLine.label = cfg.thresholdLabel;
  vulnerabilityTrendChartInstance.update("none");
}
