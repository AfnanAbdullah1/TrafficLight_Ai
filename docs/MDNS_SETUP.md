# mDNS Setup — No More Pasting IPs

When you change phones (same WiFi name/password), IP addresses change. **Hostnames stay the same.**

| Device | Hostname |
|--------|----------|
| Traffic ESP32 | `traffic-esp.local` |
| Camera lane 1 | `cam-lane1.local` |
| Camera lane 2 | `cam-lane2.local` |
| Camera lane 3 | `cam-lane3.local` |

---

## WiFi (all devices)

| Setting | Value |
|---------|--------|
| SSID | `TrafficSys` |
| Password | `System@123` |

Edit **`firmware/wifi_config.h`** to change; copy that file into each sketch folder.

## Step 1 — Traffic ESP32 (one board)

1. Open `firmware/traffic_controller/traffic_controller.ino` in Arduino IDE
2. WiFi is read from `wifi_config.h` (no edit needed if using defaults above)
3. Board: **ESP32 Dev Module**
4. Upload
5. Serial Monitor should show: `mDNS hostname: http://traffic-esp.local`

---

## Step 2 — ESP32-CAM ×3 (one hostname per board)

1. Open `firmware/CameraWebServer/CameraWebServer.ino` in Arduino IDE
2. Board: **AI Thinker ESP32-CAM** | Partition: **Huge APP (3MB)**
3. Set `CAM_HOSTNAME` at top of file:
   - Board 1: `"cam-lane1"` → upload
   - Board 2: `"cam-lane2"` → upload
   - Board 3: `"cam-lane3"` → upload
4. Serial Monitor shows the mDNS hostname after WiFi connects

> WiFi credentials are read from `wifi_config.h` (already in the sketch folder).

---

## Step 3 — Laptop + dashboard

1. Connect **laptop and all ESP devices** to the **same** hotspot
2. Run: `python app.py`
3. Open: `http://localhost:5000`
4. Click **Connect All** (or wait ~1s — auto-connect runs)

Hostnames are pre-filled. You do **not** need new IPs when you switch phones.

---

## Step 4 — After changing hotspot phone

1. Power on ESP32 + cameras (they join WiFi)
2. Start `python app.py` on laptop (on same hotspot)
3. Open dashboard → **Connect All**

Same hostnames, new IPs resolved automatically.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| ESP32 not connecting | Check Serial Monitor; confirm same WiFi as laptop |
| `.local` not found on Windows | Install [Bonjour](https://support.apple.com/kb/DL999) or use IP once from Serial |
| Camera stream fails | Confirm mDNS firmware uploaded; open `http://cam-lane1.local` in browser |
| Still using old firmware | Re-upload `traffic_controller.ino` and `CameraWebServer.ino` |

---

## Optional: raw IP still works

You can still type `192.168.x.x` in the dashboard if needed.
