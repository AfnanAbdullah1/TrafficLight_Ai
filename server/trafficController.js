/**
 * ============================================================
 *  AI Hybrid Traffic Lights Control System
 *  Traffic Controller — Core Logic Module
 * ============================================================
 *
 *  Manages the traffic light state machine, operating modes,
 *  density-based adaptive timing, and emergency overrides.
 *
 * ============================================================
 */

const EventEmitter = require("events");

class TrafficController extends EventEmitter {
  constructor() {
    super();

    this.TOTAL_ROUTES = 3;

    // ── Operating modes ──
    this.MODE = { AUTO: "auto", MANUAL: "manual", EMERGENCY: "emergency" };
    this.currentMode = this.MODE.AUTO;

    // ── Default timing (ms) ──
    this.defaultGreen = 5000;
    this.defaultYellow = 2000;
    this.defaultRedGap = 3000;

    // ── Per-route configurable timing ──
    this.routeTimings = {
      1: { green: 5000, yellow: 2000, redGap: 3000 },
      2: { green: 5000, yellow: 2000, redGap: 3000 },
      3: { green: 5000, yellow: 2000, redGap: 3000 },
    };

    // ── Current state ──
    this.routeStates = {
      1: "red",
      2: "red",
      3: "red",
    };

    // ── Density data (from AI engine) ──
    this.densityData = {
      1: { count: 0, level: "low", updatedAt: null },
      2: { count: 0, level: "low", updatedAt: null },
      3: { count: 0, level: "low", updatedAt: null },
    };

    // ── Vehicle counts (from ultrasonic) ──
    this.vehicleCounts = { 1: 0, 2: 0 };

    // ── Pedestrian alerts ──
    this.pedestrianAlerts = { 1: false, 2: false, 3: false };

    // ── State machine ──
    // States: [route]_green, [route]_yellow, [route]_redgap
    this.stateSequence = [
      { name: "route1_green", route: 1, light: "green", timingKey: "green" },
      { name: "route1_yellow", route: 1, light: "yellow", timingKey: "yellow" },
      { name: "route1_redgap", route: 0, light: "red", timingKey: "redGap" },
      { name: "route2_green", route: 2, light: "green", timingKey: "green" },
      { name: "route2_yellow", route: 2, light: "yellow", timingKey: "yellow" },
      { name: "route2_redgap", route: 0, light: "red", timingKey: "redGap" },
      { name: "route3_green", route: 3, light: "green", timingKey: "green" },
      { name: "route3_yellow", route: 3, light: "yellow", timingKey: "yellow" },
      { name: "route3_redgap", route: 0, light: "red", timingKey: "redGap" },
    ];

    this.currentStateIndex = 0;
    this.stateTimer = null;
    this.stateStartTime = null;
    this.isPaused = false;

    // ── Emergency state ──
    this.emergencyRoute = null;

    // ── Master device status ──
    this.masterStatus = { online: false, lastSeen: null };
  }

  // ── Start the automatic sequence ──
  start() {
    console.log("[TRAFFIC] Starting traffic controller in AUTO mode");
    this.currentMode = this.MODE.AUTO;
    this.currentStateIndex = 0;
    this.executeCurrentState();
  }

  // ── Stop everything ──
  stop() {
    if (this.stateTimer) clearTimeout(this.stateTimer);
    this.stateTimer = null;
    console.log("[TRAFFIC] Controller stopped");
  }

  // ── Execute the current state in the sequence ──
  executeCurrentState() {
    if (this.currentMode !== this.MODE.AUTO) return;
    if (this.isPaused) return;

    const state = this.stateSequence[this.currentStateIndex];
    const routeForTiming =
      state.route || this.stateSequence[this.currentStateIndex - 1]?.route || 1;

    // Set all routes to red first
    for (let r = 1; r <= this.TOTAL_ROUTES; r++) {
      this.routeStates[r] = "red";
    }

    // Set the active route's light
    if (state.route > 0) {
      this.routeStates[state.route] = state.light;
    }

    // Get duration for this state
    let duration =
      this.routeTimings[routeForTiming][state.timingKey] ||
      this.defaultGreen;

    // If this is a green state, check density for adaptive timing
    if (state.timingKey === "green") {
      duration = this.getAdaptiveTiming(state.route);
    }

    this.stateStartTime = Date.now();

    // Emit state change to broadcast via MQTT and WebSocket
    this.emit("stateChange", {
      states: { ...this.routeStates },
      currentPhase: state.name,
      duration: duration,
      mode: this.currentMode,
      stateIndex: this.currentStateIndex,
    });

    console.log(
      `[TRAFFIC] ${state.name} | Duration: ${duration}ms | Routes: R1=${this.routeStates[1]} R2=${this.routeStates[2]} R3=${this.routeStates[3]}`
    );

    // Schedule next state
    this.stateTimer = setTimeout(() => {
      this.currentStateIndex =
        (this.currentStateIndex + 1) % this.stateSequence.length;
      this.executeCurrentState();
    }, duration);
  }

