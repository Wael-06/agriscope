let plannerRegions = [];
let plannerMap = null;
let plannerPin = null;
let weightTimer = null;

document.addEventListener("DOMContentLoaded", async () => {
  initAppShell("planner", { showContextBar: true });
  populateCropDropdowns();
  plannerRegions = await fetchRegions();
  initPlannerMap(plannerRegions);
  renderPlannerRegions(plannerRegions);
  hydratePlannerForm(getFieldState());
  bindPlannerEvents();
  await runPlannerAnalysis();
});

function initPlannerMap(regions) {
  const s = getFieldState();
  plannerMap = L.map("planner-map", { zoomControl: false }).setView([s.lat || 31.11, s.lon || 30.94], 9);
  L.control.zoom({ position: "bottomright" }).addTo(plannerMap);

  wireBasemapSwitcher("planner-basemap-switcher", plannerMap, getPreferredBasemap());

  plannerPin = L.marker([s.lat, s.lon], { icon: createPulsingPinIcon(), zIndexOffset: 500 }).addTo(plannerMap);
  updatePlannerMapHud(s.regionName, s.lat, s.lon);

  regions.forEach((reg) => {
    const stroke = reg.country === "USA" ? "#38bdf8" : reg.country === "CHINA" ? "#f59e0b" : "#34d399";
    const marker = L.circleMarker([reg.lat, reg.lon], {
      radius: 6,
      weight: 2,
      color: stroke,
      fillColor: stroke,
      fillOpacity: 0.45
    }).addTo(plannerMap);
    marker.bindTooltip(`<strong>${reg.name}</strong><br/>Click to select region`);
    marker.on("click", () => selectPlannerRegion(reg));
  });

  plannerMap.on("click", (e) => {
    const lat = Number(e.latlng.lat.toFixed(4));
    const lon = Number(e.latlng.lng.toFixed(4));
    plannerPin.setLatLng([lat, lon]);
    updatePlannerMapHud("Custom Field Pin", lat, lon);
    document.getElementById("lat").value = lat;
    document.getElementById("lon").value = lon;
    const regSel = document.getElementById("planner-region-select"); if (regSel) regSel.value = "";
    readFormToState();
    runPlannerAnalysis();
  });

  const expandBtn = document.getElementById("expand-planner-map-btn");
  const canvas = document.getElementById("planner-map");
  expandBtn.addEventListener("click", () => {
    const expanded = canvas.classList.toggle("expanded");
    expandBtn.textContent = expanded ? "Compact" : "Expand";
    setTimeout(() => plannerMap.invalidateSize(), 260);
  });
}

function updatePlannerMapHud(label, lat, lon) {
  const n = document.getElementById("planner-map-location");
  const c = document.getElementById("planner-map-coords");
  if (n) n.textContent = label || "Field Pin";
  if (c) c.textContent = `${Number(lat).toFixed(3)}°, ${Number(lon).toFixed(3)}°`;
}

function syncPlannerMapView(lat, lon, label, fly = true) {
  if (!plannerMap || !plannerPin) return;
  plannerPin.setLatLng([lat, lon]);
  updatePlannerMapHud(label, lat, lon);
  if (fly) plannerMap.flyTo([lat, lon], 9, { duration: 0.9 });
  else plannerMap.panTo([lat, lon]);
}

function populateCropDropdowns() {
  const cropSel = document.getElementById("crop");
  const prevSel = document.getElementById("previous_crop");
  cropSel.innerHTML = ALL_CROPS.map((c) => `<option value="${c.value}">${c.label}</option>`).join("");
  prevSel.innerHTML = `<option value="">Skip comparison</option>` +
    ALL_CROPS.map((c) => `<option value="${c.value}">${c.label}</option>`).join("");
}

function selectPlannerRegion(reg) {
  const next = applyRegionToState(reg);
  const regSel = document.getElementById("planner-region-select");
  if (regSel) regSel.value = reg.id;
  updateCropCoverage(reg);
  hydratePlannerForm(next);
  syncPlannerMapView(reg.lat, reg.lon, reg.name, true);
  runPlannerAnalysis();
}

function renderPlannerRegions(regions) {
  const select = document.getElementById("planner-region-select");
  if (!select) return;
  select.innerHTML = "";

  const customOpt = document.createElement("option");
  customOpt.value = "";
  customOpt.textContent = "Custom location (map pin / coordinates)";
  select.appendChild(customOpt);

  const grouped = regions.reduce((acc, r) => {
    const country = r.country || "EGYPT";
    (acc[country] ||= []).push(r);
    return acc;
  }, {});
  const labels = { EGYPT: "Egypt", USA: "United States", CHINA: "China" };

  Object.entries(grouped).forEach(([country, list]) => {
    const optgroup = document.createElement("optgroup");
    optgroup.label = labels[country] || country;
    list.forEach((reg) => {
      const opt = document.createElement("option");
      opt.value = reg.id;
      opt.textContent = reg.name;
      optgroup.appendChild(opt);
    });
    select.appendChild(optgroup);
  });

  const activeId = getFieldState().regionId || "";
  select.value = regions.some((r) => r.id === activeId) ? activeId : "";

  select.addEventListener("change", () => {
    const picked = regions.find((r) => r.id === select.value);
    if (picked) selectPlannerRegion(picked);
  });
}

