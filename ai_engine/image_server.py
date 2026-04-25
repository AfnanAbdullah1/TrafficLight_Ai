"""
============================================================
 AI Hybrid Traffic Lights Control System
 Image Server — Flask + MQTT
============================================================

 Receives JPEG frames from ESP32-CAMs via HTTP POST,
 runs YOLOv8 vehicle detection, and publishes density
 results to the MQTT broker.

 Endpoints:
   POST /upload/route<N>  — Receive a frame from route N
   GET  /status           — Get current density data
   GET  /health           — Health check

============================================================
"""

import os
import json
import time
import threading
from datetime import datetime

from flask import Flask, request, jsonify
import paho.mqtt.client as paho_mqtt

from vehicle_detector import VehicleDetector

# ── Configuration ──
MQTT_BROKER = os.environ.get("MQTT_BROKER", "localhost")
MQTT_PORT = int(os.environ.get("MQTT_PORT", 1883))
FLASK_PORT = int(os.environ.get("FLASK_PORT", 5000))
SAVE_FRAMES = os.environ.get("SAVE_FRAMES", "false").lower() == "true"
FRAMES_DIR = os.path.join(os.path.dirname(__file__), "frames")

# ── Initialize ──
app = Flask(__name__)
detector = VehicleDetector()

# MQTT Client
mqtt_client = paho_mqtt.Client(paho_mqtt.CallbackAPIVersion.VERSION2, client_id="ai_engine")
mqtt_connected = False

# Density state (last result per route)
density_state = {
    "route1": {"count": 0, "level": "low", "last_update": None, "processing_ms": 0},
    "route2": {"count": 0, "level": "low", "last_update": None, "processing_ms": 0},
    "route3": {"count": 0, "level": "low", "last_update": None, "processing_ms": 0},
}


def count_to_level(count):
    """Map vehicle count to density level."""
    if count <= 3:
        return "low"
    elif count <= 8:
        return "medium"
    elif count <= 15:
        return "high"
    else:
        return "very_high"


# ── MQTT Callbacks ──
def on_mqtt_connect(client, userdata, flags, reason_code, properties=None):
    global mqtt_connected
    if reason_code == 0:
        mqtt_connected = True
        print(f"[MQTT] Connected to broker at {MQTT_BROKER}:{MQTT_PORT}")
    else:
        print(f"[MQTT] Connection failed with code: {reason_code}")


def on_mqtt_disconnect(client, userdata, flags, reason_code, properties=None):
    global mqtt_connected
    mqtt_connected = False
    print("[MQTT] Disconnected from broker")


def connect_mqtt():
    """Connect to MQTT broker in a background thread."""
    global mqtt_connected
    try:
        mqtt_client.on_connect = on_mqtt_connect
        mqtt_client.on_disconnect = on_mqtt_disconnect
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
        mqtt_client.loop_start()
        print(f"[MQTT] Connecting to {MQTT_BROKER}:{MQTT_PORT}...")
    except Exception as e:
        mqtt_connected = False
        print(f"[MQTT] Failed to connect: {e}")
        print("[MQTT] Running without MQTT — density data available via /status endpoint only")


# ── Flask Routes ──

@app.route("/upload/<route_id>", methods=["POST"])
def receive_frame(route_id):
    """
    Receive a JPEG frame from an ESP32-CAM.
    
    Expected: POST with raw JPEG body
    Route ID format: "route1", "route2", "route3"
    """
    if not route_id.startswith("route"):
        return jsonify({"error": "Invalid route ID. Use: route1, route2, route3"}), 400

    image_data = request.data
    if not image_data or len(image_data) < 100:
        return jsonify({"error": "No image data received"}), 400

    # Save frame to disk (optional, for debugging)
    if SAVE_FRAMES:
        os.makedirs(FRAMES_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filepath = os.path.join(FRAMES_DIR, f"{route_id}_{timestamp}.jpg")
        with open(filepath, "wb") as f:
            f.write(image_data)

    # Run vehicle detection
    result = detector.count_vehicles(image_data)
    count = result["count"]
    level = count_to_level(count)

    # Update local state
    density_state[route_id] = {
        "count": count,
        "level": level,
        "last_update": datetime.now().isoformat(),
        "processing_ms": result["processing_time_ms"],
        "vehicles": result.get("vehicles", []),
    }

    # Publish to MQTT
    if mqtt_connected:
        mqtt_payload = json.dumps({"count": count, "level": level})
        mqtt_client.publish(f"traffic/density/{route_id}", mqtt_payload)

    print(
        f"[{route_id.upper()}] Vehicles: {count} ({level}) | "
        f"Processing: {result['processing_time_ms']:.0f}ms | "
        f"Frame size: {len(image_data)} bytes"
    )

    return jsonify({
        "route": route_id,
        "count": count,
        "level": level,
        "processing_ms": result["processing_time_ms"],
    })


@app.route("/status", methods=["GET"])
def get_status():
    """Get current density data for all routes."""
    return jsonify({
        "density": density_state,
        "mqtt_connected": mqtt_connected,
        "detector": "YOLOv8-nano",
    })


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok", "timestamp": datetime.now().isoformat()})


# ── Main ──
if __name__ == "__main__":
    print("\n========================================")
    print("  AI Traffic Light — AI Engine")
    print("========================================")
    print(f"  Flask Server:  http://0.0.0.0:{FLASK_PORT}")
    print(f"  MQTT Broker:   {MQTT_BROKER}:{MQTT_PORT}")
    print(f"  Save Frames:   {SAVE_FRAMES}")
    print("========================================\n")

    # Connect MQTT (non-blocking)
    connect_mqtt()

    # Start Flask
    app.run(host="0.0.0.0", port=FLASK_PORT, debug=False)
