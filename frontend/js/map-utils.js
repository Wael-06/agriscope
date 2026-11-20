function createBasemapGroup(styleKey) {
  if (styleKey === "satellite") {
    const imagery = L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 18,
        attribution: "Tiles &copy; Esri &mdash; Earthstar Geographics"
      }
    );
    const labels = L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 18,
        subdomains: "abcd",
        opacity: 0.92,
        attribution: "&copy; CARTO"
      }
    );
    return L.layerGroup([imagery, labels]);
  }

  if (styleKey === "terrain") {
    return L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 18,
        attribution: "Tiles &copy; Esri &mdash; World Topographic Map"
      }
    );
  }

  if (styleKey === "dark") {
    return L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
      {
        maxZoom: 18,
        subdomains: "abcd",
        attribution: "&copy; OpenStreetMap contributors &copy; CARTO"
      }
    );
  }

  return L.tileLayer(
    "https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png",
    {
      maxZoom: 18,
      subdomains: "abcd",
      attribution: "&copy; OpenStreetMap contributors &copy; CARTO"
    }
  );
}

function createPulsingPinIcon() {
  return L.divIcon({
    className: "agriscope-pin-wrapper",
    html: `<div class="agriscope-pin"><span class="agriscope-pin-pulse"></span><span class="agriscope-pin-core"></span></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 12],
    popupAnchor: [0, -14]
  });
}

function wireBasemapSwitcher(switcherId, map, initialStyle, onChange) {
  let activeLayer = createBasemapGroup(initialStyle).addTo(map);
  const container = document.getElementById(switcherId);

  const setStyle = (style) => {
    if (activeLayer) map.removeLayer(activeLayer);
    activeLayer = createBasemapGroup(style).addTo(map);
    if (activeLayer.bringToBack) activeLayer.bringToBack();
    setPreferredBasemap(style);
    if (container) {
      container.querySelectorAll(".basemap-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.basemap === style);
      });
    }
    if (onChange) onChange(style);
  };

  if (container) {
    container.querySelectorAll(".basemap-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.basemap === initialStyle);
      btn.addEventListener("click", () => setStyle(btn.dataset.basemap));
    });
  }

  return { setStyle };
}