function updateCropCoverage(region) {
  const cropSel = document.getElementById("crop");
  const note = document.getElementById("crop-model-coverage");
  const currentVal = cropSel.value;

  if (!Array.isArray(region?.supported_crops)) {
    cropSel.innerHTML = ALL_CROPS.map((c) => `<option value="${c.value}">${c.label}</option>`).join("");
    cropSel.value = currentVal || "wheat";
    note.textContent = "";
    note.classList.add("hidden");
    return;
  }

  const supported = new Set(region.supported_crops);
  const filtered = ALL_CROPS.filter((c) => supported.has(c.value));
  cropSel.innerHTML = filtered.map((c) => `<option value="${c.value}">${c.label}</option>`).join("");
  cropSel.value = supported.has(region.default_crop) ? region.default_crop : filtered[0]?.value || "";

  const suit = region.suitability_crops || [];
  note.textContent = `Yield benchmarks: ${filtered.map((c) => formatCropName(c.value)).join(", ")}. Validated suitability prior: ${suit.length ? suit.join(", ") : "none"}.`;
  note.classList.remove("hidden");
}

function hydratePlannerForm(state) {
  document.getElementById("lat").value = state.lat;
  document.getElementById("lon").value = state.lon;
  const matchedRegion = plannerRegions.find((r) => r.id === state.regionId);
  if (matchedRegion) updateCropCoverage(matchedRegion);
  document.getElementById("crop").value = state.crop;
  document.getElementById("previous_crop").value = state.previous_crop || "";
  document.getElementById("field_size_ha").value = state.field_size_ha;
  document.getElementById("planting_date").value = state.planting_date;
  document.getElementById("soil_texture").value = state.soil_texture;
  document.getElementById("irrigation_availability").value = state.irrigation_availability;
  document.getElementById("planning_horizon_seasons").value = state.planning_horizon_seasons;

  document.getElementById("weight-soil").value = state.weights.soil;
  document.getElementById("weight-water").value = state.weights.water;
  document.getElementById("weight-climate").value = state.weights.climate;
  refreshWeightLabels();
}

function readFormToState() {
  const lat = parseFloat(document.getElementById("lat").value);
  const lon = parseFloat(document.getElementById("lon").value);
  const matched = plannerRegions.find((r) => Math.abs(r.lat - lat) < 0.001 && Math.abs(r.lon - lon) < 0.001);

  return saveFieldState({
    regionId: matched ? matched.id : null,
    regionName: matched ? matched.name : `${lat.toFixed(3)}, ${lon.toFixed(3)}`,
    country: matched?.country || "CUSTOM",
    lat,
    lon,
    crop: document.getElementById("crop").value,
    previous_crop: document.getElementById("previous_crop").value || "",
    field_size_ha: parseFloat(document.getElementById("field_size_ha").value),
    planting_date: document.getElementById("planting_date").value,
    soil_texture: document.getElementById("soil_texture").value,
    irrigation_availability: document.getElementById("irrigation_availability").value,
    planning_horizon_seasons: parseInt(document.getElementById("planning_horizon_seasons").value, 10),
    weights: {
      soil: parseFloat(document.getElementById("weight-soil").value) || 0,
      water: parseFloat(document.getElementById("weight-water").value) || 0,
      climate: parseFloat(document.getElementById("weight-climate").value) || 0
    }
  });
}

function refreshWeightLabels() {
  const norm = computeNormalizedWeights({
    soil: document.getElementById("weight-soil").value,
    water: document.getElementById("weight-water").value,
    climate: document.getElementById("weight-climate").value
  });
  document.getElementById("val-soil").textContent = norm.soil_health.toFixed(2);
  document.getElementById("val-water").textContent = norm.water_demand.toFixed(2);
  document.getElementById("val-climate").textContent = norm.climate_suitability.toFixed(2);
}

function bindPlannerEvents() {
  document.getElementById("farmer-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const s = readFormToState();
    syncPlannerMapView(s.lat, s.lon, s.regionName, true);
    const regSel = document.getElementById("planner-region-select");
    if (regSel) regSel.value = s.regionId || "";
    runPlannerAnalysis();
  });

  ["weight-soil", "weight-water", "weight-climate"].forEach((id) => {
    document.getElementById(id).addEventListener("input", () => {
      refreshWeightLabels();
      readFormToState();
      clearTimeout(weightTimer);
      weightTimer = setTimeout(runPlannerAnalysis, 300);
    });
  });
}

