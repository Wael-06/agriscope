let globeInstance = null;

function initLandingGlobe(regions, onRegionSelectedFromGlobe) {
  const container = document.getElementById("globe-container");
  const overlay = document.getElementById("globe-overlay");
  if (!container || typeof Globe === "undefined") {
    if (overlay) overlay.classList.add("fade-out");
    return;
  }

  const pointsData = (regions || []).map((r) => ({
    ...r,
    size: 0.45,
    color: "#4ade80"
  }));

  globeInstance = Globe()(container)
    .globeImageUrl("https://unpkg.com/three-globe/example/img/earth-blue-marble.jpg")
    .bumpImageUrl("https://unpkg.com/three-globe/example/img/earth-topology.png")
    .backgroundImageUrl("https://unpkg.com/three-globe/example/img/night-sky.png")
    .showAtmosphere(true)
    .atmosphereColor("#38bdf8")
    .atmosphereAltitude(0.18)
    .pointsData(pointsData)
    .pointLat("lat")
    .pointLng("lon")
    .pointColor("color")
    .pointAltitude(0.03)
    .pointRadius("size")
    .ringsData(pointsData)
    .ringLat("lat")
    .ringLng("lon")
    .ringColor(() => "#22c55e")
    .ringMaxRadius(3.5)
    .ringPropagationSpeed(2.0)
    .ringRepeatPeriod(900)
    .labelsData(pointsData)
    .labelLat("lat")
    .labelLng("lon")
    .labelText("name")
    .labelSize(1.25)
    .labelDotRadius(0.45)
    .labelColor(() => "#ffffff")
    .labelResolution(2)
    .onPointClick((point) => {
      zoomGlobeAndTransition(point, onRegionSelectedFromGlobe);
    })
    .onLabelClick((point) => {
      zoomGlobeAndTransition(point, onRegionSelectedFromGlobe);
    });

  globeInstance.pointOfView({ lat: 28.5, lng: 30.8, altitude: 1.85 }, 0);

  const controls = globeInstance.controls();
  if (controls) {
    controls.autoRotate = true;
    controls.autoRotateSpeed = 0.45;
  }

  document.getElementById("enter-dashboard-btn").addEventListener("click", () => {
    const defaultRegion = pointsData[0] || { lat: 31.11, lon: 30.94 };
    zoomGlobeAndTransition(defaultRegion, onRegionSelectedFromGlobe);
  });

  document.getElementById("reopen-globe-btn").addEventListener("click", () => {
    overlay.classList.remove("fade-out");
    globeInstance.pointOfView({ lat: 28.5, lng: 30.8, altitude: 1.75 }, 900);
    if (controls) controls.autoRotate = true;
  });

  window.addEventListener("resize", () => {
    if (globeInstance) {
      globeInstance.width(window.innerWidth);
      globeInstance.height(window.innerHeight);
    }
  });
}

function zoomGlobeAndTransition(targetRegion, callback) {
  const overlay = document.getElementById("globe-overlay");
  if (!globeInstance || !overlay) return;

  const controls = globeInstance.controls();
  if (controls) controls.autoRotate = false;

  globeInstance.pointOfView(
    { lat: targetRegion.lat, lng: targetRegion.lon, altitude: 0.32 },
    1100
  );

  setTimeout(() => {
    overlay.classList.add("fade-out");
    if (callback && targetRegion.id) {
      callback(targetRegion);
    }
    if (typeof mapInstance !== "undefined" && mapInstance) {
      setTimeout(() => mapInstance.invalidateSize(), 200);
    }
  }, 1150);
}
