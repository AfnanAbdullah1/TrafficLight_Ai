/**
 * ============================================================
 *  AI Hybrid Traffic Lights Control System
 *  MQTT Handler Module
 * ============================================================
 *
 *  Connects to the Mosquitto MQTT broker and bridges
 *  communication between ESP32 devices and the server logic.
 *
 * ============================================================
 */

const mqtt = require("mqtt");

class MQTTHandler {
  constructor(trafficController, options = {}) {
    this.tc = trafficController;
    this.brokerUrl = options.brokerUrl || "mqtt://localhost:1883";
    this.client = null;
    this.connected = false;
  }

  connect() {
    console.log(`[MQTT] Connecting to broker: ${this.brokerUrl}`);

    this.client = mqtt.connect(this.brokerUrl, {
      clientId: "traffic_server_" + Date.now(),
      clean: true,
      reconnectPeriod: 3000,
    });

    this.client.on("connect", () => {
      this.connected = true;
      console.log("[MQTT] Connected to broker!");

      // Subscribe to all traffic topics
      this.client.subscribe("traffic/#", (err) => {
        if (err) console.error("[MQTT] Subscribe error:", err);
        else console.log("[MQTT] Subscribed to traffic/#");
      });
    });

    this.client.on("message", (topic, message) => {
      this.handleMessage(topic, message.toString());
    });

    this.client.on("error", (err) => {
      console.error("[MQTT] Error:", err.message);
    });

    this.client.on("close", () => {
      this.connected = false;
      console.log("[MQTT] Disconnected from broker");
    });

    // ── Listen to TrafficController events and publish to MQTT ──
    this.tc.on("stateChange", (data) => {
      // Send LED commands to each ESP32-CAM
      for (let route = 1; route <= 3; route++) {
        this.publish(
          `traffic/route/${route}/command`,
          data.states[route] || "red"
        );
      }
    });

    this.tc.on("modeChange", (data) => {
      this.publish("traffic/mode", data.mode);
    });

    this.tc.on("emergency", (data) => {
      if (data.active) {
        // Send emergency command — clear the specified route
        for (let route = 1; route <= 3; route++) {
          const state = route === data.route ? "green" : "red";
          this.publish("traffic/emergency", `route:${route}:${state}`);
        }
      } else {
        this.publish("traffic/mode", "auto");
      }
    });

    this.tc.on("timingChange", (data) => {
      this.publish(
        `traffic/route/${data.route}/timing`,
        String(data.timing.green)
      );
    });
  }

  handleMessage(topic, message) {
    try {
      // ── Route status updates from ESP32-CAMs ──
      const statusMatch = topic.match(/^traffic\/route\/(\d+)\/status$/);
      if (statusMatch) {
        // ESP32-CAM reporting its state — forward to dashboard via events
        const data = JSON.parse(message);
        this.tc.emit("espStatus", data);
        return;
      }

      // ── Density data from AI engine ──
      const densityMatch = topic.match(/^traffic\/density\/route(\d+)$/);
      if (densityMatch) {
        const route = parseInt(densityMatch[1]);
        const data = JSON.parse(message);
        this.tc.updateDensity(route, data.count || 0);
        return;
      }

      // ── Vehicle counts from WROOM ultrasonic ──
      const countMatch = topic.match(/^traffic\/vehicle_count\/(\d+)$/);
      if (countMatch) {
        const route = parseInt(countMatch[1]);
        const data = JSON.parse(message);
        this.tc.updateVehicleCount(route, data.count || 0);
        return;
      }

      // ── Pedestrian detection from PIR ──
      const pirMatch = topic.match(/^traffic\/pedestrian\/(\d+)$/);
      if (pirMatch) {
        const route = parseInt(pirMatch[1]);
        this.tc.handlePedestrianAlert(route);
        return;
      }

      // ── Master WROOM status ──
      if (topic === "traffic/master/status") {
        const data = JSON.parse(message);
        this.tc.masterStatus = {
          online: data.status === "online" || true,
          lastSeen: new Date().toISOString(),
        };
        return;
      }
    } catch (err) {
      // Non-JSON messages or parse errors — ignore silently
    }
  }

  publish(topic, message) {
    if (this.client && this.connected) {
      this.client.publish(topic, message);
    }
  }

  getStatus() {
    return {
      connected: this.connected,
      brokerUrl: this.brokerUrl,
    };
  }
}

module.exports = MQTTHandler;
