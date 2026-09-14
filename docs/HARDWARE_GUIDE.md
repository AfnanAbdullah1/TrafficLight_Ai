# 🔧 Hardware Implementation Guide
## AI Hybrid Traffic Lights Control System — Step by Step

---

## Components Checklist

| # | Component | Qty | Role |
|---|-----------|-----|------|
| 1 | ESP32-CAM (AI Thinker) | 3 | Cameras — one per lane |
| 2 | ESP32 WROOM (Dev Module) | 1 | Master controller — all LEDs + Ultrasonic sensors |
| 3 | Traffic LED Module (R/Y/G) | 3 | One per lane |
| 4 | Ultrasonic Sensor (HC-SR04) | 3 | Car counting — one per lane |
| 5 | Breadboard | 2–3 | Prototyping base |
| 6 | Jumper Wires | ~45 | Connections |
| 7 | USB Cables | 4 | Power + programming |

---

## STEP 1: Build the Intersection Model
**Time: 30 minutes**

```
              Lane 1 (Top)
                  │
                  │
                  ▼
    ─────────────────────────────
    Lane 3 ◄────  ┃  ────► Lane 2
    (Left)        ┃         (Right)
    ─────────────────────────────
                 Model Base
                (Cardboard / Wood)
```

1. Take a flat board (cardboard, wood, or acrylic) — roughly **40×40 cm**
2. Draw or tape 3 roads meeting at a **T-junction**
3. Label the roads: **Lane 1** (top), **Lane 2** (right), **Lane 3** (left)
4. Mark spots where traffic lights will go (at the intersection edge of each lane)
5. Mark camera mounting positions (elevated, looking down at each lane)

---

## STEP 2: Wire Traffic LED Modules to ESP32 WROOM
**Time: 20 minutes**

The WROOM controls ALL 3 traffic LED modules. Each module has 3 LEDs (Red, Yellow, Green) and a common ground.

### Wiring Table

> **Pin numbers match `firmware/traffic_controller/traffic_controller.ino`**

| LED Module | LED | WROOM GPIO | Wire Color (suggested) |
|------------|-----|------------|----------------------|
| **Lane 1 (Road A)** | 🔴 Red | **GPIO 23** | Red wire |
| | 🟡 Yellow | **GPIO 22** | Yellow wire |
| | 🟢 Green | **GPIO 21** | Green wire |
| | GND | **GND** | Black wire |
| **Lane 2 (Road B)** | 🔴 Red | **GPIO 19** | Red wire |
| | 🟡 Yellow | **GPIO 18** | Yellow wire |
| | 🟢 Green | **GPIO 5** | Green wire |
| | GND | **GND** | Black wire |
| **Lane 3 (Road C)** | 🔴 Red | **GPIO 26** | Red wire |
| | 🟡 Yellow | **GPIO 25** | Yellow wire |
| | 🟢 Green | **GPIO 4** | Green wire |
| | GND | **GND** | Black wire |

### How to Wire (per LED module):

```
   Traffic LED Module              ESP32 WROOM
   ┌──────────────┐               ┌──────────┐
   │  🔴 R ───────────────────────│ GPIO 23  │  (Lane 1)
   │  🟡 Y ───────────────────────│ GPIO 22  │
   │  🟢 G ───────────────────────│ GPIO 21  │
   │  GND ────────────────────────│ GND      │
   └──────────────┘               └──────────┘
```

> **Note:** If your LED modules have **built-in resistors** (most modules do), connect directly. If using bare LEDs, add a **220Ω resistor** on each LED pin.

### Physical Placement:
- Place each LED module at the edge of its lane, facing the incoming traffic direction
- Secure with tape or hot glue to the model base

---

## STEP 3: Wire Ultrasonic Sensors to WROOM
**Time: 15 minutes**

Three Ultrasonic distance sensors (HC-SR04) detect cars passing through each lane. The system measures distance; if an object is closer than **5 cm**, it counts as a car.

### Wiring Table

