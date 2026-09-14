/*
 * =====================================================
 * ESP32 Traffic Signal Controller
 * Compatible with: AI Traffic Signal Dashboard
 * =====================================================
 * 
 * This code runs on the ESP32 and receives commands
 * from the Flask dashboard over WiFi.
 * 
 * DASHBOARD SENDS:
 *   GET  /status         → We reply with connection info + Sensor counts
 *   GET  /sensor_counts  → We reply with car counts from Ultrasonic sensors
 *   POST /signal         → We receive {"lane1":"GREEN","lane2":"RED","lane3":"RED"}
 *   POST /reset_counts   → We reset all Ultrasonic car counters to zero
 * 
 * WIRING (Change pins below to match your setup):
 *   Road A (Lane 1): RED=23, YELLOW=22, GREEN=21
 *   Road B (Lane 2): RED=19, YELLOW=18, GREEN=5
 *   Road C (Lane 3): RED=26, YELLOW=25, GREEN=4
 *   Ultrasonic Lane 1: TRIG=13, ECHO=12
 *   Ultrasonic Lane 2: TRIG=14, ECHO=27
 *   Ultrasonic Lane 3: TRIG=15, ECHO=32
 * 
 * HOW TO USE:
 *   1. WiFi: edit firmware/wifi_config.h if needed
 *   2. Change pin numbers if your wiring is different
 *   3. Upload to ESP32 via Arduino IDE
 *   4. Dashboard uses hostname: traffic-esp.local (no IP paste needed)
 *   5. Click Connect (or Connect All) → WiFi badge turns green
 *   6. All dashboard controls now work on hardware
 * =====================================================
 */

#include <WiFi.h>
#include <ESPmDNS.h>
#include <WebServer.h>
#include <ArduinoJson.h>
#include "wifi_config.h"

// =====================================================
// WIFI — credentials in wifi_config.h (TrafficSys)
// =====================================================
const char* ssid     = WIFI_SSID;
const char* password = WIFI_PASSWORD;

// Fixed mDNS name — dashboard connects to traffic-esp.local
const char* MDNS_HOSTNAME = "traffic-esp";

// =====================================================
// WEB SERVER ON PORT 80
// =====================================================
WebServer server(80);

bool mdnsStarted = false;

void startMdns() {
    if (MDNS.begin(MDNS_HOSTNAME)) {
        mdnsStarted = true;
        Serial.print("mDNS hostname: http://");
        Serial.print(MDNS_HOSTNAME);
        Serial.println(".local");
    } else {
        mdnsStarted = false;
        Serial.println("mDNS start failed — use IP from Serial Monitor");
    }
}

// =====================================================
// PIN DEFINITIONS — CHANGE THESE TO MATCH YOUR WIRING
// =====================================================

// Road A (Lane 1)
#define A_RED    23
#define A_YELLOW 22
#define A_GREEN  21

// Road B (Lane 2)
#define B_RED    19
#define B_YELLOW 18
#define B_GREEN  5

// Road C (Lane 3)
#define C_RED    26
#define C_YELLOW 25
#define C_GREEN  4

// Ultrasonic Sensors (HC-SR04) for Car Counting
#define TRIG1 13
#define ECHO1 12

#define TRIG2 14
#define ECHO2 27

#define TRIG3 15
#define ECHO3 32

// Ultrasonic Threshold — distance in cm to detect a car
#define DIST_THRESHOLD 5  // Count if object is closer than 5 cm

// =====================================================
// CURRENT STATE TRACKING
// =====================================================
String lane1State = "RED";
String lane2State = "RED";
String lane3State = "RED";

// Hardware System Power State (now always true — controlled from dashboard only)
bool systemOn = true;

// Ultrasonic Car Count Variables
int carCount1 = 0;
int carCount2 = 0;
int carCount3 = 0;

// State tracking to prevent double counting
bool carPresent1 = false;
bool carPresent2 = false;
bool carPresent3 = false;

// =====================================================
// SET A SINGLE LANE's LIGHTS
// =====================================================
void setLane(int redPin, int yellowPin, int greenPin, String state) {
    // Turn all lights off for this lane first
    digitalWrite(redPin, LOW);
    digitalWrite(yellowPin, LOW);
    digitalWrite(greenPin, LOW);

    // Turn on the correct light
    if (state == "GREEN") {
        digitalWrite(greenPin, HIGH);
    } else if (state == "YELLOW") {
        digitalWrite(yellowPin, HIGH);
    } else {
        // Default to RED for safety
        digitalWrite(redPin, HIGH);
    }
}

