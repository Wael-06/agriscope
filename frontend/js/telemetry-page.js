let pollTimer = null;

document.addEventListener("DOMContentLoaded", () => {
  initAppShell("telemetry", { showContextBar: true });
  const state = getFieldState();

  const toggle = document.getElementById("use-live-sensor");
  const deviceInput = document.getElementById("device-id");
  toggle.checked = Boolean(state.use_live_sensor);
  deviceInput.value = state.device_id || "demo-esp32-01";

  toggle.addEventListener("change", () => {
    saveFieldState({ use_live_sensor: toggle.checked, device_id: deviceInput.value.trim() || "demo-esp32-01" });
    refreshTelemetry();
  });

  deviceInput.addEventListener("change", () => {
    saveFieldState({ device_id: deviceInput.value.trim() || "demo-esp32-01" });
    refreshTelemetry();
  });

  document.getElementById("refresh-telemetry-btn").addEventListener("click", refreshTelemetry);

  document.getElementById("irrigate-now-btn").addEventListener("click", async () => {
    const deviceId = deviceInput.value.trim() || "demo-esp32-01";
    const duration = parseInt(document.getElementById("pump-duration").value, 10) || 5;
    const statusEl = document.getElementById("sensor-command-status");
    try {
      await postDeviceCommand(deviceId, true, duration);
      statusEl.className = "banner banner-info";
      statusEl.textContent = `Irrigation command queued for ${deviceId} (${duration}s).`;
      statusEl.classList.remove("hidden");
    } catch (err) {
      statusEl.className = "banner banner-error";
      statusEl.textContent = `Command failed: ${err.message}`;
      statusEl.classList.remove("hidden");
    }
  });

  document.getElementById("auto-poll").addEventListener("change", (e) => {
    if (e.target.checked) {
      pollTimer = setInterval(refreshTelemetry, 5000);
    } else if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  });

  refreshTelemetry();
});

async function refreshTelemetry() {
  const deviceId = document.getElementById("device-id").value.trim() || "demo-esp32-01";
  const payload = buildRecommendationPayload({ ...getFieldState(), use_live_sensor: true, device_id: deviceId });

  const [status, rec] = await Promise.all([
    fetchTelemetryStatus(deviceId),
    postRecommendation(payload)
  ]);

  const online = Boolean(status.online);
  const dot = document.getElementById("sensor-online-dot");
  dot.className = `pulse-dot ${online ? "online" : "offline"}`;
  document.getElementById("sensor-online-label").textContent = online ? "Live Node Online" : "Live Node Offline";

  const satVal = rec.data?.satellite_soil_moisture_top;
  const satPct = Number.isFinite(satVal) ? Math.min(100, Math.max(0, satVal * 100)) : null;
  document.getElementById("satellite-soil-moisture").textContent = satPct !== null ? `${satPct.toFixed(1)}%` : "Unavailable";
  document.getElementById("sat-gauge-fill").style.width = satPct !== null ? `${satPct}%` : "0%";

  const liveVal = status.reading?.soil_moisture_top;
  const livePct = Number.isFinite(liveVal) ? Math.min(100, Math.max(0, liveVal * 100)) : null;
  document.getElementById("live-soil-moisture").textContent = livePct !== null ? `${livePct.toFixed(1)}%` : "—";
  document.getElementById("live-gauge-fill").style.width = livePct !== null ? `${livePct}%` : "0%";

  const temp = status.reading?.temperature_c;
  const hum = status.reading?.humidity_pct;
  document.getElementById("sensor-env-temp").textContent = Number.isFinite(temp) ? `${temp.toFixed(1)} °C` : "—";
  document.getElementById("sensor-env-hum").textContent = Number.isFinite(hum) ? `${hum.toFixed(0)} %` : "—";

  const ts = status.last_seen ? Date.parse(status.last_seen) : NaN;
  document.getElementById("sensor-last-seen").textContent = Number.isFinite(ts)
    ? `Last telemetry received ${Math.max(0, Math.floor((Date.now() - ts) / 1000))}s ago`
    : "No telemetry packets received yet for this device ID.";
}
