let mapInstance = null;
let activeMarker = null;
let loadedRegions = [];

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
        fillColor: country === "USA" ? "#60a5fa" : country === "CHINA" ? "#f87171" : "#22c55e",
        fillOpacity: 0.75
      }).addTo(mapInstance);

      circle.bindTooltip(reg.name);
      circle.on("click", () => btn.click());
    });
    group.appendChild(buttons);
    container.appendChild(group);
  });
}