// =====================================================
// APPLY ALL THREE LANES AT ONCE
// =====================================================
void applySignals() {
    // If system is toggled off locally, turn off all lights
    if (!systemOn) {
        int pins[] = {A_RED, A_YELLOW, A_GREEN, B_RED, B_YELLOW, B_GREEN, C_RED, C_YELLOW, C_GREEN};
        for (int p : pins) {
            digitalWrite(p, LOW);
        }
        return;
    }
    
    setLane(A_RED, A_YELLOW, A_GREEN, lane1State);
    setLane(B_RED, B_YELLOW, B_GREEN, lane2State);
    setLane(C_RED, C_YELLOW, C_GREEN, lane3State);
}

// =====================================================
// SAFETY: ALL RED
// =====================================================
void allRed() {
    lane1State = "RED";
    lane2State = "RED";
    lane3State = "RED";
    applySignals();
}

// =====================================================
// ULTRASONIC SENSOR HANDLING (Car Counting)
// =====================================================
long measureDistance(int trigPin, int echoPin) {
    // Clear the trigger
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    
    // Send 10 microsecond pulse
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);
    
    // Read the echo pulse duration
    long duration = pulseIn(echoPin, HIGH, 30000); // 30ms timeout (~5m max)
    
    if (duration == 0) return 999; // Timeout / No ping
    
    // Calculate distance in cm (Speed of sound = 343m/s)
    long distance = duration * 0.034 / 2;
    return distance;
}

void checkUltrasonicSensor(int trigPin, int echoPin, bool &carPresent, int &count, const char* label) {
    long distance = measureDistance(trigPin, echoPin);
    
    // Detect if car is within threshold
    if (distance < DIST_THRESHOLD) {
        if (!carPresent) {
            // Car just arrived!
            count++;
            carPresent = true;
            Serial.print("[Sensor] ");
            Serial.print(label);
            Serial.print(" car detected (");
            Serial.print(distance);
            Serial.print(" cm)! Total: ");
            Serial.println(count);
        }
    } else {
        // Car has left
        carPresent = false;
    }
}

void checkSensors() {
    checkUltrasonicSensor(TRIG1, ECHO1, carPresent1, carCount1, "Lane 1");
    // Small delay to avoid acoustic interference between sensors
    delay(10); 
    checkUltrasonicSensor(TRIG2, ECHO2, carPresent2, carCount2, "Lane 2");
    delay(10);
    checkUltrasonicSensor(TRIG3, ECHO3, carPresent3, carCount3, "Lane 3");
}

