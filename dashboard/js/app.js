/**
 * ============================================================
 *  AI Hybrid Traffic Lights Control System
 *  Dashboard Client JavaScript
 * ============================================================
 *
 *  Connects to the server via Socket.IO (WebSocket) and
 *  provides real-time control and monitoring of traffic lights.
 *
 * ============================================================
 */

// ── Socket.IO Connection ──
const socket = io();

// ── State ──
let currentMode = "auto";
let emergencyActive = false;

// ── DOM References ──
const connectionStatus = document.getElementById("connectionStatus");
const uptimeText = document.getElementById("uptimeText");
const logContainer = document.getElementById("logContainer");
const emergencyBanner = document.getElementById("emergencyBanner");
const emergencyRouteDisplay = document.getElementById("emergencyRouteDisplay");
const cancelEmergencyBtn = document.getElementById("cancelEmergencyBtn");

// ── Connection Events ──
socket.on("connect", () => {
  connectionStatus.textContent = "Connected — Live";
  connectionStatus.classList.add("connected");
  addLog("Connected to server", "info");
});

socket.on("disconnect", () => {
  connectionStatus.textContent = "Disconnected";
  connectionStatus.classList.remove("connected");
  addLog("Disconnected from server", "emergency");
});

// ── Full Status Update ──
socket.on("fullStatus", (data) => {
  // Update mode buttons
  updateModeUI(data.mode);

  // Update route lights
  for (let r = 1; r <= 3; r++) {
    updateTrafficLight(r, data.routes[r] || "red");
  }

  // Update density
  for (let r = 1; r <= 3; r++) {
    if (data.density && data.density[r]) {
      updateDensityUI(r, data.density[r]);
    }
  }

  // Update vehicle counts
  if (data.vehicleCounts) {
    for (const [route, count] of Object.entries(data.vehicleCounts)) {
      const el = document.getElementById(`vehicleCount${route}`);
      if (el) el.textContent = count;
    }
  }

  // Update pedestrian alerts
  if (data.pedestrians) {
    for (let r = 1; r <= 3; r++) {
      const alertEl = document.getElementById(`pedAlert${r}`);
      if (alertEl) {
        alertEl.classList.toggle("hidden", !data.pedestrians[r]);
      }
    }
  }

  // Update emergency state
  if (data.emergency) {
    emergencyActive = data.emergency.active;
    updateEmergencyUI(data.emergency);
  }

  // Update uptime
  if (data.uptime) {
    const mins = Math.floor(data.uptime / 60);
    const secs = Math.floor(data.uptime % 60);
    uptimeText.textContent = `${String(mins).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }

  // Update timing sliders
  if (data.timings) {
    for (let r = 1; r <= 3; r++) {
      if (data.timings[r]) {
        const seconds = Math.round(data.timings[r].green / 1000);
        const slider = document.getElementById(`slider${r}`);
        const label = document.getElementById(`sliderLabel${r}`);
        if (slider) slider.value = seconds;
        if (label) label.textContent = `${seconds}s`;
      }
    }
  }
});

// ── State Change Event ──
socket.on("stateChange", (data) => {
  for (let r = 1; r <= 3; r++) {
    updateTrafficLight(r, data.states[r] || "red");
  }
  addLog(`${data.currentPhase} (${data.duration}ms)`, "info");
});

// ── Mode Change Event ──
socket.on("modeChange", (data) => {
  updateModeUI(data.mode);
  addLog(`Mode changed to ${data.mode.toUpperCase()}`, "warning");
});

// ── Emergency Event ──
socket.on("emergency", (data) => {
  emergencyActive = data.active;
  updateEmergencyUI(data);
  if (data.active) {
    addLog(`🚨 EMERGENCY ACTIVATED — Route ${data.route}`, "emergency");
  } else {
    addLog("Emergency deactivated — resuming auto", "info");
  }
});

// ── Density Update ──
socket.on("densityUpdate", (data) => {
  updateDensityUI(data.route, data);
  const el = document.getElementById(`vehicleCount${data.route}`);
  if (el) el.textContent = data.count;
});

// ── Vehicle Count ──
socket.on("vehicleCount", (data) => {
  const el = document.getElementById(`vehicleCount${data.route}`);
  if (el) el.textContent = data.count;
});

// ── Pedestrian Alert ──
socket.on("pedestrianAlert", (data) => {
  const alertEl = document.getElementById(`pedAlert${data.route}`);
  if (alertEl) {
    alertEl.classList.remove("hidden");
    addLog(`🚶 Pedestrian detected on Route ${data.route}`, "warning");
    // Auto-hide after 10 seconds
    setTimeout(() => alertEl.classList.add("hidden"), 10000);
  }
});

// ── Timing Change ──
socket.on("timingChange", (data) => {
  const seconds = Math.round(data.timing.green / 1000);
  const slider = document.getElementById(`slider${data.route}`);
  const label = document.getElementById(`sliderLabel${data.route}`);
  if (slider) slider.value = seconds;
  if (label) label.textContent = `${seconds}s`;
  addLog(`Route ${data.route} timing → ${seconds}s`, "info");
});

// ══════════════════════════════════════════════
//  UI UPDATE FUNCTIONS
// ══════════════════════════════════════════════

function updateTrafficLight(route, state) {
  // Update light indicators
  const lights = ["red", "yellow", "green"];
  lights.forEach((color) => {
    const el = document.getElementById(`light${route}_${color}`);
    if (el) {
      el.classList.toggle("active", color === state);
    }
  });

  // Update badge
  const badge = document.getElementById(`routeBadge${route}`);
  if (badge) {
    badge.textContent = state.toUpperCase();
    badge.className = `route-badge ${state}`;
  }

  // Update card border
  const card = document.getElementById(`routeCard${route}`);
  if (card) {
    card.className = `route-card active-${state}`;
  }
}

function updateModeUI(mode) {
  currentMode = mode;
  document.querySelectorAll(".mode-btn").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.mode === mode);
  });
}

function updateDensityUI(route, data) {
  const el = document.getElementById(`density${route}`);
  if (el) {
    const level = data.level || "low";
    el.textContent = level.charAt(0).toUpperCase() + level.slice(1).replace("_", " ");
    el.className = `info-value density-badge ${level}`;
  }
}

function updateEmergencyUI(data) {
  if (data.active) {
    emergencyBanner.classList.remove("hidden");
    cancelEmergencyBtn.classList.remove("hidden");
    emergencyRouteDisplay.textContent = data.route;
  } else {
    emergencyBanner.classList.add("hidden");
    cancelEmergencyBtn.classList.add("hidden");
  }
}

// ══════════════════════════════════════════════
//  USER ACTION FUNCTIONS (called from HTML)
// ══════════════════════════════════════════════

// Mode switching
document.querySelectorAll(".mode-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    const mode = btn.dataset.mode;
    socket.emit("setMode", mode);
    addLog(`Switching to ${mode.toUpperCase()} mode...`, "info");
  });
});

// Set route state (manual control)
function setRoute(route, state) {
  if (currentMode !== "manual" && currentMode !== "emergency") {
    // Auto-switch to manual mode when using route controls
    socket.emit("setMode", "manual");
  }
  socket.emit("setRoute", { route, state });
  addLog(`Manual: Route ${route} → ${state.toUpperCase()}`, "info");
}

// Timing slider label update
function updateSliderLabel(route, value) {
  document.getElementById(`sliderLabel${route}`).textContent = `${value}s`;
}

// Apply timing
function applyTiming(route) {
  const slider = document.getElementById(`slider${route}`);
  const greenMs = parseInt(slider.value) * 1000;
  socket.emit("setTiming", { route, greenMs });
  addLog(`Timing: Route ${route} → ${slider.value}s green`, "info");
}

// Emergency controls
function activateEmergency(route) {
  socket.emit("emergencyActivate", { route });
}

function deactivateEmergency() {
  socket.emit("emergencyDeactivate");
}

// ══════════════════════════════════════════════
//  LOGGING
// ══════════════════════════════════════════════

function addLog(message, type = "") {
  const entry = document.createElement("div");
  entry.className = `log-entry ${type}`;
  const time = new Date().toLocaleTimeString();
  entry.textContent = `[${time}] ${message}`;

  logContainer.insertBefore(entry, logContainer.firstChild);

  // Keep max 50 entries
  while (logContainer.children.length > 50) {
    logContainer.removeChild(logContainer.lastChild);
  }
}
