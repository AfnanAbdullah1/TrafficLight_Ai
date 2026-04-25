/*
 * ============================================================
 *  AI Hybrid Traffic Lights Control System
 *  ESP32 WROOM — Master Coordinator Firmware
 * ============================================================
 *
 *  The WROOM handles:
 *    - 2x Ultrasonic sensors for vehicle counting
 *    - Fallback local timing sequence when WiFi is down
 *    - Coordinates with server via MQTT
 *
 * ============================================================
 */

// ==================== CONFIGURATION ====================

// WiFi Credentials
const char* WIFI_SSID     = "YOUR_WIFI_SSID";      // <<< CHANGE THIS
const char* WIFI_PASSWORD  = "YOUR_WIFI_PASSWORD";  // <<< CHANGE THIS

// MQTT Broker (your PC's IP)
const char* MQTT_SERVER    = "192.168.1.100";       // <<< CHANGE THIS
const int   MQTT_PORT      = 1883;

// ==================== PIN DEFINITIONS ====================
// Ultrasonic Sensor 1 (Route 1)
#define US1_TRIG   5
#define US1_ECHO   18

// Ultrasonic Sensor 2 (Route 2)
#define US2_TRIG   19
#define US2_ECHO   21

// Status LED (built-in or external)
#define STATUS_LED 2

// ==================== TIMING ====================
#define US_READ_INTERVAL      1000    // Read ultrasonic every 1s
#define US_PUBLISH_INTERVAL   5000    // Publish counts every 5s
#define VEHICLE_THRESHOLD     30.0    // cm — closer than this = vehicle detected
#define STATUS_INTERVAL       3000    // Publish master status every 3s

// ==================== INCLUDES ====================
#include <WiFi.h>
#include <PubSubClient.h>

// ==================== GLOBAL STATE ====================
WiFiClient espClient;
PubSubClient mqtt(espClient);

// Ultrasonic vehicle counts (reset after each publish)
int vehicleCount1 = 0;
int vehicleCount2 = 0;

// Previous detection state (for edge detection)
bool prevDetected1 = false;
bool prevDetected2 = false;

// Timing trackers
unsigned long lastUSRead = 0;
unsigned long lastUSPublish = 0;
unsigned long lastStatusPublish = 0;
unsigned long lastWifiAttempt = 0;

// System state
bool wifiConnected = false;
bool mqttConnected = false;

// ==================== ULTRASONIC FUNCTIONS ====================

float readUltrasonic(int trigPin, int echoPin) {
    // Send trigger pulse
    digitalWrite(trigPin, LOW);
    delayMicroseconds(2);
    digitalWrite(trigPin, HIGH);
    delayMicroseconds(10);
    digitalWrite(trigPin, LOW);

    // Read echo with timeout (30ms = ~5m max)
    long duration = pulseIn(echoPin, HIGH, 30000);

    if (duration == 0) return -1;  // No echo (timeout)

    float distance = (duration * 0.034) / 2.0;
    return distance;
}

void processUltrasonicReadings() {
    // Read Sensor 1 (Route 1)
    float dist1 = readUltrasonic(US1_TRIG, US1_ECHO);
    if (dist1 > 0 && dist1 < VEHICLE_THRESHOLD) {
        if (!prevDetected1) {
            // Rising edge — new vehicle detected
            vehicleCount1++;
            Serial.printf("[US1] Vehicle detected! Distance: %.1f cm | Count: %d\n", dist1, vehicleCount1);
        }
        prevDetected1 = true;
    } else {
        prevDetected1 = false;
    }

    // Read Sensor 2 (Route 2)
    float dist2 = readUltrasonic(US2_TRIG, US2_ECHO);
    if (dist2 > 0 && dist2 < VEHICLE_THRESHOLD) {
        if (!prevDetected2) {
            vehicleCount2++;
            Serial.printf("[US2] Vehicle detected! Distance: %.1f cm | Count: %d\n", dist2, vehicleCount2);
        }
        prevDetected2 = true;
    } else {
        prevDetected2 = false;
    }
}

void publishVehicleCounts() {
    char msg1[60], msg2[60];

    snprintf(msg1, sizeof(msg1), "{\"route\":1,\"count\":%d}", vehicleCount1);
    snprintf(msg2, sizeof(msg2), "{\"route\":2,\"count\":%d}", vehicleCount2);

    mqtt.publish("traffic/vehicle_count/1", msg1);
    mqtt.publish("traffic/vehicle_count/2", msg2);

    Serial.printf("[PUBLISH] Route 1: %d vehicles | Route 2: %d vehicles\n", vehicleCount1, vehicleCount2);

    // Reset counters
    vehicleCount1 = 0;
    vehicleCount2 = 0;
}

