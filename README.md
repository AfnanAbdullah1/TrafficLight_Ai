# 🚦 AI Smart Traffic Light Control System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web%20Server-green?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![YOLOv8](https://img.shields.io/badge/AI-YOLOv8-cyan?style=for-the-badge&logo=yolo&logoColor=black)](https://docs.ultralytics.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-orange?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![ESP32](https://img.shields.io/badge/IoT-ESP32%20%26%20ESP32--CAM-red?style=for-the-badge&logo=espressif&logoColor=white)](https://www.espressif.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

> A smart, hybrid traffic management system that uses **YOLOv8 AI cameras** and **hardware ultrasonic sensors** to detect traffic density in real time, dynamically give more green light time to busy lanes, and automatically turn all lights **RED** if an accident happens.

---

## 📸 Project Gallery

| 🖥️ Live Web Dashboard | 🛠️ Hardware Setup & Model |
| :---: | :---: |
| ![Dashboard Preview](Images/dashboard_preview.png) | ![Hardware Setup](Images/HardwareDesign.jpeg) |
| *Real-time video feeds, AI car counts & signal controls* | *3-lane physical intersection with ESP32 & LEDs* |

*(Drop `dashboard_preview.png` into [`Images/`](Images/) to show your web dashboard screenshot)*

---

## 💡 What is this Project?

Normal traffic lights change on rigid, fixed timers. Even when a road is completely empty, it stays green while busy lanes stay stuck in traffic.

**This project solves that using Dual-Layer Sensing (AI Vision + Ultrasonic Telemetry):**
- **👀 AI Cameras (Lane Eyes):** 3 ESP32-CAMs stream live video of each lane to a central laptop.
- **🧠 YOLOv8 AI (Brain):** Detects vehicle density and classifies cars in real time.
- **📡 Ultrasonic Proximity Sensors (Physical Verification):** HC-SR04 sensors measure vehicle distance at each lane entrance to count cars physically.
- **⏱️ Dynamic Green Light Timing:**
  - **1 Car:** 5 seconds green
  - **2 Cars:** 7 seconds green
  - **3+ Cars (Heavy Traffic):** 10 seconds green
- **🚨 Instant Accident Safety:** If a crash happens, the AI immediately trips an **All-Red safety stop** across all lanes to protect motorists.
- **📶 No IP Address Hassle:** Uses **mDNS** hostnames (`traffic-esp.local`, `cam-lane1.local`), so you never need to copy-paste new IP addresses when switching Wi-Fi.

---

## 🏗️ System Flow & Architecture

<p align="center">
  <img src="Images/FlowDiagram.jpg" alt="System Flow Diagram" width="100%">
</p>

```
        📷 3x ESP32-CAMs                   💻 Laptop / PC                    🚦 ESP32 Controller
   (Watching 3 Traffic Lanes)           (Running YOLOv8 + Flask)             (Controls 9x LEDs & Sensors)
  ┌──────────────────────────┐         ┌──────────────────────────┐         ┌──────────────────────────┐
  │  cam-lane1.local         │         │   1. Receives video      │         │   1. Changes Red/Yellow/ │
  │  cam-lane2.local         ├────────►│   2. YOLOv8 counts cars  ├────────►│      Green LEDs          │
  │  cam-lane3.local         │  Video  │   3. Calculates green    │  HTTP   │   2. Ultrasonic sensors  │
  └──────────────────────────┘  Stream │      timer (5s / 7s / 10s│ Command │      physically count    │
                                       │   4. Hosts Web Dashboard │         │      incoming cars (<5cm)│
                                       └──────────────────────────┘         │   traffic-esp.local      │
                                                                            └──────────────────────────┘
```

---

## 📡 Ultrasonic Sensors & Dual-Layer Car Counting

In addition to computer vision, the system integrates **3× HC-SR04 ultrasonic distance sensors** directly onto the master ESP32 controller.

