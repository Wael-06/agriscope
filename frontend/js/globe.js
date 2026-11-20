let globeInstance = null;
let landingRegions = Array.isArray(FALLBACK_REGIONS) ? FALLBACK_REGIONS : [];

document.addEventListener("DOMContentLoaded", async () => {
  const plannerBtn = document.getElementById("enter-planner-btn");
  const mapBtn = document.getElementById("enter-map-btn");

  if (plannerBtn) {
    plannerBtn.addEventListener("click", () => {
      const target = landingRegions[0] || getFieldState();
      zoomIntoEarthAndNavigate(target, "planner.html");
    });
  }

  if (mapBtn) {
    mapBtn.addEventListener("click", () => {
      const target = landingRegions[0] || getFieldState();
      zoomIntoEarthAndNavigate(target, "map.html");
    });
  }

  initLandingEarth(landingRegions);
  checkBackendHealth();

  try {
    const fetched = await fetchRegions();
    if (Array.isArray(fetched) && fetched.length > 0) {
      landingRegions = fetched;
      updateEarthRegions(landingRegions);
    }
  } catch (err) {
    console.warn("Using fallback regions on globe:", err);
  }
});

function formatGlobePoints(regions) {
  return (regions || []).map((r) => ({
    ...r,
    size: 0.48,
    color: "#4ade80"
  }));
}

function initLandingEarth(regions) {
  const container = document.getElementById("globe-container");
  if (!container || typeof Globe === "undefined") return;

  try {
    const pointsData = formatGlobePoints(regions);

    globeInstance = Globe()(container)
      .width(window.innerWidth)
      .height(window.innerHeight)
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
      .ringRepeatPeriod(950)
      .labelsData(pointsData)
      .labelLat("lat")
      .labelLng("lon")
      .labelText("name")
      .labelSize(1.25)
      .labelDotRadius(0.45)
      .labelColor(() => "#ffffff")
      .labelResolution(2)
      .onPointClick((point) => zoomIntoEarthAndNavigate(point, "planner.html"))
      .onLabelClick((point) => zoomIntoEarthAndNavigate(point, "planner.html"));

    globeInstance.pointOfView({ lat: 26, lng: 25, altitude: 2.35 }, 0);

    const controls = globeInstance.controls();
    if (controls) {
      controls.autoRotate = true;
      controls.autoRotateSpeed = 0.42;
    }

    window.addEventListener("resize", () => {
      if (globeInstance) {
        globeInstance.width(window.innerWidth);
        globeInstance.height(window.innerHeight);
      }
    });
  } catch (err) {
    console.error("Globe initialization failed:", err);
    globeInstance = null;
  }
}

function updateEarthRegions(regions) {
  if (!globeInstance) return;
  const pointsData = formatGlobePoints(regions);
  globeInstance
    .pointsData(pointsData)
    .ringsData(pointsData)
    .labelsData(pointsData);
}

function zoomIntoEarthAndNavigate(targetRegion, destinationUrl) {
  if (targetRegion && targetRegion.lat !== undefined && targetRegion.lon !== undefined) {
    applyRegionToState(targetRegion);
  }

  const stage = document.getElementById("landing-stage");
  if (!globeInstance) {
    window.location.href = destinationUrl;
    return;
  }

  const controls = globeInstance.controls();
  if (controls) controls.autoRotate = false;

  globeInstance.pointOfView(
    { lat: targetRegion.lat, lng: targetRegion.lon, altitude: 0.30 },
    950
  );

  setTimeout(() => {
    if (stage) stage.classList.add("transitioning");
  }, 680);

  setTimeout(() => {
    window.location.href = destinationUrl;
  }, 1050);
}
