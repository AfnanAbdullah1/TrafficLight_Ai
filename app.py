"""
AI Traffic Signal System — app.py
Runs on your laptop. Controls ESP32 via WiFi.
Integrated with YOLOv8 for Traffic Density and Accident Detection
Start: python app.py
Open:  http://localhost:5000
"""

import time
import threading
import socket
import requests
import cv2
import numpy as np
from flask import Flask, render_template, request, jsonify, Response

try:
    from ultralytics import YOLO
    # Load the custom YOLO model
    model = YOLO("models/best.pt")
    print("✅ Custom YOLOv8 Model loaded successfully.")
except Exception as e:
    print(f"⚠️ Error loading YOLO model: {e}")
    model = None

app = Flask(__name__)

# ══════════════════════════════════════════════
# mDNS HOSTNAMES (fixed — survive IP changes on new hotspot)
# ══════════════════════════════════════════════
DEFAULT_ESP_HOST = "traffic-esp.local"
DEFAULT_CAM_HOSTS = {
    "lane1": "cam-lane1.local",
    "lane2": "cam-lane2.local",
    "lane3": "cam-lane3.local",
}


def _normalize_host(raw: str) -> str:
    """Accept hostname, IP, or pasted URL; return host part only."""
    s = (raw or "").strip()
    if not s:
        return ""
    s = s.replace("http://", "").replace("https://", "")
    s = s.split("/")[0].strip()
    # Strip :port (not IPv6)
    if s.count(":") == 1:
        host, _, port = s.partition(":")
        if port.isdigit():
            s = host
    return s


def _resolve_host(host: str) -> str:
    """Resolve mDNS/hostname to IPv4 for OpenCV and HTTP. IPs pass through."""
    host = _normalize_host(host)
    if not host:
        return ""
    try:
        socket.inet_aton(host)
        return host
    except OSError:
        pass
    try:
        infos = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
        if infos:
            return infos[0][4][0]
    except OSError:
        pass
    return host


# ══════════════════════════════════════════════
# SHARED STATE (Memory accessible by all threads)
# ══════════════════════════════════════════════
# Because Flask and background threads run simultaneously, they need a safe way
# to share data. We use a "Lock" to prevent two threads from modifying variables
# at the exact same time, which would cause a crash.
_lock = threading.Lock()

_state = {
    "system_on":        True,
    "mode":             "sequence",   # sequence | manual
    "active_lane":      "lane1",
    "timer":            0,
    "emergency_active": False,
    "emergency_lane":   None,
    "esp32_ip":         DEFAULT_ESP_HOST,
    "wifi_connected":   False,
    "signals": {
        "lane1": "RED",
        "lane2": "RED",
        "lane3": "RED",
    },
    "timings": {
        "lane1": 5,
        "lane2": 5,
        "lane3": 5,
    },
    "cam_ips": {
        "lane1": DEFAULT_CAM_HOSTS["lane1"],
        "lane2": DEFAULT_CAM_HOSTS["lane2"],
        "lane3": DEFAULT_CAM_HOSTS["lane3"],
    },
    "ai_counts": {
        "lane1": "None",
        "lane2": "None",
        "lane3": "None",
    },
    "sensor_counts": {
        "lane1": 0,
        "lane2": 0,
        "lane3": 0,
    }
}

# Stores the latest encoded JPEG frame for streaming per lane
_latest_frames = {
    "lane1": None,
    "lane2": None,
    "lane3": None
}

def get(key):
    with _lock:
        return _state[key]


def gets(*keys):
    with _lock:
        return tuple(_state[k] for k in keys)


def _set(key, val):
    """Internal set — caller must NOT hold the lock."""
    with _lock:
        _state[key] = val


# ══════════════════════════════════════════════
# ESP32 COMMUNICATION (Hardware Control)
# ══════════════════════════════════════════════
# This section contains the functions that talk to the physical traffic pole.
# We use standard HTTP requests (like visiting a website) to send commands to the ESP32.

def _esp32_post_signal(signals: dict, host: str):
    """Send signal dict to ESP32. Fire-and-forget."""
    addr = _resolve_host(host)
    if not addr:
        return
    for attempt in range(2):
        try:
            requests.post(f"http://{addr}/signal",
                          json=signals, timeout=3.5)
            break
        except Exception as e:
            if attempt == 1:
                print(f"⚠️ [WARNING] Could not send signal to ESP32 at {addr}: {e}")