// ==================== WiFi FUNCTIONS ====================

void connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        return;
    }

    Serial.printf("[WiFi] Connecting to %s", WIFI_SSID);
    WiFi.mode(WIFI_STA);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

    int attempts = 0;
    while (WiFi.status() != WL_CONNECTED && attempts < 20) {
        delay(500);
        Serial.print(".");
        attempts++;
    }

    if (WiFi.status() == WL_CONNECTED) {
        wifiConnected = true;
        Serial.printf("\n[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
        digitalWrite(STATUS_LED, HIGH);
    } else {
        wifiConnected = false;
        Serial.println("\n[WiFi] Connection failed, will retry...");
        digitalWrite(STATUS_LED, LOW);
    }
}

// ==================== MQTT FUNCTIONS ====================

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    char message[256];
    int len = min((unsigned int)255, length);
    memcpy(message, payload, len);
    message[len] = '\0';

    Serial.printf("[MQTT] Topic: %s | Message: %s\n", topic, message);

    // The WROOM listens but doesn't control LEDs directly
    // It can relay commands to ESP32-CAMs via ESP-NOW if WiFi fails (future enhancement)
}

void connectMQTT() {
    if (mqtt.connected()) {
        mqttConnected = true;
        return;
    }

    Serial.println("[MQTT] Connecting as wroom_master...");

    if (mqtt.connect("wroom_master")) {
        mqttConnected = true;
        Serial.println("[MQTT] Connected!");

        // Subscribe to system-wide topics
        mqtt.subscribe("traffic/mode");
        mqtt.subscribe("traffic/emergency");

        // Announce master online
        mqtt.publish("traffic/master/status", "{\"device\":\"wroom_master\",\"status\":\"online\"}");
    } else {
        mqttConnected = false;
        Serial.printf("[MQTT] Failed, rc=%d. Will retry...\n", mqtt.state());
    }
}

void publishMasterStatus() {
    char statusMsg[120];
    snprintf(statusMsg, sizeof(statusMsg),
        "{\"device\":\"wroom_master\",\"wifi\":%s,\"mqtt\":%s,\"uptime\":%lu}",
        wifiConnected ? "true" : "false",
        mqttConnected ? "true" : "false",
        millis() / 1000
    );
    mqtt.publish("traffic/master/status", statusMsg);
}

// ==================== SETUP ====================

void setup() {
    Serial.begin(115200);
    Serial.println("\n\n========================================");
    Serial.println("  AI Traffic Light - WROOM Master");
    Serial.println("========================================\n");

    // Ultrasonic pins
    pinMode(US1_TRIG, OUTPUT);
    pinMode(US1_ECHO, INPUT);
    pinMode(US2_TRIG, OUTPUT);
    pinMode(US2_ECHO, INPUT);

    // Status LED
    pinMode(STATUS_LED, OUTPUT);
    digitalWrite(STATUS_LED, LOW);

    // Connect WiFi
    connectWiFi();

    // Setup MQTT
    mqtt.setServer(MQTT_SERVER, MQTT_PORT);
    mqtt.setCallback(mqttCallback);
    mqtt.setBufferSize(512);

    connectMQTT();

    Serial.println("[SETUP] Master initialization complete!\n");
}

// ==================== MAIN LOOP ====================

void loop() {
    unsigned long now = millis();

    // Maintain WiFi
    if (WiFi.status() != WL_CONNECTED) {
        wifiConnected = false;
        if (now - lastWifiAttempt > 5000) {
            lastWifiAttempt = now;
            connectWiFi();
        }
    } else {
        wifiConnected = true;
    }

    // Maintain MQTT
    if (wifiConnected) {
        if (!mqtt.connected()) {
            mqttConnected = false;
            connectMQTT();
        }
        mqtt.loop();
    }

    // Read ultrasonic sensors
    if (now - lastUSRead >= US_READ_INTERVAL) {
        lastUSRead = now;
        processUltrasonicReadings();
    }

    // Publish vehicle counts
    if (now - lastUSPublish >= US_PUBLISH_INTERVAL) {
        lastUSPublish = now;
        if (mqttConnected) {
            publishVehicleCounts();
        }
    }

    // Publish master status
    if (now - lastStatusPublish >= STATUS_INTERVAL) {
        lastStatusPublish = now;
        if (mqttConnected) {
            publishMasterStatus();
        }
    }

    // Blink status LED if disconnected
    if (!wifiConnected) {
        digitalWrite(STATUS_LED, (millis() / 500) % 2);
    }
}