### ❓ Why use Ultrasonic Sensors with Cameras?
Cameras can suffer from bad lighting, lens obstructions, or network lags. Ultrasonic sensors provide a **hardware-level second layer of truth**:
- **Sonic Wave Detection:** Emits a 10µs ultrasonic pulse and measures echo reflection time (`Distance = Time × 0.034 / 2 cm`).
- **Proximity Trigger:** When a car gets closer than **5 cm** (`DIST_THRESHOLD`), the sensor registers a vehicle arrival.
- **Smart Anti-Double-Count Logic:** If a car stops in front of the sensor waiting at a red light, a software state latch (`carPresent`) prevents it from repeatedly incrementing. Only after the car drives away does it reset for the next vehicle.
- **Live Telemetry & Dashboard Sync:** Counts are transmitted over Wi-Fi to the Flask dashboard with live color badges:
  - 🔵 **0 Cars:** Low traffic (`sensor-low`)
  - 🟢 **1–3 Cars:** Medium traffic (`sensor-med`)
  - 🟡 **4+ Cars:** High traffic warning (`sensor-high`)
- **Remote Zeroing:** Features a 1-click **"🔄 Reset All Counters"** button on the web dashboard that calls `/reset_sensor` to clear counts both in memory and on the physical ESP32.

```
       HC-SR04 Sensor                      ESP32 WROOM Controller
    ┌──────────────────┐                     ┌──────────────────┐
    │  VCC (5V)        ├─────────────────────┤ 5V (VIN)         │
    │  TRIG (Trigger)  ├─────────────────────┤ GPIO 13 / 14 / 15│
    │  ECHO (Echo)     ├──[ 1kΩ Resistor ]───┤ GPIO 12 / 27 / 32│
    │  GND (Ground)    ├─────────────────────┤ GND              │
    └──────────────────┘                     └──────────────────┘
```

---

## 🛠️ Hardware Specifications

| Component | Qty | Role |
| :--- | :---: | :--- |
| **ESP32 WROOM** | 1 | Master controller — drives 9 signal LEDs & polls ultrasonic sensors |
| **ESP32-CAM (AI-Thinker)** | 3 | Dedicated camera nodes — streams live MJPEG video per lane |
| **Traffic Light Modules** | 3 | Road A (Lane 1), Road B (Lane 2), Road C (Lane 3) LEDs |
| **HC-SR04 Sensors** | 3 | Ultrasonic sensors for physical vehicle presence verification |

### 📌 Wiring Pinout (ESP32 WROOM)

| Lane | 🔴 Red LED | 🟡 Yellow LED | 🟢 Green LED | 📡 Ultrasonic TRIG | 📡 Ultrasonic ECHO |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Lane 1 (Road A)** | GPIO 23 | GPIO 22 | GPIO 21 | **GPIO 13** | **GPIO 12** |
| **Lane 2 (Road B)** | GPIO 19 | GPIO 18 | GPIO 5  | **GPIO 14** | **GPIO 27** |
| **Lane 3 (Road C)** | GPIO 26 | GPIO 25 | GPIO 4  | **GPIO 15** | **GPIO 32** |

> 📖 **Full Hardware Guide:** See [docs/HARDWARE_GUIDE.md](docs/HARDWARE_GUIDE.md) for step-by-step assembly and breadboard diagrams.

---

## 🚀 Quick Start (Run in 3 Steps)

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/AfnanAbdullah1/TrafficLight_Ai.git
cd TrafficLight_Ai

# Create virtual environment (recommended)
python -m venv venv
.\venv\Scripts\activate   # On Windows

# Install required libraries
pip install -r requirements.txt
```

### 2. Set Up Wi-Fi
Open `firmware/wifi_config.h` and write your Wi-Fi or Hotspot name and password:
```cpp
#define WIFI_SSID "YourWiFiName"
#define WIFI_PASS "YourPassword"
```
*(Upload firmware to ESP32 boards using Arduino IDE. Full guide: [docs/MDNS_SETUP.md](docs/MDNS_SETUP.md))*

### 3. Start the System
```bash
python app.py
```
*Or simply double-click `scripts/start_system.bat` on Windows.*

👉 Open your browser at **`http://localhost:5000`** and click **"Connect All"**!

---

## 🎮 Web Dashboard & Controls

The web dashboard allows monitoring and controlling the whole system from any phone, laptop, or tablet:

- **Live Video Feeds:** Shows all 3 lanes with AI bounding boxes.
- **Signal Status:** Shows which lane is currently GREEN, YELLOW, or RED.
- **Ultrasonic Car Counters:** Displays live car counts detected by HC-SR04 sensors with a 1-click reset button.
- **Emergency Button:** Turn all lights RED immediately with one click.
- **Mode Toggle:** Switch between Autonomous Sequence Mode and Manual Signal Override.

### ⌨️ Keyboard Shortcuts
- Press **`1`**, **`2`**, or **`3`** → Force Green on Lane 1, 2, or 3
- Press **`A`** → Switch to Automatic AI Mode
- Press **`M`** → Switch to Manual Mode
- Press **`Esc`** → Clear Emergency and resume normal traffic

---

## 🧠 AI Model Details

- **Model:** Ultralytics YOLOv8 (trained on custom dataset).
- **Classes:**
  1. `OneCar` → Assigns **5 seconds** green
  2. `TwoCar` → Assigns **7 seconds** green
  3. `ThreeCar` → Assigns **10 seconds** green
  4. `Accident` → Triggers **Immediate All-Red** safety halt
- **Weights:** Saved in [`models/best.pt`](models/best.pt)

---

## 📁 Project Structure

```
TrafficLight_Ai/
├── app.py                     # Main Python Flask server + YOLO AI logic
├── requirements.txt           # Python packages list
├── LICENSE                    # MIT License
├── README.md                  # This file
│
├── Images/                    # Flow diagram & hardware screenshots
│   ├── FlowDiagram.jpg        # System architecture and workflow diagram
│   └── HardwareDesign.jpeg    # Physical intersection model & hardware photo
│
├── models/
│   └── best.pt                # Custom trained YOLOv8 model
│
├── templates/
│   └── index.html             # Web dashboard user interface
│
├── firmware/                  # Arduino code for microcontrollers
│   ├── wifi_config.h          # Wi-Fi settings
│   ├── traffic_controller/    # ESP32 WROOM code (LEDs & HC-SR04 Sensors)
│   └── CameraWebServer/       # ESP32-CAM code (mDNS video stream)
│
├── data/                      # Dataset files & annotations
│
├── docs/                      # Detailed Guides
│   ├── HARDWARE_GUIDE.md      # Physical wiring & ultrasonic instructions
│   ├── MDNS_SETUP.md          # mDNS setup (no IP paste needed)
│   ├── DEPLOYMENT_GUIDE.md    # Remote internet access (Ngrok/Cloudflare)
│   ├── Full_Project_Description.pdf
│   └── Traffic_AI_Overview.pdf
│
└── scripts/
    └── start_system.bat       # One-click launcher for Windows
```

---

## 💼 CV / Resume Ready Points

You can copy and paste these points into your CV / Resume under **Projects**:

- **AI Smart Traffic Light System (Computer Vision & IoT Sensor Fusion)**
  - Architected an adaptive 3-lane intersection controller using **YOLOv8** and **ESP32 microcontrollers**, dynamically modulating green light phase durations based on real-time vehicle density.
  - Implemented a **dual-modal sensing pipeline** combining computer vision vehicle tracking with hardware-level **HC-SR04 ultrasonic distance sensors** for fail-safe vehicle counting and proximity verification.
  - Built an automated accident-detection protocol that triggers an emergency all-red stop in **<100ms** to prevent secondary collisions upon detecting a vehicle crash.
  - Configured zero-touch **mDNS** networking (`.local` resolution) for seamless plug-and-play node synchronization across changing Wi-Fi environments.
  - Developed a full-stack **Flask** web dashboard featuring low-latency MJPEG video streaming, live ultrasonic telemetry, manual overrides, and secure remote tunneling via **Ngrok / Cloudflare**.

---

## 📄 Documentation Links

- 🔧 [Step-by-step Hardware Wiring & Ultrasonic Guide](docs/HARDWARE_GUIDE.md)
- 📡 [mDNS Wi-Fi Setup Guide](docs/MDNS_SETUP.md)
- 🌐 [Remote Internet Access Guide](docs/DEPLOYMENT_GUIDE.md)
- 📑 [Full Project Report (PDF)](docs/Full_Project_Description.pdf)

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