def _esp32_check(host: str):
    """Return (wifi_connected, hardware_system_on, sensor_counts) from ESP32."""
    addr = _resolve_host(host)
    if not addr:
        return False, True, None
    try:
        r = requests.get(f"http://{addr}/status", timeout=3.5)
        if r.status_code == 200:
            data = r.json()
            sensors = {
                "lane1": data.get("sensor_lane1", 0),
                "lane2": data.get("sensor_lane2", 0),
                "lane3": data.get("sensor_lane3", 0),
            }
            return data.get("wifi") == "connected", data.get("hardware_system_on", True), sensors
    except Exception:
        pass
    return False, True, None


# ══════════════════════════════════════════════
# HELPER — apply signals and push to ESP32
# ══════════════════════════════════════════════
def _apply(signals: dict, active: str, timer: int):
    """Write signals into state and push to ESP32 (lock acquired internally)."""
    with _lock:
        _state["signals"].update(signals)
        _state["active_lane"] = active
        _state["timer"] = timer
        ip = _state["esp32_ip"]
    _esp32_post_signal(signals, ip)


# ══════════════════════════════════════════════
# AI VIDEO PROCESSING WORKER (The "Eyes" of the System)
# ══════════════════════════════════════════════
# This function runs continuously in the background for each camera (Lane 1, 2, 3).
# It grabs live video frames, feeds them to the YOLOv8 AI, counts the cars,
# checks for accidents, and prepares the video to be shown on the dashboard.
def _ai_worker(lane):
    while True:
        with _lock:
            cam_ip = _state["cam_ips"][lane]
        
        if not cam_ip:
            time.sleep(1)
            continue

        cam_addr = _resolve_host(cam_ip)
        if not cam_addr:
            time.sleep(2)
            continue

        # Standard ESP32-CAM MJPEG stream URL
        stream_url = f"http://{cam_addr}:81/stream"
        
        try:
            res = requests.get(stream_url, stream=True, timeout=(5, 10))
            if res.status_code != 200:
                print(f"⚠️ [WARNING] Failed to connect to camera on {lane} at {stream_url}")
                time.sleep(2)
                continue
                
            bytes_data = b''
            for chunk in res.iter_content(chunk_size=4096):
                with _lock:
                    if _state["cam_ips"][lane] != cam_ip:
                        break
                        
                bytes_data += chunk
                a = bytes_data.find(b'\xff\xd8')
                b = bytes_data.find(b'\xff\xd9')
                if a != -1 and b != -1:
                    jpg = bytes_data[a:b+2]
                    bytes_data = bytes_data[b+2:]
                    
                    frame = cv2.imdecode(np.frombuffer(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                    if frame is None:
                        continue
                        
                    best_class = "None"
                    priority = -1
                    annotated_frame = frame
                    
                    if model:
                        # Run YOLO Inference
                        results = model(frame, verbose=False)
                        
                        if len(results) > 0:
                            for box in results[0].boxes:
                                cls_id = int(box.cls[0])
                                cls_name = model.names[cls_id].lower()
                                
                                # Prioritize: Accident > Three > Two > One
                                p = 0
                                if "accident" in cls_name or "acciedent" in cls_name:
                                    p = 4
                                elif "three" in cls_name:
                                    p = 3
                                elif "two" in cls_name:
                                    p = 2
                                elif "one" in cls_name:
                                    p = 1
                                else:
                                    p = 0 # unknown class
                                    
                                if p > priority:
                                    priority = p
                                    best_class = cls_name
                            
                            # Annotate frame
                            annotated_frame = results[0].plot()
                    
                    # Update state
                    with _lock:
                        _state["ai_counts"][lane] = best_class
                        
                        # Automatically trigger emergency if an accident is detected
                        if priority == 4 and not _state["emergency_active"]:
                            _state["emergency_active"] = True
                            _state["emergency_lane"] = "all_red"
                            _state["active_lane"] = "none"
                            sigs = {"lane1": "RED", "lane2": "RED", "lane3": "RED"}
                            _state["signals"].update(sigs)
                            esp_ip = _state["esp32_ip"]
                            
                            print(f"🚨 ACCIDENT DETECTED ON {lane.upper()}! Triggering All Red Emergency.")
                            threading.Thread(target=_esp32_post_signal, args=(sigs, esp_ip)).start()
                    
                    # Encode frame for web streaming
                    ret_jpg, jpeg = cv2.imencode('.jpg', annotated_frame)
                    if ret_jpg:
                        _latest_frames[lane] = jpeg.tobytes()
        except Exception as e:
            print(f"⚠️ [WARNING] Stream error on {lane}: {e}")
            time.sleep(2)

# Start an AI worker for each lane
for l in ["lane1", "lane2", "lane3"]:
    threading.Thread(target=_ai_worker, args=(l,), daemon=True).start()


# ══════════════════════════════════════════════
# SEQUENCE WORKER THREAD (The "Traffic Cop")
# ══════════════════════════════════════════════
# Cycles the Green light through Lane 1 → Lane 2 → Lane 3 automatically.
# It looks at the AI's traffic count to decide if the Green light should be 
# 5 seconds, 7 seconds, or 10 seconds.
# It also handles the Yellow transition and Red clearance times.

def _sequence_worker():
    lanes = ["lane1", "lane2", "lane3"]
    idx = 0

    while True:
        # ── Gate ────────────────────────────
        with _lock:
            sys_on = _state["system_on"]
            mode   = _state["mode"]
            emg    = _state["emergency_active"]

        if not sys_on or mode != "sequence" or emg:
            time.sleep(0.1)
            continue

        lane = lanes[idx]

        # ── PREPARE TO GO (YELLOW) ──────────
        sigs = {l: ("YELLOW" if l == lane else "RED") for l in lanes}
        _apply(sigs, lane, 2)

        interrupted = False
        while True:
            time.sleep(1)
            with _lock:
                if not _state["system_on"] or _state["mode"] != "sequence" or _state["emergency_active"]:
                    interrupted = True
                    break
                _state["timer"] -= 1
                if _state["timer"] <= 0:
                    break
        if interrupted:
            continue

        # ── GREEN (Dynamic Duration) ────────
        with _lock:
            ai_cls = _state["ai_counts"][lane].lower()
            sensor_count = _state["sensor_counts"][lane]
            
            # Calculate dynamic timing based on AI detection
            if "three" in ai_cls:
                green_dur = 10
            elif "two" in ai_cls:
                green_dur = 7
            elif "one" in ai_cls:
                green_dur = 5
            elif ai_cls == "none":
                # Fallback to Sensor counts when AI cameras are offline
                if sensor_count >= 4:
                    green_dur = 10
                elif sensor_count >= 1:
                    green_dur = 7
                else:
                    green_dur = _state["timings"][lane]
            else:
                # Fallback to default timing
                green_dur = _state["timings"][lane]

        sigs = {l: ("GREEN" if l == lane else "RED") for l in lanes}
        _apply(sigs, lane, green_dur)

        interrupted = False
        while True:
            time.sleep(1)
            with _lock:
                if not _state["system_on"] or _state["mode"] != "sequence" or _state["emergency_active"]:
                    interrupted = True
                    break
                _state["timer"] -= 1
                if _state["timer"] <= 0:
                    break
        if interrupted:
            continue

        # ── YELLOW ──────────────────────────
        sigs = {l: ("YELLOW" if l == lane else "RED") for l in lanes}
        _apply(sigs, lane, 2)

        while True:
            time.sleep(1)
            with _lock:
                if not _state["system_on"] or _state["mode"] != "sequence" or _state["emergency_active"]:
                    interrupted = True
                    break
                _state["timer"] -= 1
                if _state["timer"] <= 0:
                    break
        if interrupted:
            continue

        # ── RED / clearance ──────────────────
        sigs = {l: "RED" for l in lanes}
        _apply(sigs, lane, 3)

        while True:
            time.sleep(1)
            with _lock:
                if not _state["system_on"] or _state["mode"] != "sequence" or _state["emergency_active"]:
                    interrupted = True
                    break
                _state["timer"] -= 1
                if _state["timer"] <= 0:
                    break
        if interrupted:
            continue

        idx = (idx + 1) % len(lanes)


# ══════════════════════════════════════════════
# ESP32 STATUS POLLER THREAD
# Checks every 3 seconds
# ══════════════════════════════════════════════

def _esp32_poller():
    while True:
        with _lock:
            ip = _state["esp32_ip"]
        ok, hw_on, sensors = _esp32_check(ip)
        with _lock:
            _state["wifi_connected"] = ok
            if sensors is not None:
                _state["sensor_counts"].update(sensors)
        time.sleep(3)


threading.Thread(target=_sequence_worker, daemon=True).start()
threading.Thread(target=_esp32_poller,    daemon=True).start()


# ══════════════════════════════════════════════
# FLASK ROUTES
# ══════════════════════════════════════════════

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/status")
def status():
    with _lock:
        s = _state.copy()
        s["signals"] = _state["signals"].copy()
        s["timings"] = _state["timings"].copy()
        s["cam_ips"] = _state["cam_ips"].copy()
        s["ai_counts"] = _state["ai_counts"].copy()
        s["sensor_counts"] = _state["sensor_counts"].copy()

    if not s["system_on"]:
        msg = "System is OFF (All Red)"
    elif s["emergency_active"]:
        if s["emergency_lane"] == "all_red":
            msg = "🚨 EMERGENCY — ALL RED"
        else:
            msg = f"🚨 EMERGENCY — {s['emergency_lane'].upper()} is GREEN"
    elif s["mode"] == "manual":
        msg = "Manual Mode Active"
    else:
        msg = f"{s['active_lane'].upper()} active — {s['timer']}s remaining"

    s["status_message"] = msg
    return jsonify(s)


@app.route("/connect", methods=["POST"])
def connect():
    raw = (request.json or {}).get("ip", "").strip()
    host = _normalize_host(raw) or DEFAULT_ESP_HOST
    with _lock:
        _state["esp32_ip"] = host
        _state["wifi_connected"] = False
    ok, hw_on, sensors = _esp32_check(host)
    with _lock:
        _state["wifi_connected"] = ok
        if sensors is not None:
            _state["sensor_counts"].update(sensors)
    return jsonify({
        "success": True,
        "connected": ok,
        "host": host,
        "resolved_ip": _resolve_host(host) if ok else "",
    })


@app.route("/connect_all", methods=["POST"])
def connect_all():
    """Connect traffic ESP32 and all three cameras using saved hostnames."""
    data = request.json or {}
    esp_host = _normalize_host(data.get("esp_ip", "")) or DEFAULT_ESP_HOST
    cam_hosts = {}
    for lane in ("lane1", "lane2", "lane3"):
        key = f"cam_{lane}"
        raw = data.get(key, "")
        cam_hosts[lane] = _normalize_host(raw) or DEFAULT_CAM_HOSTS[lane]

    with _lock:
        _state["esp32_ip"] = esp_host
        _state["wifi_connected"] = False
        for lane, h in cam_hosts.items():
            _state["cam_ips"][lane] = h

    esp_ok, hw_on, sensors = _esp32_check(esp_host)
    cam_status = {}
    for lane, h in cam_hosts.items():
        addr = _resolve_host(h)
        cam_status[lane] = bool(addr)

    with _lock:
        _state["wifi_connected"] = esp_ok
        if sensors is not None:
            _state["sensor_counts"].update(sensors)

    return jsonify({
        "success": True,
        "esp_connected": esp_ok,
        "esp_host": esp_host,
        "esp_resolved_ip": _resolve_host(esp_host) if esp_ok else "",
        "cameras": cam_status,
    })


@app.route("/set_cam_ip", methods=["POST"])
def set_cam_ip():
    data = request.json or {}
    lane = data.get("lane", "")
    host = _normalize_host(data.get("ip", ""))

    if lane in ("lane1", "lane2", "lane3"):
        with _lock:
            _state["cam_ips"][lane] = host
    return jsonify({
        "success": True,
        "host": host,
        "resolved_ip": _resolve_host(host) if host else "",
    })


@app.route("/set_mode", methods=["POST"])
def set_mode():
    mode = (request.json or {}).get("mode", "")
    if mode in ("sequence", "manual"):
        with _lock:
            _state["mode"] = mode
    return jsonify({"success": True})


@app.route("/set_timing", methods=["POST"])
def set_timing():
    data   = request.json or {}
    preset = data.get("preset", "")
    with _lock:
        if preset in ("default", "equal"):
            _state["timings"] = {"lane1": 5, "lane2": 5, "lane3": 5}
        elif preset == "custom":
            for l in ("lane1", "lane2", "lane3"):
                v = data.get(l)
                if v is not None:
                    _state["timings"][l] = max(1, int(v))
    return jsonify({"success": True})


@app.route("/manual_signal", methods=["POST"])
def manual_signal():
    data   = request.json or {}
    lane   = data.get("lane", "")
    signal = data.get("signal", "")
    lanes  = ["lane1", "lane2", "lane3"]

    with _lock:
        if _state["mode"] != "manual":
            return jsonify({"success": False, "reason": "not in manual mode"})
        if _state["emergency_active"]:
            return jsonify({"success": False, "reason": "emergency active"})
        if lane not in lanes or signal not in ("GREEN", "YELLOW", "RED"):
            return jsonify({"success": False, "reason": "invalid"})

        if signal == "GREEN":
            for l in lanes:
                _state["signals"][l] = "GREEN" if l == lane else "RED"
        else:
            _state["signals"][lane] = signal

        _state["active_lane"] = lane
        ip  = _state["esp32_ip"]
        sig = _state["signals"].copy()

    _esp32_post_signal(sig, ip)
    return jsonify({"success": True})


@app.route("/adjust_timing", methods=["POST"])
def adjust_timing():
    data = request.json or {}
    lane = data.get("lane", "")
    secs = data.get("seconds", 5)
    if lane in ("lane1", "lane2", "lane3"):
        with _lock:
            _state["timings"][lane] = max(1, int(secs))
    return jsonify({"success": True})


@app.route("/emergency", methods=["POST"])
def emergency():
    lane  = (request.json or {}).get("lane", "")
    lanes = ["lane1", "lane2", "lane3"]

    if lane == "all_red":
        sigs = {l: "RED" for l in lanes}
        with _lock:
            _state["emergency_active"] = True
            _state["emergency_lane"]   = "all_red"
            _state["active_lane"]      = "none"
            _state["signals"].update(sigs)
            ip = _state["esp32_ip"]
        _esp32_post_signal(sigs, ip)
        return jsonify({"success": True})

    if lane not in lanes:
        return jsonify({"success": False})

    sigs = {l: ("GREEN" if l == lane else "RED") for l in lanes}
    with _lock:
        _state["emergency_active"] = True
        _state["emergency_lane"]   = lane
        _state["active_lane"]      = lane
        _state["signals"].update(sigs)
        ip = _state["esp32_ip"]

    _esp32_post_signal(sigs, ip)
    return jsonify({"success": True})


@app.route("/clear_emergency", methods=["POST"])
def clear_emergency():
    with _lock:
        _state["emergency_active"] = False
        _state["emergency_lane"]   = None
    return jsonify({"success": True})


@app.route("/reset_sensor", methods=["POST"])
def reset_sensor():
    """Forward Ultrasonic counter reset to ESP32 and clear local state."""
    with _lock:
        ip = _state["esp32_ip"]
        _state["sensor_counts"] = {"lane1": 0, "lane2": 0, "lane3": 0}
    addr = _resolve_host(ip)
    if addr:
        try:
            requests.post(f"http://{addr}/reset_counts", timeout=3.5)
        except Exception:
            pass
    return jsonify({"success": True})


@app.route("/system_power", methods=["POST"])
def system_power():
    on = (request.json or {}).get("on", True)
    with _lock:
        _state["system_on"] = on
        if not on:
            sigs = {"lane1": "RED", "lane2": "RED", "lane3": "RED"}
            _state["signals"].update(sigs)
            _state["active_lane"] = "none"
            ip = _state["esp32_ip"]
        else:
            ip = None
    if not on and ip:
        _esp32_post_signal(sigs, ip)
    return jsonify({"success": True})


@app.route("/add_time", methods=["POST"])
def add_time():
    secs = (request.json or {}).get("seconds", 5)
    with _lock:
        if _state["mode"] == "sequence" and not _state["emergency_active"] and _state["system_on"]:
            _state["timer"] += secs
    return jsonify({"success": True})

# ══════════════════════════════════════════════
# MJPEG STREAMING ROUTES
# ══════════════════════════════════════════════
def generate_frames(lane):
    while True:
        frame = _latest_frames.get(lane)
        if frame is not None:
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
        else:
            # If no frame yet, yield a tiny placeholder or just sleep
            time.sleep(0.1)

@app.route("/video_feed/<lane>")
def video_feed(lane):
    if lane not in ("lane1", "lane2", "lane3"):
        return "Invalid lane", 400
    return Response(generate_frames(lane), mimetype='multipart/x-mixed-replace; boundary=frame')

# ══════════════════════════════════════════════
# STARTUP
# ══════════════════════════════════════════════
def _local_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


if __name__ == "__main__":
    ip = _local_ip()
    print("\n" + "═" * 42)
    print("   AI Traffic Signal System")
    print("═" * 42)
    print(f"   Local  →  http://localhost:5000")
    print(f"   Phone  →  http://{ip}:5000")
    print("─" * 42)
    print("   mDNS devices (set once, same on any hotspot):")
    print(f"   ESP32      →  {DEFAULT_ESP_HOST}")
    for lane, h in DEFAULT_CAM_HOSTS.items():
        print(f"   {lane:8}  →  {h}")
    print("═" * 42 + "\n")
    app.run(host="0.0.0.0", port=5000,
            debug=False, use_reloader=False, threaded=True)