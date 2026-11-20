const NAV_ITEMS = [
  {
    id: "earth",
    href: "index.html",
    label: "3D Earth",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><path d="M2 12h20"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg>`
  },
  {
    id: "planner",
    href: "planner.html",
    label: "Field Planner",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2v20"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>`
  },
  {
    id: "map",
    href: "map.html",
    label: "Vulnerability Map",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="3 6 9 3 15 6 21 3 21 18 15 21 9 18 3 21"/><line x1="9" y1="3" x2="9" y2="18"/><line x1="15" y1="6" x2="15" y2="21"/></svg>`
  },
  {
    id: "advisor",
    href: "advisor.html",
    label: "AI Advisor",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3z"/></svg>`
  },
  {
    id: "telemetry",
    href: "telemetry.html",
    label: "Field Sensors",
    icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M1.42 9a16 16 0 0 1 21.16 0"/><path d="M8.53 16.11a6 6 0 0 1 6.95 0"/><line x1="12" y1="20" x2="12.01" y2="20"/></svg>`
  }
];

function getThemeIcon(theme) {
  if (theme === "dark") {
    return `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>`;
  }
  return `<svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>`;
}

function initAppShell(activePageId, options = { showContextBar: true }) {
  const headerMount = document.getElementById("app-header-mount");
  if (headerMount) {
    const linksHtml = NAV_ITEMS.map((item) => `
      <a href="${item.href}" class="nav-link${item.id === activePageId ? " active" : ""}">
        ${item.icon}<span>${item.label}</span>
      </a>
    `).join("");

    headerMount.innerHTML = `
      <header class="app-navbar">
        <div class="nav-inner">
          <a href="index.html" class="brand-link" title="Return to 3D Earth view">
            <svg class="brand-mark" viewBox="0 0 36 36" aria-hidden="true">
              <rect width="36" height="36" rx="10" fill="#156248" />
              <circle cx="18" cy="14.5" r="5.5" fill="#f0b443" />
              <path d="M5 27c4-5 8-7 13-7s9 2 13 7" fill="none" stroke="#fff" stroke-width="2.1" stroke-linecap="round" />
              <path d="M9 31c3-3 6-4.5 9-4.5s6 1.5 9 4.5" fill="none" stroke="#9ad5bc" stroke-width="2" stroke-linecap="round" />
            </svg>
            <div>
              <div class="brand-title">AgriScope</div>
              <span class="brand-sub">NASA Space Apps 2026 · Field Shift</span>
            </div>
          </a>

          <nav class="nav-links" aria-label="Primary navigation">${linksHtml}</nav>

          <div class="nav-actions">
            <div id="api-status" class="status-pill status-mock">Checking…</div>
            <button type="button" id="theme-toggle-btn" class="icon-btn" aria-label="Toggle color theme" title="Switch light / dark theme">
              ${getThemeIcon(getTheme())}
            </button>
            <button type="button" id="mobile-menu-btn" class="icon-btn mobile-menu-btn" aria-label="Open menu">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="3" y1="6" x2="21" y2="6"/><line x1="3" y1="12" x2="21" y2="12"/><line x1="3" y1="18" x2="21" y2="18"/></svg>
            </button>
          </div>
        </div>
        <nav id="mobile-drawer" class="mobile-drawer" aria-label="Mobile navigation">${linksHtml}</nav>
      </header>
      ${options.showContextBar ? `<div id="context-bar" class="context-bar"></div>` : ""}
    `;

    const themeBtn = document.getElementById("theme-toggle-btn");
    themeBtn.addEventListener("click", () => {
      const next = toggleTheme();
      themeBtn.innerHTML = getThemeIcon(next);
    });

    const mobileBtn = document.getElementById("mobile-menu-btn");
    const mobileDrawer = document.getElementById("mobile-drawer");
    mobileBtn.addEventListener("click", () => mobileDrawer.classList.toggle("open"));
  }

  const footerMount = document.getElementById("app-footer-mount");
  if (footerMount) {
    footerMount.innerHTML = `
      <footer class="app-footer">
        <div class="footer-inner">
          <span><strong>AgriScope</strong> — Turning NASA POWER, MODIS NDVI & Open-Meteo data into climate-resilient field decisions.</span>
          <span>Research prototype · Not an official NASA product or certified agronomic prescription.</span>
        </div>
      </footer>
    `;
  }

  if (options.showContextBar) renderContextBar();
  checkBackendHealth();
}

function renderContextBar() {
  const bar = document.getElementById("context-bar");
  if (!bar) return;
  const s = getFieldState();
  const soilNames = { clay: "Clay", loam: "Loam", sandy: "Sandy" };
  const irrigNames = { available: "Available", limited: "Limited", none: "Rainfed" };
  bar.innerHTML = `
    <div class="context-bar-inner">
      <div class="context-chips">
        <span class="context-chip">Location: <strong>${s.regionName || `${Number(s.lat).toFixed(2)}, ${Number(s.lon).toFixed(2)}`}</strong></span>
        <span class="context-chip">Coords: <strong>${Number(s.lat).toFixed(3)}, ${Number(s.lon).toFixed(3)}</strong></span>
        <span class="context-chip">Crop: <strong>${formatCropName(s.crop)}</strong></span>
        <span class="context-chip">Soil: <strong>${soilNames[s.soil_texture] || s.soil_texture}</strong></span>
        <span class="context-chip">Irrigation: <strong>${irrigNames[s.irrigation_availability] || s.irrigation_availability}</strong></span>
        ${s.use_live_sensor ? `<span class="context-chip">Sensor: <strong>${s.device_id}</strong></span>` : ""}
      </div>
      <a class="context-action" href="planner.html">Edit field settings →</a>
    </div>
  `;
}
