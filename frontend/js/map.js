let mapInstance = null;
let activeMarker = null;
let loadedRegions = [];

function initMap(onLocationSelected) {
  mapInstance = L.map("map").setView([28.8, 30.8], 6);

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

  regions.forEach((reg, idx) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.dataset.regionId = reg.id;
    btn.className = "preset-btn" + (idx === 0 ? " active" : "");
    btn.textContent = reg.name;

    btn.addEventListener("click", () => {
      clearActivePresetButtons();
      btn.classList.add("active");
      setMapMarker(reg.lat, reg.lon, `<strong>${reg.name}</strong><br/>Soil: ${reg.soil}`);
      onRegionPicked(reg);
    });

    container.appendChild(btn);

    const circle = L.circleMarker([reg.lat, reg.lon], {
      radius: 7,
      color: "#1b5e20",
      fillColor: "#22c55e",
      fillOpacity: 0.75
    }).addTo(mapInstance);

    circle.bindTooltip(reg.name);
    circle.on("click", () => btn.click());
  });
}