  // ── Get adaptive timing based on density ──
  getAdaptiveTiming(route) {
    const density = this.densityData[route];
    if (!density || !density.updatedAt) {
      return this.routeTimings[route].green; // Use configured default
    }

    // Check if density data is fresh (within last 30 seconds)
    const age = Date.now() - new Date(density.updatedAt).getTime();
    if (age > 30000) {
      return this.routeTimings[route].green; // Stale data, use default
    }

    // Map density count to green time
    const count = density.count;
    if (count <= 3) return Math.max(this.routeTimings[route].green, 5000);
    if (count <= 8) return 10000;
    if (count <= 15) return 20000;
    return 30000; // Very high density
  }

  // ── Mode switching ──
  setMode(mode) {
    const prevMode = this.currentMode;
    this.currentMode = mode;

    console.log(`[TRAFFIC] Mode changed: ${prevMode} → ${mode}`);

    if (mode === this.MODE.AUTO && prevMode !== this.MODE.AUTO) {
      // Restart auto sequence
      this.stop();
      this.start();
    } else if (mode === this.MODE.MANUAL) {
      this.stop(); // Stop auto sequence, wait for manual commands
    } else if (mode === this.MODE.EMERGENCY) {
      this.stop(); // Stop auto sequence, wait for emergency commands
    }

    this.emit("modeChange", { mode, prevMode });
  }

  // ── Manual route control ──
  setRouteState(route, state) {
    if (route < 1 || route > this.TOTAL_ROUTES) return;
    if (!["red", "yellow", "green", "off"].includes(state)) return;

    // Safety: if setting a route to green, set all others to red
    if (state === "green") {
      for (let r = 1; r <= this.TOTAL_ROUTES; r++) {
        this.routeStates[r] = r === route ? "green" : "red";
      }
    } else {
      this.routeStates[route] = state;
    }

    this.emit("stateChange", {
      states: { ...this.routeStates },
      currentPhase: `manual_route${route}_${state}`,
      duration: 0,
      mode: this.currentMode,
    });
  }

  // ── Emergency override ──
  activateEmergency(route) {
    console.log(`[EMERGENCY] Activating emergency on Route ${route}`);

    this.emergencyRoute = route;
    this.setMode(this.MODE.EMERGENCY);

    // Force the emergency route green, all others red
    for (let r = 1; r <= this.TOTAL_ROUTES; r++) {
      this.routeStates[r] = r === route ? "green" : "red";
    }

    this.emit("stateChange", {
      states: { ...this.routeStates },
      currentPhase: `emergency_route${route}`,
      duration: 0,
      mode: this.MODE.EMERGENCY,
    });

    this.emit("emergency", { active: true, route });
  }

  deactivateEmergency() {
    console.log("[EMERGENCY] Deactivating emergency, resuming AUTO");
    this.emergencyRoute = null;

    // Resume auto mode
    this.setMode(this.MODE.AUTO);

    this.emit("emergency", { active: false, route: null });
  }

  // ── Update timing for a route ──
  updateTiming(route, greenMs) {
    if (route < 1 || route > this.TOTAL_ROUTES) return;
    if (greenMs < 1000 || greenMs > 60000) return;

    this.routeTimings[route].green = greenMs;
    console.log(`[TIMING] Route ${route} green time updated to ${greenMs}ms`);

    this.emit("timingChange", {
      route,
      timing: this.routeTimings[route],
    });
  }

  // ── Update density data (from AI engine) ──
  updateDensity(route, count) {
    if (route < 1 || route > this.TOTAL_ROUTES) return;

    let level = "low";
    if (count > 15) level = "very_high";
    else if (count > 8) level = "high";
    else if (count > 3) level = "medium";

    this.densityData[route] = {
      count,
      level,
      updatedAt: new Date().toISOString(),
    };

    console.log(
      `[DENSITY] Route ${route}: ${count} vehicles (${level})`
    );

    this.emit("densityUpdate", { route, count, level });
  }

  // ── Update vehicle count (from ultrasonic) ──
  updateVehicleCount(route, count) {
    this.vehicleCounts[route] = count;
    this.emit("vehicleCount", { route, count });
  }

  // ── Pedestrian alert ──
  handlePedestrianAlert(route) {
    this.pedestrianAlerts[route] = true;
    console.log(`[PEDESTRIAN] Alert on Route ${route}`);

    this.emit("pedestrianAlert", { route });

    // Auto-clear after 10 seconds
    setTimeout(() => {
      this.pedestrianAlerts[route] = false;
    }, 10000);
  }

  // ── Get full system status ──
  getFullStatus() {
    return {
      mode: this.currentMode,
      routes: { ...this.routeStates },
      timings: JSON.parse(JSON.stringify(this.routeTimings)),
      density: JSON.parse(JSON.stringify(this.densityData)),
      vehicleCounts: { ...this.vehicleCounts },
      pedestrians: { ...this.pedestrianAlerts },
      emergency: {
        active: this.currentMode === this.MODE.EMERGENCY,
        route: this.emergencyRoute,
      },
      masterOnline: this.masterStatus.online,
      uptime: process.uptime(),
    };
  }
}

module.exports = TrafficController;