| Ultrasonic Sensor | TRIG Pin | ECHO Pin | VCC | GND |
|-----------|-----------|-----------|-----|-----|
| **Lane 1 Sensor** | **GPIO 13** | **GPIO 12** | **5V (VIN)** | **GND** |
| **Lane 2 Sensor** | **GPIO 14** | **GPIO 27** | **5V (VIN)** | **GND** |
| **Lane 3 Sensor** | **GPIO 15** | **GPIO 32** | **5V (VIN)** | **GND** |

### Wiring Diagram (per Ultrasonic sensor):

```
   Ultrasonic Sensor (HC-SR04)    ESP32 WROOM
   ┌──────────────┐               ┌──────────┐
   │  VCC ──────────────────│ 5V (VIN) │
   │  TRIG ─────────────────│ GPIO 13  │  (Lane 1 example)
   │  ECHO ─────────────────│ GPIO 12  │
   │  GND ──────────────────│ GND      │
   └──────────────┘               └──────────┘
```

> **Note on Voltage:** HC-SR04 sensors need **5V power** (use VIN pin). The ECHO pin will send a 5V signal back to the ESP32. While ESP32 pins are generally tolerant enough for short-term projects, the safest practice is to place a **1kΩ to 2kΩ resistor** between the sensor's ECHO pin and the ESP32 GPIO pin to step down the voltage.

### Physical Placement:
- Place each Ultrasonic sensor at the **entrance** of its lane, facing across the road (like a toll booth sensor) or directly at the oncoming traffic.
- Mount at a height where the body of passing toy cars will block the sound wave.

```
   Ultrasonic Sensor Placement
      [Sensor] ) ) ) ) ) ) 🚗  (measures < 5cm = count)
   ────────────────── Road
```

---

## STEP 4: Setup ESP32-CAMs (Camera Only)
**Time: 15 minutes per camera**

Each ESP32-CAM runs the CameraWebServer with mDNS — no wiring needed for LEDs or sensors. Just power and position.

### Power Options (choose one):
1. **USB cable** — connect micro-USB for power + programming
2. **5V pin** — supply 5V + GND from an external source

### Programming Setup:
ESP32-CAM has **no USB-to-serial chip**. You need an **FTDI programmer** (or USB-to-TTL adapter):

```
   FTDI Programmer              ESP32-CAM
   ┌──────────┐                ┌──────────────┐
   │ 5V  ──────────────────── │ 5V            │
   │ GND ──────────────────── │ GND           │
   │ TX  ──────────────────── │ U0R (GPIO 3)  │
   │ RX  ──────────────────── │ U0T (GPIO 1)  │
   └──────────┘                │               │
                               │ GPIO 0 ── GND │ ← Connect ONLY during upload!
                               └──────────────┘
```

> **Upload Mode:** Connect GPIO 0 to GND → press RESET → upload → disconnect GPIO 0 → press RESET again.

### Flashing with mDNS:

1. Open `firmware/CameraWebServer/CameraWebServer.ino` in Arduino IDE
2. Set `CAM_HOSTNAME`:
   - Board 1: `"cam-lane1"` → upload
   - Board 2: `"cam-lane2"` → upload
   - Board 3: `"cam-lane3"` → upload
3. Board: **AI Thinker ESP32-CAM** | Partition: **Huge APP (3MB)**
4. Serial Monitor shows: `cam-laneX.local`

### Physical Placement:
- Mount each camera **above** its lane, looking down at the road
- Use a small stand, clip, or tape to elevate ~15-20 cm
- Angle: **45°–90°** downward for best vehicle detection
- Ensure the camera view covers the road section of its lane

```
     Camera (elevated)
         📷
        / | \
       /  |  \
      /   |   \
   ──────────────── Road
     Vehicle view area
```

---

## STEP 5: Complete WROOM Pin Map (Visual Reference)

