# 🔧 Hardware Implementation Guide
## AI Hybrid Traffic Lights Control System — Step by Step

---

## Components Checklist

| # | Component | Qty | Role |
|---|-----------|-----|------|
| 1 | ESP32-CAM (AI Thinker) | 3 | Cameras — one per route |
| 2 | ESP32 WROOM NodeMCU 32-pin | 1 | Master controller — all LEDs + sensors |
| 3 | Traffic LED Module (R/Y/G) | 3 | One per route |
| 4 | PIR Motion Sensor | 3 | Pedestrian detection |
| 5 | Ultrasonic Sensor (HC-SR04) | 2 | Vehicle detection (Route 1 & 2) |
| 6 | Breadboard | 3 | Prototyping base |
| 7 | Jumper Wires | ~40 | Connections |
| 8 | USB Cables | 4 | Power + programming |
| 9 | 1kΩ + 2kΩ Resistors | 2 each | Voltage dividers for ultrasonic ECHO |

---

## STEP 1: Build the Intersection Model
**Time: 30 minutes**

```
              Route 1 (Top)
                  │
                  │
                  ▼
    ─────────────────────────────
    Route 3 ◄────  ┃  ────► Route 2
    (Left)         ┃         (Right)
    ─────────────────────────────
                 Model Base
                (Cardboard / Wood)
```

1. Take a flat board (cardboard, wood, or acrylic) — roughly **40×40 cm**
2. Draw or tape 3 roads meeting at a **T-junction**
3. Label the roads: **Route 1** (top), **Route 2** (right), **Route 3** (left)
4. Mark spots where traffic lights will go (at the intersection edge of each route)
5. Mark camera mounting positions (elevated, looking down at each route)

---

## STEP 2: Wire Traffic LED Modules to ESP32 WROOM
**Time: 20 minutes**

The WROOM controls ALL 3 traffic LED modules. Each module has 3 LEDs (Red, Yellow, Green) and a common ground.

### Wiring Table

| LED Module | LED | WROOM GPIO | Wire Color (suggested) |
|------------|-----|------------|----------------------|
| **Route 1** | 🔴 Red | **GPIO 4** | Red wire |
| | 🟡 Yellow | **GPIO 16** | Yellow wire |
| | 🟢 Green | **GPIO 17** | Green wire |
| | GND | **GND** | Black wire |
| **Route 2** | 🔴 Red | **GPIO 5** | Red wire |
| | 🟡 Yellow | **GPIO 18** | Yellow wire |
| | 🟢 Green | **GPIO 19** | Green wire |
| | GND | **GND** | Black wire |
| **Route 3** | 🔴 Red | **GPIO 13** | Red wire |
| | 🟡 Yellow | **GPIO 14** | Yellow wire |
| | 🟢 Green | **GPIO 27** | Green wire |
| | GND | **GND** | Black wire |

### How to Wire (per LED module):

```
   Traffic LED Module              ESP32 WROOM
   ┌──────────────┐               ┌──────────┐
   │  🔴 R ───────────────────────│ GPIO 4   │
   │  🟡 Y ───────────────────────│ GPIO 16  │
   │  🟢 G ───────────────────────│ GPIO 17  │
   │  GND ────────────────────────│ GND      │
   └──────────────┘               └──────────┘
```

> **Note:** If your LED modules have **built-in resistors** (most modules do), connect directly. If using bare LEDs, add a **220Ω resistor** on each LED pin.

### Physical Placement:
- Place each LED module at the edge of its route, facing the incoming traffic direction
- Secure with tape or hot glue to the model base

---

## STEP 3: Wire PIR Motion Sensors to WROOM
**Time: 10 minutes**

PIR sensors detect pedestrians waiting at each crossing.

### Wiring Table

| PIR Sensor | PIR Pin | WROOM Pin |
|------------|---------|-----------|
| **PIR Route 1** | VCC | **3.3V** |
| | GND | **GND** |
| | OUT | **GPIO 25** |
| **PIR Route 2** | VCC | **3.3V** |
| | GND | **GND** |
| | OUT | **GPIO 26** |
| **PIR Route 3** | VCC | **3.3V** |
| | GND | **GND** |
| | OUT | **GPIO 33** |

### Wiring Diagram (per PIR):

```
   PIR Sensor                     ESP32 WROOM
   ┌──────────┐                  ┌──────────┐
   │ VCC ─────────────────────── │ 3.3V     │
   │ OUT ─────────────────────── │ GPIO 25  │
   │ GND ─────────────────────── │ GND      │
   └──────────┘                  └──────────┘
```

### Physical Placement:
- Place at the **pedestrian crossing area** of each route
- Angle the sensor to face the sidewalk/crossing zone
- Adjust the **sensitivity knob** on the PIR module (turn clockwise for more range)

---

## STEP 4: Wire Ultrasonic Sensors to WROOM
**Time: 15 minutes**

Ultrasonic sensors detect vehicles on Route 1 and Route 2.

### ⚠️ Important: Voltage Divider Required!

The HC-SR04 ECHO pin outputs **5V**, but ESP32 GPIO is **3.3V**. You MUST use a voltage divider:

```
   ECHO Pin ──── [1kΩ] ──── ESP32 GPIO ──── [2kΩ] ──── GND
                              (3.3V safe)
```

### Wiring Table