async function runPlannerAnalysis() {
  const loading = document.getElementById("loading-state");
  const errorBox = document.getElementById("error-state");
  const btn = document.getElementById("submit-btn");
  errorBox.classList.add("hidden");
  loading.classList.remove("hidden");
  btn.disabled = true;

  try {
    const state = getFieldState();
    const payload = buildRecommendationPayload(state);
    const { data, isLive } = await postRecommendation(payload);
    renderPlannerResults(data, payload, isLive);
  } catch (err) {
    errorBox.textContent = `Unable to run field analysis: ${err.message}`;
    errorBox.classList.remove("hidden");
  } finally {
    loading.classList.add("hidden");
    btn.disabled = false;
  }
}

function renderPlannerResults(data, payload, isLive) {
  const yieldVal = Number(data.yield_estimate_kg_ha || 0);
  const irrigMm = Number(data.irrigation_mm_per_week || 0);
  const conf = data.confidence || "Medium";
  const confLower = conf.toLowerCase();
  const topRot = (data.rotation_recommendations || [])[0];

  document.getElementById("kpi-yield").textContent = `${yieldVal.toLocaleString()} kg/ha`;
  document.getElementById("kpi-yield-sub").textContent = `Confidence: ${conf}`;
  document.getElementById("kpi-irrig").textContent = `${irrigMm.toFixed(1)} mm/wk`;
  document.getElementById("kpi-irrig-sub").textContent = `Next date: ${data.next_irrigation_date || "—"}`;
  document.getElementById("kpi-crop").textContent = formatCropName(payload.crop);
  document.getElementById("kpi-crop-sub").textContent = `${payload.field_size_ha} ha · ${payload.soil_texture} soil`;
  document.getElementById("kpi-rotation").textContent = topRot ? Number(topRot.score).toFixed(2) : "—";
  document.getElementById("kpi-rotation-sub").textContent = topRot
    ? (topRot.sequence_label || formatCropName(topRot.crop))
    : "No sequences scored";

  document.getElementById("res-yield").textContent = yieldVal.toLocaleString();
  const confEl = document.getElementById("res-confidence");
  confEl.textContent = `Confidence: ${conf}`;
  confEl.className = `badge badge-${confLower === "high" ? "high" : confLower === "low" ? "low" : "medium"}`;
  document.getElementById("res-notes").textContent =
    data.notes || "Baseline estimate from documented environmental variables and FAOSTAT history.";

  document.getElementById("res-irrig-mm").textContent = `${irrigMm.toFixed(1)} mm/wk`;
  document.getElementById("res-irrig-date").textContent = data.next_irrigation_date || "—";

  const fallbackSources = data.fallback_sources || [];
  const fallbackMsg = !isLive
    ? "Offline demo mode — placeholder values shown."
    : fallbackSources.length
      ? `Fallback data used for: ${fallbackSources.join(", ")}.`
      : "";

  for (const id of ["irrig-mode-badge", "rotation-mode-badge"]) {
    const el = document.getElementById(id);
    el.textContent = fallbackMsg;
    el.classList.toggle("hidden", !fallbackMsg);
  }

  const cropMeta = KC_TABLE[payload.crop] || { kc: 1.15, stage: "Mid-season" };
  const et0 = 4.2;
  const etc = Number((et0 * cropMeta.kc).toFixed(2));
  document.getElementById("spec-crop").textContent = formatCropName(payload.crop);
  document.getElementById("spec-stage").textContent = cropMeta.stage;
  document.getElementById("spec-et0").textContent = `${et0} mm/day`;
  document.getElementById("spec-kc").textContent = cropMeta.kc.toFixed(2);
  document.getElementById("spec-etc").textContent = `${etc} mm/day`;

  const baselineEl = document.getElementById("rotation-baseline");
  if (!payload.previous_crop) {
    baselineEl.classList.add("hidden");
  } else {
    baselineEl.textContent = Number.isFinite(data.baseline_score)
      ? `Existing practice (${formatCropName(payload.previous_crop)} → ${formatCropName(payload.crop)}): ${Number(data.baseline_score).toFixed(2)} / 1.00`
      : isLive
        ? "Existing-practice score unavailable for this crop pair."
        : "Existing-practice score unavailable in offline demo mode.";
    baselineEl.classList.remove("hidden");
  }

  const listEl = document.getElementById("rotation-list");
  listEl.innerHTML = "";
  (data.rotation_recommendations || []).slice(0, 3).forEach((item, idx) => {
    const score = Number(item.score || 0);
    const pct = Math.max(0, Math.min(100, Math.round(score * 100)));
    const seqTitle = item.sequence_label || item.crop.split(" → ").map(formatCropName).join(" → ");
    const li = document.createElement("li");
    li.className = "rotation-item" + (idx === 0 ? " top-pick" : "");
    li.innerHTML = `
      <div class="rotation-item-top">
        <div class="rotation-title-wrap">
          <span class="rotation-rank">${idx + 1}</span>
          <span class="rotation-title">${seqTitle}</span>
        </div>
        <span class="rotation-score-pill">Score ${score.toFixed(2)}</span>
      </div>
      <div class="score-bar-track"><div class="score-bar-fill" style="width:${pct}%"></div></div>
      <p class="rotation-reason">${item.reason || ""}</p>
    `;
    listEl.appendChild(li);
  });
}