```
              ESP32 WROOM (Dev Module)
              ┌────────────────────────┐
              │                    3V3 │
              │                    GND │─── Common GND
              │                  GPIO 4│─── Lane 3 GREEN
              │                  GPIO 5│─── Lane 2 GREEN
              │                 GPIO 12│─── Lane 1 ECHO
              │                 GPIO 13│─── Lane 1 TRIG
              │                 GPIO 14│─── Lane 2 TRIG
              │                 GPIO 15│─── Lane 3 TRIG
              │                 GPIO 18│─── Lane 2 YELLOW
              │                 GPIO 19│─── Lane 2 RED
              │                 GPIO 21│─── Lane 1 GREEN
              │                 GPIO 22│─── Lane 1 YELLOW
              │                 GPIO 23│─── Lane 1 RED
              │                 GPIO 25│─── Lane 3 YELLOW
              │                 GPIO 26│─── Lane 3 RED
              │                 GPIO 27│─── Lane 2 ECHO
              │                 GPIO 32│─── Lane 3 ECHO
              │                    VIN │─── 5V for HC-SR04 sensors
              │                  GPIO 2│─── Status LED (built-in)
              └────────────────────────┘
              
    Total pins used: 15 out of 25+ available
```

---

## STEP 6: Power Everything Up & Test
**Time: 15 minutes**

### Power-On Sequence:
```
1. Connect WROOM via USB         → LEDs should all go RED (safe state)
2. Connect ESP32-CAM #1 via USB  → Wait for WiFi connection
3. Connect ESP32-CAM #2 via USB  → Wait for WiFi connection
4. Connect ESP32-CAM #3 via USB  → Wait for WiFi connection
```

### Quick Hardware Tests (before any software):

| Test | How | Expected Result |
|------|-----|-----------------|
| **LEDs** | Upload WROOM firmware → watch Serial Monitor | All RED → mDNS: traffic-esp.local |
| **Sensor Lane 1** | Place hand <5cm from Sensor on Lane 1 | Serial prints "[Sensor] Lane 1 car detected!" |
| **Sensor Lane 2** | Place hand <5cm from Sensor on Lane 2 | Serial prints "[Sensor] Lane 2 car detected!" |
| **Sensor Lane 3** | Place hand <5cm from Sensor on Lane 3 | Serial prints "[Sensor] Lane 3 car detected!" |
| **Camera 1** | Open `http://cam-lane1.local` in browser | See live camera web UI |
| **Camera 2** | Open `http://cam-lane2.local` | See live camera web UI |
| **Camera 3** | Open `http://cam-lane3.local` | See live camera web UI |

### Troubleshooting:

| Problem | Solution |
|---------|----------|
| LEDs don't light up | Check wire connections, verify GPIO pin numbers match table above |
| Sensor not detecting | Check VCC is connected to 5V (VIN), make sure object is < 5cm away |
| Sensor double-counting | Move object fully away so distance goes > 5cm before testing again |
| Camera won't connect to WiFi | SSID **TrafficSys**, password **System@123** (`firmware/wifi_config.h`) |
| Camera shows no image | Ensure GPIO 0 is NOT connected to GND (upload mode) |
| `.local` not found on Windows | Install [Bonjour](https://support.apple.com/kb/DL999) or use IP from Serial |
| WROOM keeps resetting | Check for short circuits, ensure stable power |

---

## Summary: Physical Model Layout

```
                    ┌──────────────────────┐
                    │           📷 CAM 1   │
                    │            ↓         │
                    │    🚦 Lane 1         │
                    │    ║  (LED Module 1)  │
                    │    ║  [HC-SR04 Sens 1]│
                    │    ║                  │
    ────────────────┤    ║                  ├────────────────
    📷 CAM 3        │    ║                  │        📷 CAM 2
      ↓             │    ║                  │         ↓
    🚦 Lane 3 ══════╬════╝                  ╠══════ Lane 2 🚦
    (LED Module 3)  │    T-Junction         │  (LED Module 2)
    [HC-SR04 Sens 3]│                       │  [HC-SR04 Sens 2]
    ────────────────┤                       ├────────────────
                    │                       │
                    │   ┌──────────────┐    │
                    │   │ ESP32 WROOM  │    │
                    │   │  (Master)    │    │
                    │   │  USB → PC    │    │
                    │   └──────────────┘    │
                    └──────────────────────┘
```

---

> **Next:** Flash firmware with mDNS ([MDNS_SETUP.md](MDNS_SETUP.md)), run `python app.py`, open `http://localhost:5000`, click **Connect All**.
