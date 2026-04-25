# 🚦 AI Hybrid Traffic Lights Control System

A dynamic, real-time traffic management system using ESP32-CAM modules, AI-based vehicle detection, and a web dashboard for remote control.

---

## 📁 Project Structure

```
TrafficLight_Ai/
├── firmware/                          # ESP32 Arduino code
│   ├── esp32cam_route/                # ESP32-CAM firmware (shared for all 3 routes)
│   │   └── esp32cam_route.ino         # Change ROUTE_ID per board (1, 2, 3)
│   └── esp32_wroom_master/            # ESP32 WROOM coordinator
│       └── esp32_wroom_master.ino     # Ultrasonic sensors + coordination
│
├── server/                            # Node.js backend
│   ├── server.js                      # Main server (Express + Socket.IO + MQTT)
│   ├── trafficController.js           # Traffic light state machine & logic
│   ├── mqttHandler.js                 # MQTT bridge to ESP32 devices
│   └── package.json
│
├── dashboard/                         # Web frontend (served by Node.js)
│   ├── index.html                     # Dashboard page
│   ├── css/style.css                  # Premium dark theme
│   └── js/app.js                      # WebSocket client & UI logic
│
├── ai_engine/                         # Python AI processing
│   ├── image_server.py                # Flask server for ESP32-CAM frames
│   ├── vehicle_detector.py            # YOLOv8 vehicle counting
│   └── requirements.txt
│
└── README.md
```

---

## 🚀 Quick Start

### Prerequisites
- **Node.js** v18+ — [Download](https://nodejs.org/)
- **Python** 3.10+ — [Download](https://python.org/)
- **Mosquitto MQTT Broker** — [Download](https://mosquitto.org/download/)
- **Arduino IDE** or **PlatformIO** — For ESP32 firmware upload

### Step 1: Install MQTT Broker
```powershell
# Windows (via Chocolatey)
choco install mosquitto

# Or download from https://mosquitto.org/download/
# Start the broker:
net start mosquitto
```

### Step 2: Start Node.js Server
```powershell
cd server
npm install
npm start
```
Dashboard will be available at: **http://localhost:3000**

### Step 3: Start AI Engine
```powershell
cd ai_engine
pip install -r requirements.txt
python image_server.py
```
AI Engine runs at: **http://localhost:5000**

### Step 4: Flash ESP32 Firmware
1. Open `firmware/esp32cam_route/esp32cam_route.ino` in Arduino IDE
2. **Update** WiFi credentials and PC IP address at the top of the file
3. **Change `ROUTE_ID`** for each ESP32-CAM (1, 2, or 3)
4. Select board: **AI Thinker ESP32-CAM**
5. Upload to each ESP32-CAM

6. Open `firmware/esp32_wroom_master/esp32_wroom_master.ino`
7. Update WiFi credentials and PC IP
8. Select board: **ESP32 Dev Module**
9. Upload to ESP32 WROOM

### Step 5: Access Dashboard from Phone
1. Connect phone to **same WiFi** as PC
2. Open browser → `http://<YOUR-PC-IP>:3000`
3. Control traffic lights from your phone!

---

## 🎮 Features

| Feature | Status |
|---------|--------|
| WiFi connectivity | ✅ |
| Manual control from phone | ✅ |
| Emergency alert (open/block routes) | ✅ |
| Sequence timing (5s/2s/3s) | ✅ |
| Phone dashboard control | ✅ |
| Density-based adaptive timing | ✅ |
| Cloud streaming (add-on) | 🔜 |
| IR sensor counting (add-on) | 🔜 |

---

## 📱 Dashboard Controls

- **Auto Mode** — Cycles through routes automatically (5s green, 2s yellow, 3s red gap)
- **Manual Mode** — Control each route's light from your phone
- **Emergency Mode** — Force any route green, all others red
- **Timing Sliders** — Adjust green duration per route (1–60 seconds)
- **System Log** — Live event feed

---

## ⚙️ Configuration

### WiFi & Server IP
Edit these values in **both** firmware files:
```cpp
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD  = "YOUR_WIFI_PASSWORD";
const char* MQTT_SERVER    = "192.168.1.100";  // Your PC's IP
const char* AI_SERVER_IP   = "192.168.1.100";  // Your PC's IP
```

### Find your PC's IP:
```powershell
ipconfig
# Look for "IPv4 Address" under your WiFi adapter
```

---

## 🏗️ Hardware Wiring

### ESP32-CAM (per route)
| Pin | Connected To |
|-----|-------------|
| GPIO 12 | Red LED |
| GPIO 13 | Yellow LED |
| GPIO 14 | Green LED |
| GPIO 15 | PIR Sensor OUT |

### ESP32 WROOM
| Pin | Connected To |
|-----|-------------|
| GPIO 5 | Ultrasonic 1 TRIG |
| GPIO 18 | Ultrasonic 1 ECHO (via voltage divider) |
| GPIO 19 | Ultrasonic 2 TRIG |
| GPIO 21 | Ultrasonic 2 ECHO (via voltage divider) |

---

## 📡 MQTT Topics

| Topic | Direction | Purpose |
|-------|-----------|---------|
| `traffic/route/{1-3}/command` | Server → ESP32 | LED commands |
| `traffic/route/{1-3}/status` | ESP32 → Server | LED state report |
| `traffic/mode` | Server → All | Mode switching |
| `traffic/emergency` | Server → All | Emergency override |
| `traffic/density/route{1-3}` | AI → Server | Vehicle counts |
| `traffic/vehicle_count/{1-2}` | WROOM → Server | Ultrasonic counts |
| `traffic/pedestrian/{1-3}` | ESP32 → Server | PIR detections |
