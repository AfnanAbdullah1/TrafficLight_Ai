# 🚦 AI Smart Traffic Light Control System

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-Web%20Server-green?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![YOLOv8](https://img.shields.io/badge/AI-YOLOv8-cyan?style=for-the-badge&logo=yolo&logoColor=black)](https://docs.ultralytics.com/)
[![OpenCV](https://img.shields.io/badge/OpenCV-Computer%20Vision-orange?style=for-the-badge&logo=opencv&logoColor=white)](https://opencv.org/)
[![ESP32](https://img.shields.io/badge/IoT-ESP32%20%26%20ESP32--CAM-red?style=for-the-badge&logo=espressif&logoColor=white)](https://www.espressif.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)

> A smart traffic light system that uses **AI cameras** to count cars in real time and give more green light time to busy lanes, while turning all lights **RED** instantly if an accident happens.

---

## 📸 Project Gallery

| 🖥️ Live Web Dashboard | 🛠️ Hardware Setup & Model |
| :---: | :---: |
| ![Dashboard Preview](assets/dashboard_preview.png) | ![Hardware Setup](assets/hardware_setup.png) |
| *Real-time video feeds, AI car counts & signal controls* | *3-lane physical intersection with ESP32 & LEDs* |

*(Screenshots will appear here once images are added to the [`assets/`](assets/) folder)*

---

## 💡 What is this Project?

Normal traffic lights change on fixed timers. Even when a road is completely empty, it stays green while busy lanes stay stuck in traffic.

**This project solves that:**
- **👀 AI Cameras Watch Each Lane:** 3 ESP32-CAMs stream live video of the intersection.
- **🧠 YOLOv8 AI Counts Vehicles:** The AI counts cars in each lane in real time.
- **⏱️ Dynamic Green Light Time:**
  - **1 Car:** 5 seconds green
  - **2 Cars:** 7 seconds green
  - **3+ Cars (Heavy Traffic):** 10 seconds green
- **🚨 Instant Accident Safety:** If a crash happens, the system detects it and turns **all signals RED** immediately to prevent further accidents.
- **📶 No IP Address Hassle:** Uses **mDNS** hostnames (`traffic-esp.local`, `cam-lane1.local`), so you never need to copy-paste new IP addresses when switching Wi-Fi.

---

## 🏗️ How It Works (Simple Architecture)

```
        📷 3x ESP32-CAMs                   💻 Laptop / PC                    🚦 ESP32 Controller
   (Watching 3 Traffic Lanes)           (Running YOLOv8 + Flask)             (Controls 9x LEDs & Sensors)
  ┌──────────────────────────┐         ┌──────────────────────────┐         ┌──────────────────────────┐
  │  cam-lane1.local         │         │   1. Receives video      │         │   1. Changes Red/Yellow/ │
  │  cam-lane2.local         ├────────►│   2. YOLOv8 counts cars  ├────────►│      Green LEDs          │
  │  cam-lane3.local         │  Video  │   3. Calculates green    │  HTTP   │   2. Ultrasonic sensors  │
  └──────────────────────────┘  Stream │      timer (5s / 7s / 10s│ Command │      double-check cars   │
                                       │   4. Hosts Web Dashboard │         │   traffic-esp.local      │
                                       └──────────────────────────┘         └──────────────────────────┘
```

---

## 🛠️ Hardware Used

| Component | Qty | Role |
| :--- | :---: | :--- |
| **ESP32 WROOM** | 1 | Master board — controls all 9 LEDs & reads distance sensors |
| **ESP32-CAM (AI-Thinker)** | 3 | Camera boards — streams live video for each lane |
| **Traffic Light Modules** | 3 | Red, Yellow, and Green LEDs for 3 lanes |
| **HC-SR04 Sensors** | 3 | Ultrasonic sensors to count cars by distance (<5 cm) |

### 📌 Wiring Pinout (ESP32 WROOM)

| Lane | 🔴 Red LED | 🟡 Yellow LED | 🟢 Green LED | 📡 Ultrasonic (TRIG / ECHO) |
| :--- | :---: | :---: | :---: | :---: |
| **Lane 1** | GPIO 23 | GPIO 22 | GPIO 21 | GPIO 13 / GPIO 12 |
| **Lane 2** | GPIO 19 | GPIO 18 | GPIO 5 | GPIO 14 / GPIO 27 |
| **Lane 3** | GPIO 26 | GPIO 25 | GPIO 4 | GPIO 15 / GPIO 32 |

> 📖 **Full Hardware Guide:** See [docs/HARDWARE_GUIDE.md](docs/HARDWARE_GUIDE.md) for breadboard connections and assembly steps.

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
- **Signal Status:** Shows which lane is currently GREEN or RED.
- **Sensor Counters:** Displays cars detected by ultrasonic sensors with a reset button.
- **Emergency Button:** Turn all lights RED with one click.

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
├── assets/                    # Project screenshots and demo photos
│
├── models/
│   └── best.pt                # Custom trained YOLOv8 model
│
├── templates/
│   └── index.html             # Web dashboard user interface
│
├── firmware/                  # Arduino code for microcontrollers
│   ├── wifi_config.h          # Wi-Fi settings
│   ├── traffic_controller/    # ESP32 WROOM code (LEDs & Sensors)
│   └── CameraWebServer/       # ESP32-CAM code (mDNS video stream)
│
├── data/                      # Dataset files & annotations
│
├── docs/                      # Detailed Guides
│   ├── HARDWARE_GUIDE.md      # Physical wiring & hardware instructions
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

- **AI Smart Traffic Light System (Computer Vision & IoT)**
  - Built an intelligent 3-lane traffic control system using **YOLOv8** and **ESP32 microcontrollers** to dynamically change signal timing based on real-time vehicle density.
  - Implemented automatic accident detection that triggers an emergency all-red stop in **<100ms** to prevent secondary collisions.
  - Configured zero-touch **mDNS** networking so devices auto-connect without static IP configuration.
  - Developed a real-time web dashboard using **Flask** and **OpenCV** with live video feeds, ultrasonic sensor data, and remote control via cloud tunnels.

---

## 📄 Documentation Links

- 🔧 [Step-by-step Hardware Wiring Guide](docs/HARDWARE_GUIDE.md)
- 📡 [mDNS Wi-Fi Setup Guide](docs/MDNS_SETUP.md)
- 🌐 [Remote Internet Access Guide](docs/DEPLOYMENT_GUIDE.md)
- 📑 [Full Project Report (PDF)](docs/Full_Project_Description.pdf)

---

## 📜 License

This project is licensed under the [MIT License](LICENSE).