| Sensor | Sensor Pin | WROOM Pin | Notes |
|--------|-----------|-----------|-------|
| **Ultrasonic 1** | VCC | **5V (VIN)** | Needs 5V power |
| (Route 1) | GND | **GND** | |
| | TRIG | **GPIO 23** | Direct connection |
| | ECHO | **GPIO 35** | Via voltage divider! |
| **Ultrasonic 2** | VCC | **5V (VIN)** | Needs 5V power |
| (Route 2) | GND | **GND** | |
| | TRIG | **GPIO 32** | Direct connection |
| | ECHO | **GPIO 34** | Via voltage divider! |

### Wiring Diagram (per Ultrasonic):

```
   HC-SR04                        ESP32 WROOM
   ┌──────────┐                  ┌──────────┐
   │ VCC ─────────────────────── │ 5V (VIN) │
   │ TRIG ────────────────────── │ GPIO 23  │
   │ ECHO ──[1kΩ]──┬──────────── │ GPIO 35  │
   │               [2kΩ]         │          │
   │               │             │          │
   │ GND ──────────┴──────────── │ GND      │
   └──────────┘                  └──────────┘
```

### Physical Placement:
- Mount at the **entry point** of Route 1 and Route 2
- Face the sensor towards incoming vehicles
- Height: ~5-10 cm above road surface on your model
- The sensor detects vehicles passing within **30 cm**

---

## STEP 5: Setup ESP32-CAMs (Camera Only)
**Time: 15 minutes per camera**

Each ESP32-CAM runs the stock CameraWebServer — no wiring needed for LEDs or sensors. Just power and position.

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

### Physical Placement:
- Mount each camera **above** its route, looking down at the road
- Use a small stand, clip, or tape to elevate ~15-20 cm
- Angle: **45°–90°** downward for best vehicle detection
- Ensure the camera view covers the road section of its route

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

## STEP 6: Complete WROOM Pin Map (Visual Reference)

```
              ESP32 WROOM NodeMCU 32-Pin
              ┌────────────────────────┐
              │                    3V3 │─── PIR VCC (all 3)
              │                    GND │─── Common GND
              │                   GPIO4│─── Route 1 RED
              │                   GPIO5│─── Route 2 RED
              │                  GPIO13│─── Route 3 RED
              │                  GPIO14│─── Route 3 YELLOW
              │                  GPIO16│─── Route 1 YELLOW
              │                  GPIO17│─── Route 1 GREEN
              │                  GPIO18│─── Route 2 YELLOW
              │                  GPIO19│─── Route 2 GREEN
              │                  GPIO23│─── Ultrasonic 1 TRIG
              │                  GPIO25│─── PIR Route 1
              │                  GPIO26│─── PIR Route 2
              │                  GPIO27│─── Route 3 GREEN
              │                  GPIO32│─── Ultrasonic 2 TRIG
              │                  GPIO33│─── PIR Route 3
              │                  GPIO34│─── Ultrasonic 2 ECHO*
              │                  GPIO35│─── Ultrasonic 1 ECHO*
              │                    VIN │─── Ultrasonic VCC (5V)
              │                    GND │─── Ultrasonic GND
              │                  GPIO 2│─── Status LED (built-in)
              └────────────────────────┘
              
    * = via voltage divider (1kΩ + 2kΩ)
    Total pins used: 17 out of 25+ available
```

---

## STEP 7: Power Everything Up & Test
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
| **LEDs** | Upload WROOM firmware → watch Serial Monitor | All RED → then starts cycling if no WiFi |
| **PIR** | Wave hand in front of sensor | Serial prints "Pedestrian on Route X" |
| **Ultrasonic** | Place hand close (<30cm) | Serial prints "Vehicle! dist=Xcm" |
| **Camera 1** | Check Serial for IP → open in browser | See live camera web UI |
| **Camera 2** | Same as above | See live camera web UI |
| **Camera 3** | Same as above | See live camera web UI |

### Troubleshooting:

| Problem | Solution |
|---------|----------|
| LEDs don't light up | Check wire connections, verify GPIO pin numbers |
| PIR always HIGH | Adjust sensitivity potentiometer, check 3.3V power |
| Ultrasonic reads -1 | Check voltage divider on ECHO, verify 5V power |
| Camera won't connect to WiFi | Verify SSID/password, check serial output |
| Camera shows no image | Ensure GPIO 0 is NOT connected to GND (upload mode) |
| WROOM keeps resetting | Check for short circuits, ensure stable power |

---

## Summary: Physical Model Layout

```
                    ┌──────────────────────┐
                    │     PIR 1  📷 CAM 1  │
                    │       ↓     ↓        │
                    │    🚦 Route 1        │
                    │    ║  (LED Module 1)  │
                    │    ║                  │
    ────────────────┤    ║                  ├────────────────
    PIR 3  📷 CAM 3 │    ║                  │ PIR 2  📷 CAM 2
      ↓      ↓      │    ║                  │  ↓       ↓
    🚦 Route 3 ═════╬════╝                  ╠══════ Route 2 🚦
    (LED Module 3)  │    T-Junction         │  (LED Module 2)
    ────────────────┤                       ├────────────────
                    │  [Ultrasonic 1]       │
                    │  [Ultrasonic 2]       │
                    │                       │
                    │   ┌──────────────┐    │
                    │   │ ESP32 WROOM  │    │
                    │   │  (Master)    │    │
                    │   │  USB → PC    │    │
                    │   └──────────────┘    │
                    └──────────────────────┘
```

---

> **Next:** After hardware is wired and tested, proceed to the **Software Setup** — install Mosquitto, start the Node.js server, start the AI engine, and open the dashboard on your phone.