// =====================================================
// SETUP
// =====================================================
void setup() {
    Serial.begin(115200);
    Serial.println("\n================================");
    Serial.println("ESP32 Traffic Signal Controller");
    Serial.println("================================");

    // Initialize all pins as OUTPUT
    int pins[] = {
        A_RED, A_YELLOW, A_GREEN,
        B_RED, B_YELLOW, B_GREEN,
        C_RED, C_YELLOW, C_GREEN
    };

    for (int p : pins) {
        pinMode(p, OUTPUT);
        digitalWrite(p, LOW);
    }
    
    // Set Ultrasonic sensor pins
    pinMode(TRIG1, OUTPUT);
    pinMode(ECHO1, INPUT);
    pinMode(TRIG2, OUTPUT);
    pinMode(ECHO2, INPUT);
    pinMode(TRIG3, OUTPUT);
    pinMode(ECHO3, INPUT);
    Serial.println("Ultrasonic sensors initialized");

    // Start with ALL RED for safety
    allRed();

    // ==================== WIFI CONNECT ====================
    WiFi.mode(WIFI_STA);
    WiFi.begin(ssid, password);

    Serial.print("Connecting to WiFi");
    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 40) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        Serial.println("\nWiFi Connected!");
        Serial.print("IP Address: ");
        Serial.println(WiFi.localIP());
        startMdns();
        Serial.println("Dashboard hostname: traffic-esp.local");
    } else {
        Serial.println("\nWiFi FAILED! Restarting in 5 seconds...");
        delay(5000);
        ESP.restart();
    }

    // ==================== ENDPOINT: GET /status ====================
    // Dashboard calls this every 2 seconds to check if ESP32 is alive
    // Must return HTTP 200 for the dashboard to show "WiFi Connected"
    server.on("/status", HTTP_GET, []() {
        // Build current status JSON (includes Ultrasonic car counts)
        StaticJsonDocument<512> doc;
        doc["wifi"] = "connected";
        doc["hostname"] = "traffic-esp.local";
        doc["ip"] = WiFi.localIP().toString();
        doc["hardware_system_on"] = systemOn;
        doc["lane1"] = lane1State;
        doc["lane2"] = lane2State;
        doc["lane3"] = lane3State;
        doc["sensor_lane1"] = carCount1;
        doc["sensor_lane2"] = carCount2;
        doc["sensor_lane3"] = carCount3;

        String response;
        serializeJson(doc, response);

        // Allow requests from any origin (CORS)
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "application/json", response);
    });

    // ==================== ENDPOINT: POST /signal ====================
    // Dashboard sends this whenever signals change
    // Format: {"lane1": "GREEN", "lane2": "RED", "lane3": "RED"}
    // Values can be: "GREEN", "YELLOW", or "RED"
    server.on("/signal", HTTP_POST, []() {
        if (!server.hasArg("plain")) {
            server.send(400, "application/json", "{\"error\":\"no body\"}");
            return;
        }

        String body = server.arg("plain");

        StaticJsonDocument<256> doc;
        DeserializationError err = deserializeJson(doc, body);

        if (err) {
            Serial.println("[ERROR] Invalid JSON received");
            server.send(400, "application/json", "{\"error\":\"invalid json\"}");
            return;
        }

        // Read all three lane states from the dashboard
        // Default to current state if not provided
        String newLane1 = doc["lane1"] | lane1State;
        String newLane2 = doc["lane2"] | lane2State;
        String newLane3 = doc["lane3"] | lane3State;

        // Only update if something changed (reduces serial spam)
        if (newLane1 != lane1State || newLane2 != lane2State || newLane3 != lane3State) {
            lane1State = newLane1;
            lane2State = newLane2;
            lane3State = newLane3;

            // Apply to hardware
            applySignals();

            Serial.println("[SIGNAL] L1:" + lane1State + " L2:" + lane2State + " L3:" + lane3State);
        }

        // Allow requests from any origin (CORS)
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "application/json", "{\"success\":true}");
    });

    // Handle CORS preflight requests
    server.on("/signal", HTTP_OPTIONS, []() {
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.sendHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
        server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
        server.send(204);
    });

    // ==================== ENDPOINT: GET /sensor_counts ====================
    // Dashboard calls this to get the current car counts from Ultrasonic sensors
    server.on("/sensor_counts", HTTP_GET, []() {
        StaticJsonDocument<128> doc;
        doc["lane1"] = carCount1;
        doc["lane2"] = carCount2;
        doc["lane3"] = carCount3;

        String response;
        serializeJson(doc, response);

        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "application/json", response);
    });

    // ==================== ENDPOINT: POST /reset_counts ====================
    // Dashboard sends this to reset all car counters to zero
    server.on("/reset_counts", HTTP_POST, []() {
        carCount1 = 0;
        carCount2 = 0;
        carCount3 = 0;
        Serial.println("[Sensor] All car counters reset to 0");

        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.send(200, "application/json", "{\"success\":true}");
    });

    // Handle CORS preflight for /reset_counts
    server.on("/reset_counts", HTTP_OPTIONS, []() {
        server.sendHeader("Access-Control-Allow-Origin", "*");
        server.sendHeader("Access-Control-Allow-Methods", "POST, GET, OPTIONS");
        server.sendHeader("Access-Control-Allow-Headers", "Content-Type");
        server.send(204);
    });

    // ==================== START SERVER ====================
    server.begin();
    Serial.println("================================");
    Serial.println("HTTP Server Started on port 80");
    Serial.println("Ultrasonic sensors active for car counting (<5cm threshold)");
    Serial.println("Waiting for dashboard commands...");
    Serial.println("================================");
}

// =====================================================
// MAIN LOOP
// =====================================================
unsigned long lastReconnectAttempt = 0;

void loop() {
    checkSensors();
    server.handleClient();

    // Auto-reconnect WiFi if disconnected (non-blocking)
    if (WiFi.status() != WL_CONNECTED) {
        mdnsStarted = false;
        unsigned long currentMillis = millis();
        if (currentMillis - lastReconnectAttempt >= 5000) {
            Serial.println("[WARN] WiFi lost! Attempting reconnect...");
            WiFi.disconnect();
            WiFi.reconnect();
            lastReconnectAttempt = currentMillis;
        }
    } else if (!mdnsStarted) {
        startMdns();
    }
}