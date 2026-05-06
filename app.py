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
    "esp32_ip":         "",
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
        "lane1": "",
        "lane2": "",
        "lane3": "",
    },
    "ai_counts": {
        "lane1": "None",
        "lane2": "None",
        "lane3": "None",
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

def _esp32_post_signal(signals: dict, ip: str):
    """Send signal dict to ESP32. Fire-and-forget."""
    if not ip:
        return
    for _ in range(2):
        try:
            requests.post(f"http://{ip}/signal",
                          json=signals, timeout=3.5)
            break
        except Exception:
            pass


def _esp32_check(ip: str):
    """Return (wifi_connected, hardware_system_on) from ESP32."""
    if not ip:
        return False, True
    try:
        r = requests.get(f"http://{ip}/status", timeout=3.5)
        if r.status_code == 200:
            data = r.json()
            return data.get("wifi") == "connected", data.get("hardware_system_on", True)
    except Exception:
        pass
    return False, True


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
            
        # Standard ESP32-CAM MJPEG stream URL
        stream_url = f"http://{cam_ip}:81/stream"
        cap = cv2.VideoCapture(stream_url)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        
        if not cap.isOpened():
            print(f"⚠️ [WARNING] Failed to connect to camera on {lane} at {stream_url}")
            time.sleep(2)
            continue
            
        while True:
            with _lock:
                # Break if IP was changed or removed
                if _state["cam_ips"][lane] != cam_ip:
                    break
            
            ret, frame = cap.read()
            if not ret:
                break
                
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
                
        cap.release()

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

        # ── GREEN (Dynamic Duration) ────────
        with _lock:
            ai_cls = _state["ai_counts"][lane].lower()
            
            # Calculate dynamic timing based on AI detection
            if "three" in ai_cls:
                green_dur = 10
            elif "two" in ai_cls:
                green_dur = 7
            elif "one" in ai_cls:
                green_dur = 5
            else:
                # Fallback to default timing if nothing detected or no camera
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
        ok, hw_on = _esp32_check(ip)
        with _lock:
            _state["wifi_connected"] = ok
            if ok:
                _state["system_on"] = hw_on
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
    ip = (request.json or {}).get("ip", "").strip()
    with _lock:
        _state["esp32_ip"] = ip
        _state["wifi_connected"] = False
    ok, hw_on = _esp32_check(ip)
    with _lock:
        _state["wifi_connected"] = ok
        if ok:
            _state["system_on"] = hw_on
    return jsonify({"success": True, "connected": ok})


@app.route("/set_cam_ip", methods=["POST"])
def set_cam_ip():
    data = request.json or {}
    lane = data.get("lane", "")
    ip = data.get("ip", "").strip()
    
    # Clean up the IP in case the user pasted "http://10.x.x.x" by mistake
    ip = ip.replace("http://", "").replace("https://", "")
    if "/" in ip:
        ip = ip.split("/")[0]
        
    if lane in ("lane1", "lane2", "lane3"):
        with _lock:
            _state["cam_ips"][lane] = ip
    return jsonify({"success": True})


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
    print("═" * 42 + "\n")
    app.run(host="0.0.0.0", port=5000,
            debug=False, use_reloader=False, threaded=True)