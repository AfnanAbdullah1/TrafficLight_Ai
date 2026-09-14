# 🚦 AI-Powered Smart Hybrid Traffic Light Control System

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.3%2B-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![YOLOv8](https://img.shields.io/badge/YOLOv8-Ultralytics-00FFFF?style=for-the-badge&logo=yolo&logoColor=black)](https://docs.ultralytics.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![ESP32](https://img.shields.io/badge/Hardware-ESP32%20%7C%20ESP32--CAM-E7352C?style=for-the-badge&logo=espressif&logoColor=white)](https://www.espressif.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

An intelligent, real-time traffic signal automation system combining **Edge AI (YOLOv8)**, **embedded IoT microcontrollers (ESP32 & ESP32-CAM)**, and a **centralized Flask web dashboard**. The system autonomously mitigates urban intersection bottlenecks by dynamically adjusting signal phase durations based on real-time vehicle density and immediately triggering safety overrides upon detecting collisions.

---

## 📑 Table of Contents

- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [Key Features](#-key-features)
- [Hardware & Pinout Specifications](#-hardware--pinout-specifications)
- [Repository Structure](#-repository-structure)
- [Quick Start Guide](#-quick-start-guide)
- [Firmware Flashing Guide](#-firmware-flashing-guide)
- [Dashboard & Controls](#-dashboard--controls)
- [Machine Learning Pipeline](#-machine-learning-pipeline)
- [Remote Deployment](#-remote-deployment)
- [Resume / CV Highlights](#-resume--cv-highlights)
- [License](#-license)

---

## 🌟 Overview

Conventional timer-based traffic lights operate on rigid, static schedules, causing severe delays on high-volume lanes while giving green lights to empty roads. 

This project solves this inefficiency with a **hybrid distributed edge architecture**:
1. **Dedicated Camera Nodes (3× ESP32-CAM)** stream low-latency MJPEG video feeds of each intersection approach over Wi-Fi.
2. **Central Edge Server (Laptop / Mini PC running Flask)** runs a custom-trained **YOLOv8 deep learning model** to assess vehicle congestion in real time and compute optimal green phase timings (e.g., 5s, 7s, 10s).
3. **Master Hardware Controller (ESP32 WROOM)** receives signal transition instructions via low-overhead HTTP REST endpoints to actuate 3-lane traffic LED modules and continuously poll **HC-SR04 ultrasonic distance sensors** for physical vehicle presence verification.
4. **Zero-Configuration Networking (mDNS)** ensures seamless reconnection across dynamic Wi-Fi/hotspot environments without IP reconfiguration.

---

## 🏗️ System Architecture

```
                                  EDGE COMPUTING HOST (Laptop / PC)
                    ┌────────────────────────────────────────────────────────────┐
                    │                      Flask Application                     │
                    │   ┌───────────────────────┐    ┌───────────────────────┐   │
                    │   │  YOLOv8 Vision Model  │    │  Web UI Dashboard     │   │
                    │   │  - Vehicle Density    │    │  - Real-time Video    │   │
                    │   │  - Accident Detection │    │  - Manual Override    │   │
                    │   └──────────▲────────────┘    │  - Sensor Telemetry   │   │
                    │              │                 └───────────────────────┘   │
                    │   ┌──────────┴────────────┐    ┌───────────────────────┐   │
                    │   │  MJPEG Stream Proxy   │    │  Adaptive Controller  │   │
                    │   │  (/video_feed/laneX)  │    │  (Dynamic Timers)     │   │
                    │   └──────────▲────────────┘    └───────────┬───────────┘   │
                    └──────────────┼─────────────────────────────┼───────────────┘
                                   │ HTTP Stream (:81)           │ HTTP POST /signal
                                   │                             │ HTTP GET  /status
             ┌─────────────────────┴───────────────┐             │
             │                                     │             ▼
    ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ ┌───────────────────────────┐
    │  ESP32-CAM #1   │ │  ESP32-CAM #2   │ │  ESP32-CAM #3   │ │  ESP32 WROOM Controller   │
    │  Lane 1 Camera  │ │  Lane 2 Camera  │ │  Lane 3 Camera  │ │  - 9x Traffic Signal LEDs  │
    │ cam-lane1.local │ │ cam-lane2.local │ │ cam-lane3.local │ │  - 3x HC-SR04 Ultrasonics │
    └─────────────────┘ └─────────────────┘ └─────────────────┘ │    traffic-esp.local      │
                                                                └───────────────────────────┘
```

### Why Hybrid Hardware Separation?
- **Stability & Isolation**: ESP32-CAM boards dedicate all memory and processing to stable video streaming via OV2640 sensors without GPIO contention.
- **Dedicated I/O**: The ESP32 WROOM provides 20+ accessible GPIO pins to handle 9 signal LEDs and 3 ultrasonic sensors with zero hardware bus conflict.
- **Fault-Tolerant Operation**: If a camera drops offline, the central controller automatically falls back to baseline sequencing and ultrasonic car count metrics.

---

## ⚡ Key Features

- **Dynamic Density-Based Timing**: Adjusts lane green signals dynamically (5s, 7s, or 10s) based on live vehicle count classifications from the YOLOv8 vision pipeline.
- **Autonomous Accident Detection & Emergency Lockout**: Immediately trips an **All-Red safety stop** across all lanes when an accident is detected, preventing secondary collisions.
- **Zero-Configuration mDNS Discovery**: Devices publish localized hostnames (`traffic-esp.local`, `cam-lane1.local`, etc.), eliminating the need to manually update static IPs when changing networks or hotspots.
- **Dual-Modal Sensing**: Combines computer vision vehicle detection with hardware ultrasonic telemetry (<5 cm proximity count) for robust verification.
- **Low-Latency Web Dashboard**: Modern, responsive dark-mode UI with live annotated video feeds, timer countdowns, lane toggles, manual overrides, and keyboard shortcuts.
- **Remote Access Ready**: Integrates seamlessly with Ngrok and Cloudflare Tunnels for monitoring and control from anywhere over mobile data or home networks.

---

## 🔌 Hardware & Pinout Specifications

### 1. Master Controller: ESP32 WROOM (30-pin Dev Module)

#### Traffic Signal LEDs (9 GPIOs)
| Lane | Red LED | Yellow LED | Green LED | Common |
|:-----|:-------:|:----------:|:---------:|:------:|
| **Lane 1 (Road A)** | GPIO 23 | GPIO 22 | GPIO 21 | GND |
| **Lane 2 (Road B)** | GPIO 19 | GPIO 18 | GPIO 5  | GND |
| **Lane 3 (Road C)** | GPIO 26 | GPIO 25 | GPIO 4  | GND |

#### Ultrasonic Sensors (HC-SR04)
| Lane | TRIG Pin | ECHO Pin | VCC | GND |
|:-----|:--------:|:--------:|:---:|:---:|
| **Lane 1** | GPIO 13 | GPIO 12 | 5V (VIN) | GND |
| **Lane 2** | GPIO 14 | GPIO 27 | 5V (VIN) | GND |
| **Lane 3** | GPIO 15 | GPIO 32 | 5V (VIN) | GND |

### 2. Camera Nodes: 3× AI Thinker ESP32-CAM
- **Camera Sensor**: OV2640 (JPEG mode, SVGA / VGA resolution)
- **Firmware**: Custom Espressif CameraWebServer with mDNS service integration
- **Power**: 5V / 2A external source recommended for clean Wi-Fi transmission

> 📖 **Comprehensive Wiring & Assembly Guide**: See [docs/HARDWARE_GUIDE.md](docs/HARDWARE_GUIDE.md) for full circuit schematics, resistor details, and breadboard diagrams.

---

## 📂 Repository Structure

```
TrafficLight_Ai/
├── .gitignore                          # Git exclusions for Python, build & IDE caches
├── LICENSE                             # MIT Open-Source License
├── README.md                           # Master repository documentation
├── requirements.txt                    # Production Python dependencies
├── app.py                              # Central Flask server, AI worker & control engine
│
├── models/
│   └── best.pt                         # Trained YOLOv8 custom model weights
│
├── templates/
│   └── index.html                      # Real-time web control dashboard
│
├── firmware/
│   ├── wifi_config.h                   # Master Wi-Fi credentials template
│   ├── traffic_controller/
│   │   ├── traffic_controller.ino      # ESP32 WROOM firmware (LEDs + Sensors + mDNS)
│   │   └── wifi_config.h               # Sketch Wi-Fi configuration
│   └── CameraWebServer/
│       ├── CameraWebServer.ino         # ESP32-CAM firmware with mDNS support
│       ├── app_httpd.cpp               # High-throughput MJPEG camera web server
│       ├── board_config.h              # AI Thinker board definition
│       ├── camera_pins.h               # Pinout mappings for ESP32-CAM
│       └── wifi_config.h               # Sketch Wi-Fi configuration
│
├── data/                               # Dataset & training metadata
│   ├── data.yaml                       # Roboflow dataset configuration (4 classes)
│   ├── train/                          # Training split (images & annotations)
│   ├── valid/                          # Validation split
│   └── test/                           # Test split
│
├── docs/                               # Detailed technical guides & specifications
│   ├── HARDWARE_GUIDE.md               # Step-by-step physical assembly & wiring guide
│   ├── MDNS_SETUP.md                   # Zero-configuration mDNS networking manual
│   ├── DEPLOYMENT_GUIDE.md             # Worldwide remote access guide (Ngrok/Cloudflare)
│   ├── Full_Project_Description.pdf    # Comprehensive academic project report
│   ├── Traffic_AI_Overview.pdf         # Visual project presentation & system architecture
│   └── Project_Report.doc              # Project documentation archive
│
└── scripts/
    └── start_system.bat                # Automated one-click server & tunnel launcher
```

---

## 🚀 Quick Start Guide

### 1. Clone & Environment Setup

```bash
# Clone the repository
git clone https://github.com/AfnanAbdullah1/TrafficLight_Ai.git
cd TrafficLight_Ai

# Create and activate a Python virtual environment
python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

# Install required dependencies
pip install -r requirements.txt
```

### 2. Configure Wi-Fi Credentials

Open `firmware/wifi_config.h` and configure your local Wi-Fi / mobile hotspot:

```cpp
#define WIFI_SSID "YourNetworkName"
#define WIFI_PASS "YourPassword"
```

*(Note: Copy this file into `firmware/traffic_controller/` and `firmware/CameraWebServer/` before flashing).*

### 3. Launch the Backend Server

```bash
python app.py
```
Or simply double-click **`scripts/start_system.bat`** on Windows.

Open your browser at **`http://localhost:5000`** and click **"Connect All"** to automatically discover all nodes via mDNS!

---

## 💻 Firmware Flashing Guide

All microcontrollers are programmed using the **Arduino IDE** (with ESP32 board definitions installed):

1. **Traffic Controller (ESP32 WROOM)**:
   - File: `firmware/traffic_controller/traffic_controller.ino`
   - Board: `ESP32 Dev Module`
   - Serial Monitor: Confirms connection at `http://traffic-esp.local`

2. **Camera Nodes (3× ESP32-CAM)**:
   - File: `firmware/CameraWebServer/CameraWebServer.ino`
   - Board: `AI Thinker ESP32-CAM` | Partition Scheme: `Huge APP (3MB No OTA)`
   - Set `CAM_HOSTNAME` sequentially per board:
     - Board 1: `"cam-lane1"`
     - Board 2: `"cam-lane2"`
     - Board 3: `"cam-lane3"`
   - Connect **GPIO 0 to GND** during upload, disconnect and hit RST to boot.

> 📖 **Detailed Step-by-Step Instructions**: Refer to [docs/MDNS_SETUP.md](docs/MDNS_SETUP.md).

---

## 🎮 Dashboard & Controls

The Flask web UI provides complete manual and automated supervisory control:

- **Live Camera Grid**: High-frame-rate MJPEG streams with real-time YOLO bounding boxes.
- **Traffic Light Status**: Real-time interactive LED indicator states matching the physical hardware.
- **Sensor Counts**: Live ultrasonic detection counts per lane with a 1-click reset button.
- **Mode Switching**: Toggle seamlessly between **Autonomous Dynamic Sequence** and **Manual Control**.
- **Accident / Emergency Protocol**: One-click override forcing all lanes Red with flashing warning banners.

### Keyboard Shortcuts
| Key | Action |
|:---:|:-------|
| `1` / `2` / `3` | Force Green light on Lane 1 / 2 / 3 |
| `A` | Switch to Autonomous AI Sequence Mode |
| `M` | Switch to Manual Mode |
| `Esc` | Clear Emergency / Resume Normal Operations |

---

## 🧠 Machine Learning Pipeline

- **Architecture**: Ultralytics YOLOv8 (nano/small backbone optimized for edge inference).
- **Dataset**: Custom-labeled multi-lane vehicle dataset via **Roboflow** (`afnan-yzsee/toycars-klrio`).
- **Detection Classes**:
  1. `Accident` (Critical Priority — triggers instant All-Red safety stop)
  2. `ThreeCar` (High Density — assigns 10s green phase)
  3. `TwoCar` (Medium Density — assigns 7s green phase)
  4. `OneCar` (Low Density — assigns 5s baseline green phase)
- **Inference Optimization**: Multi-threaded worker threads process camera streams asynchronously, preventing UI latency or frame drop.

---

## 🌐 Remote Deployment

The system is fully configured for out-of-lab remote monitoring via secure tunneling:
- **Ngrok Tunnel**: Exposes port `5000` via automated batch script `scripts/start_system.bat`.
- **Cloudflare Zero-Trust Tunnels**: Persistent, encrypted subdomains with zero port-forwarding requirements.

> 📖 **Full Remote Access Guide**: See [docs/DEPLOYMENT_GUIDE.md](docs/DEPLOYMENT_GUIDE.md).

---

## 💼 Resume / CV Highlights

*Feel free to adapt these bullet points for your Software Engineer, Computer Vision, or Embedded IoT resume:*

- **AI-Powered Smart Hybrid Traffic Light Control System | Python, YOLOv8, Flask, ESP32, OpenCV**
  - Architected a distributed edge-IoT traffic automation system utilizing **YOLOv8** and **ESP32 microcontrollers** to dynamically optimize intersection signal timing based on real-time vehicle density.
  - Implemented an autonomous safety fail-safe mechanism that detects vehicular collisions via computer vision and triggers an immediate all-red intersection halt within **<100ms**.
  - Engineered zero-configuration networking using **mDNS**, enabling seamless plug-and-play auto-discovery across dynamic Wi-Fi environments without static IP dependencies.
  - Designed a responsive full-stack **Flask** web dashboard supporting low-latency multi-channel MJPEG proxy streaming, ultrasonic sensor telemetry, and secure cloud tunneling (**Ngrok / Cloudflare**).

---

## 📄 License

This project is licensed under the [MIT License](LICENSE) — free for academic, personal, and commercial open-source use.
