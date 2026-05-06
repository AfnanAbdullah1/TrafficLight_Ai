# 🚦 AI Hybrid Traffic Lights Control System

A dynamic, real-time traffic management system using ESP32-CAM modules, AI-based vehicle detection, and a web dashboard for remote phone control.

---

## 🏗️ Architecture: Hybrid Approach

```
                         YOUR PC / LAPTOP (Brain)
                ┌──────────────────────────────────────────┐
                │  Node.js Server  ←→  MQTT  ←→  Dashboard │
                │  Python AI (YOLOv8) pulls frames from ──────┐
                └───────────────┬──────────────────────────┘  │
                                │                              │
                          WiFi / MQTT                    HTTP GET /capture
                                │                              │
          ┌─────────────────────┼─────────────────────┐        │
          │                     │                     │        │
     ┌────▼─────┐         ┌────▼─────┐         ┌────▼──────┐ │
     │ ESP32-CAM │         │ ESP32-CAM │         │ ESP32-CAM │◄┘
     │ Route 1   │         │ Route 2   │         │ Route 3   │
     │ 📷 Only   │         │ 📷 Only   │         │ 📷 Only   │
     └───────────┘         └───────────┘         └───────────┘
            Stock CameraWebServer firmware (untouched)

                          ┌──────────────┐
                          │ ESP32 WROOM   │
                          │ MASTER 🎛️    │
                          │              │
                          │ 3× LED Mods  │
                          │ 3× PIR       │
                          │ 2× Ultrasonic│
                          │ MQTT Client  │
                          └──────────────┘
```

### Why Hybrid?
- **ESP32-CAMs** run the proven, official Espressif CameraWebServer — rock-solid camera performance
- **ESP32 WROOM** has plenty of GPIO pins to control all LEDs and read all sensors
- **No GPIO conflicts** — ESP32-CAM has very limited safe pins; WROOM has 20+
- **Clean separation** — cameras do camera stuff, controller does control stuff

---

## 📁 Project Structure

```
TrafficLight_Ai/
├── firmware/
│   ├── esp32cam/CameraWebServer/      # Stock Espressif camera firmware
│   │   ├── CameraWebServer.ino        # Just change WiFi SSID/password
│   │   ├── app_httpd.cpp              # HTTP server (DO NOT MODIFY)
│   │   ├── camera_pins.h              # Pin definitions for all boards
│   │   ├── board_config.h             # Board selector (AI_THINKER set)
│   │   └── camera_index.h            # Embedded web UI
│   │
│   └── esp32_wroom_master/            # Master controller
│       └── esp32_wroom_master.ino     # ALL LEDs + PIR + ultrasonic + MQTT
│
├── server/                            # Node.js backend
│   ├── server.js                      # Express + Socket.IO + MQTT
│   ├── trafficController.js           # State machine & logic
│   ├── mqttHandler.js                 # MQTT bridge
│   └── package.json
│
├── dashboard/                         # Web frontend
│   ├── index.html                     # Mobile-first dashboard
│   ├── css/style.css                  # Dark theme
│   └── js/app.js                      # WebSocket client
│
├── ai_engine/                         # Python AI
│   ├── image_server.py                # Pulls frames from cameras + YOLO
│   ├── vehicle_detector.py            # YOLOv8 vehicle counting
│   └── requirements.txt
│
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- **Node.js** v18+ — [nodejs.org](https://nodejs.org/)
- **Python** 3.10+ — [python.org](https://python.org/)
- **Mosquitto** MQTT Broker — [mosquitto.org](https://mosquitto.org/download/)
- **Arduino IDE** — For ESP32 firmware upload

### Step 1: MQTT Broker
```powershell
# Install via Chocolatey
choco install mosquitto
net start mosquitto
```

### Step 2: Node.js Server
```powershell
cd server
npm install
npm start
# Dashboard at http://localhost:3000
```

### Step 3: Python AI Engine
```powershell
cd ai_engine
pip install -r requirements.txt
# Set camera IPs before starting:
set CAM1_IP=192.168.1.201
set CAM2_IP=192.168.1.202
set CAM3_IP=192.168.1.203
python image_server.py
```

### Step 4: Flash ESP32-CAMs (×3)
1. Open `firmware/esp32cam/CameraWebServer/CameraWebServer.ino`
2. Change WiFi credentials on lines 12-13
3. Board: **AI Thinker ESP32-CAM** | Partition: **Huge APP (3MB)**
4. Upload to each ESP32-CAM
5. Note each camera's IP from Serial Monitor

### Step 5: Flash ESP32 WROOM
1. Open `firmware/esp32_wroom_master/esp32_wroom_master.ino`
2. Change WiFi credentials + PC IP at the top
3. Board: **ESP32 Dev Module**
4. Upload

### Step 6: Phone Access
```
Connect phone to same WiFi → http://<PC-IP>:3000
```

---

## ⚡ WROOM Pin Assignment

### Traffic LEDs (9 pins)
| Route | Red | Yellow | Green |
|-------|-----|--------|-------|
| Route 1 | GPIO 4 | GPIO 16 | GPIO 17 |
| Route 2 | GPIO 5 | GPIO 18 | GPIO 19 |
| Route 3 | GPIO 13 | GPIO 14 | GPIO 27 |

### PIR Sensors (3 pins)
| Sensor | GPIO |
|--------|------|
| PIR Route 1 | GPIO 25 |
| PIR Route 2 | GPIO 26 |
| PIR Route 3 | GPIO 33 |

### Ultrasonic Sensors (4 pins)
| Sensor | TRIG | ECHO |
|--------|------|------|
| Ultrasonic 1 (Route 1) | GPIO 23 | GPIO 35 (input-only) |
| Ultrasonic 2 (Route 2) | GPIO 32 | GPIO 34 (input-only) |

### Other
| Pin | Purpose |
|-----|---------|
| GPIO 2 | Status LED (built-in) |

> ⚠️ Use a **voltage divider** on ultrasonic ECHO pins (5V→3.3V)

---

## 📡 MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `traffic/route/{1-3}/command` | Server → WROOM | LED commands (red/yellow/green) |
| `traffic/route/{1-3}/status` | WROOM → Server | Current LED state |
| `traffic/mode` | Server → WROOM | Mode (auto/manual/emergency) |
| `traffic/emergency` | Server → WROOM | Emergency override |
| `traffic/density/route{1-3}` | AI → Server | Vehicle density from camera |
| `traffic/vehicle_count/{1-2}` | WROOM → Server | Ultrasonic vehicle counts |
| `traffic/pedestrian/{1-3}` | WROOM → Server | PIR detections |
| `traffic/master/status` | WROOM → Server | Master device status |

---

## 🎮 Features

| Feature | Status | Implementation |
|---------|--------|---------------|
| WiFi connectivity | ✅ | All ESP32s connect to local WiFi |
| Manual control from phone | ✅ | Dashboard → WebSocket → MQTT → WROOM |
| Emergency alert | ✅ | One-tap route clear/block from phone |
| Sequence timing (5s/2s/3s) | ✅ | Server state machine + WROOM fallback |
| Phone dashboard control | ✅ | Responsive web UI at http://\<PC\>:3000 |
| Density-based adaptive timing | ✅ | AI pulls camera frames → YOLO → MQTT |
| Cloud streaming (add-on) | 🔜 | ngrok + camera MJPEG stream |
| IR sensor counting (add-on) | 🔜 | Replace ultrasonic with IR |
