function createBasemapGroup(styleKey) {
  if (styleKey === "terrain") {
    return L.tileLayer(
      "https://server.arcgisonline.com/ArcGIS/rest/services/World_Topo_Map/MapServer/tile/{z}/{y}/{x}",
      {
        maxZoom: 18,
        attribution: "Tiles &copy; Esri &mdash; World Topographic Map"
      }
    );
  }

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
  const safeInitial = initialStyle === "terrain" ? "terrain" : "satellite";
  let activeLayer = createBasemapGroup(safeInitial).addTo(map);
  const container = document.getElementById(switcherId);

  const setStyle = (style) => {
    const safeStyle = style === "terrain" ? "terrain" : "satellite";
    if (activeLayer) map.removeLayer(activeLayer);
    activeLayer = createBasemapGroup(safeStyle).addTo(map);
    if (activeLayer.bringToBack) activeLayer.bringToBack();
    setPreferredBasemap(safeStyle);
    if (container) {
      container.querySelectorAll(".basemap-btn").forEach((btn) => {
        btn.classList.toggle("active", btn.dataset.basemap === safeStyle);
      });
    }
    if (onChange) onChange(safeStyle);
  };

  if (container) {
    container.querySelectorAll(".basemap-btn").forEach((btn) => {
      btn.classList.toggle("active", btn.dataset.basemap === safeInitial);
      btn.addEventListener("click", () => setStyle(btn.dataset.basemap));
    });
  }

  return { setStyle };
}
