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
 *   GET  /status  → We reply with connection info
 *   POST /signal  → We receive {"lane1":"GREEN","lane2":"RED","lane3":"RED"}
 * 
 * WIRING (Change pins below to match your setup):
 *   Road A (Lane 1): RED=23, YELLOW=22, GREEN=21
 *   Road B (Lane 2): RED=19, YELLOW=18, GREEN=5
 *   Road C (Lane 3): RED=26, YELLOW=25, GREEN=4
 *   Push Button    : PIN=15
 * 
 * HOW TO USE:
 *   1. Change WiFi credentials below
 *   2. Change pin numbers if your wiring is different
 *   3. Upload to ESP32 via Arduino IDE
 *   4. Open Serial Monitor (115200 baud)
 *   5. Copy the IP address shown
 *   6. Enter that IP in the dashboard header
 *   7. Click Connect → WiFi badge turns green
 *   8. All dashboard controls now work on hardware
 * =====================================================
 */

#include <WiFi.h>
#include <WebServer.h>
#include <ArduinoJson.h>

// =====================================================
// WIFI SETTINGS — CHANGE THESE TO YOUR WIFI
// =====================================================
const char* ssid     = "Care";
const char* password = "Care@123";

// =====================================================
// WEB SERVER ON PORT 80
// =====================================================
WebServer server(80);

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

// Push Button (Toggle ON/OFF)
#define BUTTON_PIN 15

// =====================================================
// CURRENT STATE TRACKING
// =====================================================
String lane1State = "RED";
String lane2State = "RED";
String lane3State = "RED";

// Hardware System Power State
bool systemOn = true;

// Button Debounce Variables
unsigned long lastDebounceTime = 0;
int lastButtonState = HIGH;
int buttonState = HIGH;

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
// BUTTON HANDLING
// =====================================================
void checkButton() {
    int reading = digitalRead(BUTTON_PIN);
    
    // Check for state change (debouncing)
    if (reading != lastButtonState) {
        lastDebounceTime = millis();
    }
    
    // If stable for 50ms, consider it a valid state
    if ((millis() - lastDebounceTime) > 50) {
        if (reading != buttonState) {
            buttonState = reading;
            if (buttonState == LOW) { // Button pressed
                systemOn = !systemOn; // Toggle system state
                Serial.println(systemOn ? "[HARDWARE] SYSTEM ON" : "[HARDWARE] SYSTEM OFF");
                applySignals();       // Apply the new state to lights immediately
            }
        }
    }
    
    lastButtonState = reading;
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
    
    // Set button pin as input with internal pull-up resistor
    pinMode(BUTTON_PIN, INPUT_PULLUP);

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
        Serial.println("Enter this IP in the dashboard header");
    } else {
        Serial.println("\nWiFi FAILED! Restarting in 5 seconds...");
        delay(5000);
        ESP.restart();
    }

    // ==================== ENDPOINT: GET /status ====================
    // Dashboard calls this every 2 seconds to check if ESP32 is alive
    // Must return HTTP 200 for the dashboard to show "WiFi Connected"
    server.on("/status", HTTP_GET, []() {
        // Build current status JSON
        StaticJsonDocument<256> doc;
        doc["wifi"] = "connected";
        doc["hardware_system_on"] = systemOn;
        doc["lane1"] = lane1State;
        doc["lane2"] = lane2State;
        doc["lane3"] = lane3State;

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

    // ==================== START SERVER ====================
    server.begin();
    Serial.println("================================");
    Serial.println("HTTP Server Started on port 80");
    Serial.println("Waiting for dashboard commands...");
    Serial.println("================================");
}

// =====================================================
// MAIN LOOP
// =====================================================
unsigned long lastReconnectAttempt = 0;

void loop() {
    checkButton();
    server.handleClient();

    // Auto-reconnect WiFi if disconnected (non-blocking)
    if (WiFi.status() != WL_CONNECTED) {
        unsigned long currentMillis = millis();
        if (currentMillis - lastReconnectAttempt >= 5000) {
            Serial.println("[WARN] WiFi lost! Attempting reconnect...");
            WiFi.disconnect();
            WiFi.reconnect();
            lastReconnectAttempt = currentMillis;
        }
    }
}