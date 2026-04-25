/**
 * ============================================================
 *  AI Hybrid Traffic Lights Control System
 *  Main Server Entry Point
 * ============================================================
 *
 *  Express + Socket.IO + MQTT
 *  Serves the dashboard and bridges all communication.
 *
 * ============================================================
 */

const express = require("express");
const http = require("http");
const { Server } = require("socket.io");
const path = require("path");
const cors = require("cors");

const TrafficController = require("./trafficController");
const MQTTHandler = require("./mqttHandler");

// ── Initialize ──
const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });

const tc = new TrafficController();
const mqttHandler = new MQTTHandler(tc, {
  brokerUrl: process.env.MQTT_URL || "mqtt://localhost:1883",
});

// ── Middleware ──
app.use(cors());
app.use(express.json());

// Serve dashboard from ../dashboard
app.use(express.static(path.join(__dirname, "..", "dashboard")));

// ── REST API ──
app.get("/api/status", (req, res) => {
  res.json(tc.getFullStatus());
});

app.post("/api/mode", (req, res) => {
  const { mode } = req.body;
  if (["auto", "manual", "emergency"].includes(mode)) {
    tc.setMode(mode);
    res.json({ success: true, mode });
  } else {
    res.status(400).json({ error: "Invalid mode. Use: auto, manual, emergency" });
  }
});

app.post("/api/route/:id/command", (req, res) => {
  const route = parseInt(req.params.id);
  const { state } = req.body;
  tc.setRouteState(route, state);
  res.json({ success: true, route, state });
});

app.post("/api/route/:id/timing", (req, res) => {
  const route = parseInt(req.params.id);
  const { greenMs } = req.body;
  tc.updateTiming(route, greenMs);
  res.json({ success: true, route, greenMs });
});

app.post("/api/emergency/activate", (req, res) => {
  const { route } = req.body;
  tc.activateEmergency(route);
  res.json({ success: true, emergency: true, route });
});

app.post("/api/emergency/deactivate", (req, res) => {
  tc.deactivateEmergency();
  res.json({ success: true, emergency: false });
});

// ── WebSocket (Socket.IO) ──
io.on("connection", (socket) => {
  console.log(`[WS] Client connected: ${socket.id}`);

  // Send current full status on connect
  socket.emit("fullStatus", tc.getFullStatus());

  // Handle commands from dashboard
  socket.on("setMode", (mode) => {
    tc.setMode(mode);
  });

  socket.on("setRoute", ({ route, state }) => {
    tc.setRouteState(route, state);
  });

  socket.on("setTiming", ({ route, greenMs }) => {
    tc.updateTiming(route, greenMs);
  });

  socket.on("emergencyActivate", ({ route }) => {
    tc.activateEmergency(route);
  });

  socket.on("emergencyDeactivate", () => {
    tc.deactivateEmergency();
  });

  socket.on("disconnect", () => {
    console.log(`[WS] Client disconnected: ${socket.id}`);
  });
});

// ── Forward TrafficController events to all WebSocket clients ──
tc.on("stateChange", (data) => io.emit("stateChange", data));
tc.on("modeChange", (data) => io.emit("modeChange", data));
tc.on("emergency", (data) => io.emit("emergency", data));
tc.on("densityUpdate", (data) => io.emit("densityUpdate", data));
tc.on("vehicleCount", (data) => io.emit("vehicleCount", data));
tc.on("pedestrianAlert", (data) => io.emit("pedestrianAlert", data));
tc.on("timingChange", (data) => io.emit("timingChange", data));
tc.on("espStatus", (data) => io.emit("espStatus", data));

// Periodic full status broadcast
setInterval(() => {
  io.emit("fullStatus", tc.getFullStatus());
}, 3000);

// ── Start ──
const PORT = process.env.PORT || 3000;

// Connect MQTT (don't fail if broker is offline)
try {
  mqttHandler.connect();
} catch (err) {
  console.warn("[MQTT] Broker not available, running without MQTT:", err.message);
}

// Start traffic controller
tc.start();

server.listen(PORT, () => {
  console.log("\n========================================");
  console.log("  AI Hybrid Traffic Lights - Server");
  console.log("========================================");
  console.log(`  Dashboard:  http://localhost:${PORT}`);
  console.log(`  API:        http://localhost:${PORT}/api/status`);
  console.log(`  MQTT:       ${mqttHandler.brokerUrl}`);
  console.log("========================================\n");
});
