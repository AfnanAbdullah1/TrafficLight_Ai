/*
 * ============================================================
 *  AI Hybrid Traffic Lights Control System
 *  ESP32-CAM Route Controller Firmware
 * ============================================================
 *  
 *  Each ESP32-CAM controls one route's traffic LEDs, reads
 *  a PIR sensor for pedestrian detection, and captures camera
 *  frames to send to the PC for AI-based density analysis.
 *
 *  CONFIGURATION: Change ROUTE_ID below for each ESP32-CAM
 *    Route 1 → #define ROUTE_ID 1
 *    Route 2 → #define ROUTE_ID 2
 *    Route 3 → #define ROUTE_ID 3
 * ============================================================
 */

// ==================== CONFIGURATION ====================
#define ROUTE_ID          1          // <<< CHANGE THIS PER BOARD (1, 2, or 3)

// WiFi Credentials
const char* WIFI_SSID     = "YOUR_WIFI_SSID";      // <<< CHANGE THIS
const char* WIFI_PASSWORD  = "YOUR_WIFI_PASSWORD";  // <<< CHANGE THIS

// MQTT Broker (your PC's IP)
const char* MQTT_SERVER    = "192.168.1.100";       // <<< CHANGE THIS
const int   MQTT_PORT      = 1883;

// AI Engine (Python Flask server on PC)
const char* AI_SERVER_IP   = "192.168.1.100";       // <<< CHANGE THIS
const int   AI_SERVER_PORT = 5000;

// ==================== PIN DEFINITIONS ====================
// ESP32-CAM safe GPIO pins for LED control
#define RED_PIN     12
#define YELLOW_PIN  13
#define GREEN_PIN   14
#define PIR_PIN     15

// Camera capture interval (ms)
#define CAMERA_INTERVAL    5000   // 5 seconds
#define STATUS_INTERVAL    2000   // 2 seconds
#define PIR_DEBOUNCE       3000   // 3 seconds debounce

// ==================== INCLUDES ====================
#include <WiFi.h>
#include <PubSubClient.h>
#include <HTTPClient.h>
#include "esp_camera.h"

// ==================== CAMERA PIN DEFINITIONS (AI Thinker) ====================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22

// ==================== MQTT TOPICS ====================
char topicCommand[40];
char topicTiming[40];
char topicMode[30];
char topicEmergency[30];
char topicStatus[40];
char topicPedestrian[40];
char clientId[30];

// ==================== GLOBAL STATE ====================
WiFiClient espClient;
PubSubClient mqtt(espClient);

// Current LED state
enum LedState { STATE_RED, STATE_YELLOW, STATE_GREEN, STATE_OFF };
LedState currentLedState = STATE_RED;

// Operating mode (received from server)
enum Mode { MODE_AUTO, MODE_MANUAL, MODE_EMERGENCY };
Mode currentMode = MODE_AUTO;

// Timing for local fallback sequence
unsigned long greenDuration = 5000;
unsigned long yellowDuration = 2000;
unsigned long redGapDuration = 3000;

// Timing trackers
unsigned long lastCameraCapture = 0;
unsigned long lastStatusPublish = 0;
unsigned long lastPirTrigger = 0;
bool pirTriggered = false;

// WiFi reconnect
unsigned long lastWifiAttempt = 0;
#define WIFI_RETRY_INTERVAL 5000

// ==================== LED CONTROL FUNCTIONS ====================

void setLed(LedState state) {
    currentLedState = state;
    switch (state) {
        case STATE_RED:
            digitalWrite(RED_PIN, HIGH);
            digitalWrite(YELLOW_PIN, LOW);
            digitalWrite(GREEN_PIN, LOW);
            break;
        case STATE_YELLOW:
            digitalWrite(RED_PIN, LOW);
            digitalWrite(YELLOW_PIN, HIGH);
            digitalWrite(GREEN_PIN, LOW);
            break;
        case STATE_GREEN:
            digitalWrite(RED_PIN, LOW);
            digitalWrite(YELLOW_PIN, LOW);
            digitalWrite(GREEN_PIN, HIGH);
            break;
        case STATE_OFF:
            digitalWrite(RED_PIN, LOW);
            digitalWrite(YELLOW_PIN, LOW);
            digitalWrite(GREEN_PIN, LOW);
            break;
    }
}

const char* ledStateToString(LedState state) {
    switch (state) {
        case STATE_RED:    return "red";
        case STATE_YELLOW: return "yellow";
        case STATE_GREEN:  return "green";
        case STATE_OFF:    return "off";
        default:           return "unknown";
    }
}

// ==================== CAMERA FUNCTIONS ====================

bool initCamera() {
    camera_config_t config;
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer   = LEDC_TIMER_0;
    config.pin_d0       = Y2_GPIO_NUM;
    config.pin_d1       = Y3_GPIO_NUM;
    config.pin_d2       = Y4_GPIO_NUM;
    config.pin_d3       = Y5_GPIO_NUM;
    config.pin_d4       = Y6_GPIO_NUM;
    config.pin_d5       = Y7_GPIO_NUM;
    config.pin_d6       = Y8_GPIO_NUM;
    config.pin_d7       = Y9_GPIO_NUM;
    config.pin_xclk     = XCLK_GPIO_NUM;
    config.pin_pclk     = PCLK_GPIO_NUM;
    config.pin_vsync    = VSYNC_GPIO_NUM;
    config.pin_href     = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn     = PWDN_GPIO_NUM;
    config.pin_reset    = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;

    // Use lower resolution for faster transmission
    config.frame_size   = FRAMESIZE_QVGA;  // 320x240
    config.jpeg_quality = 12;
    config.fb_count     = 1;

    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK) {
        Serial.printf("[CAM] Init failed: 0x%x\n", err);
        return false;
    }
    Serial.println("[CAM] Camera initialized successfully");
    return true;
}

void captureAndSendFrame() {
    camera_fb_t *fb = esp_camera_fb_get();
    if (!fb) {
        Serial.println("[CAM] Capture failed");
        return;
    }

    // Send JPEG to AI engine via HTTP POST
    HTTPClient http;
    char url[80];
    snprintf(url, sizeof(url), "http://%s:%d/upload/route%d", AI_SERVER_IP, AI_SERVER_PORT, ROUTE_ID);

    http.begin(url);
    http.addHeader("Content-Type", "image/jpeg");
    int httpCode = http.POST(fb->buf, fb->len);

    if (httpCode == 200) {
        Serial.printf("[CAM] Frame sent (%d bytes), response: %d\n", fb->len, httpCode);
    } else {
        Serial.printf("[CAM] Send failed, HTTP code: %d\n", httpCode);
    }

    http.end();
    esp_camera_fb_return(fb);
}

// ==================== WiFi FUNCTIONS ====================

void connectWiFi() {
    if (WiFi.status() == WL_CONNECTED) return;

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
        Serial.printf("\n[WiFi] Connected! IP: %s\n", WiFi.localIP().toString().c_str());
    } else {
        Serial.println("\n[WiFi] Connection failed, will retry...");
    }
}

// ==================== MQTT FUNCTIONS ====================

void buildTopics() {
    snprintf(topicCommand,    sizeof(topicCommand),    "traffic/route/%d/command", ROUTE_ID);
    snprintf(topicTiming,     sizeof(topicTiming),     "traffic/route/%d/timing",  ROUTE_ID);
    snprintf(topicStatus,     sizeof(topicStatus),     "traffic/route/%d/status",  ROUTE_ID);
    snprintf(topicPedestrian, sizeof(topicPedestrian), "traffic/pedestrian/%d",    ROUTE_ID);
    snprintf(topicMode,       sizeof(topicMode),       "traffic/mode");
    snprintf(topicEmergency,  sizeof(topicEmergency),  "traffic/emergency");
    snprintf(clientId,        sizeof(clientId),         "esp32cam_route%d",        ROUTE_ID);
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
    // Null-terminate the payload
    char message[256];
    int len = min((unsigned int)255, length);
    memcpy(message, payload, len);
    message[len] = '\0';

    Serial.printf("[MQTT] Topic: %s | Message: %s\n", topic, message);

    // Handle route command: "red", "yellow", "green", "off"
    if (strcmp(topic, topicCommand) == 0) {
        if (strcmp(message, "red") == 0)         setLed(STATE_RED);
        else if (strcmp(message, "yellow") == 0) setLed(STATE_YELLOW);
        else if (strcmp(message, "green") == 0)  setLed(STATE_GREEN);
        else if (strcmp(message, "off") == 0)    setLed(STATE_OFF);
        
        // Immediately publish updated status
        publishStatus();
    }
    // Handle timing update: green duration in ms (e.g., "10000")
    else if (strcmp(topic, topicTiming) == 0) {
        unsigned long newTiming = atol(message);
        if (newTiming >= 1000 && newTiming <= 60000) {
            greenDuration = newTiming;
            Serial.printf("[TIMING] Green duration updated: %lu ms\n", greenDuration);
        }
    }
    // Handle mode change: "auto", "manual", "emergency"
    else if (strcmp(topic, topicMode) == 0) {
        if (strcmp(message, "auto") == 0)           currentMode = MODE_AUTO;
        else if (strcmp(message, "manual") == 0)     currentMode = MODE_MANUAL;
        else if (strcmp(message, "emergency") == 0)  currentMode = MODE_EMERGENCY;
        Serial.printf("[MODE] Changed to: %s\n", message);
    }
    // Handle emergency: "route:X:green" or "route:X:red"
    else if (strcmp(topic, topicEmergency) == 0) {
        // Parse emergency command - format: "route:N:state"
        int emergencyRoute;
        char emergencyState[10];
        if (sscanf(message, "route:%d:%s", &emergencyRoute, emergencyState) == 2) {
            if (emergencyRoute == ROUTE_ID) {
                if (strcmp(emergencyState, "green") == 0) setLed(STATE_GREEN);
                else setLed(STATE_RED);
            } else {
                // Not our route — go RED for safety
                setLed(STATE_RED);
            }
            publishStatus();
        }
    }
}

void connectMQTT() {
    if (mqtt.connected()) return;

    Serial.printf("[MQTT] Connecting as %s...\n", clientId);

    if (mqtt.connect(clientId)) {
        Serial.println("[MQTT] Connected!");

        // Subscribe to relevant topics
        mqtt.subscribe(topicCommand);
        mqtt.subscribe(topicTiming);
        mqtt.subscribe(topicMode);
        mqtt.subscribe(topicEmergency);

        Serial.println("[MQTT] Subscribed to all topics");

        // Announce ourselves
        publishStatus();
    } else {
        Serial.printf("[MQTT] Failed, rc=%d. Will retry...\n", mqtt.state());
    }
}

void publishStatus() {
    char statusMsg[100];
    snprintf(statusMsg, sizeof(statusMsg),
        "{\"route\":%d,\"state\":\"%s\",\"mode\":\"%s\",\"green_ms\":%lu}",
        ROUTE_ID,
        ledStateToString(currentLedState),
        currentMode == MODE_AUTO ? "auto" : (currentMode == MODE_MANUAL ? "manual" : "emergency"),
        greenDuration
    );
    mqtt.publish(topicStatus, statusMsg);
}

// ==================== PIR HANDLER ====================

void checkPIR() {
    unsigned long now = millis();
    if (digitalRead(PIR_PIN) == HIGH && (now - lastPirTrigger > PIR_DEBOUNCE)) {
        lastPirTrigger = now;
        pirTriggered = true;

        Serial.printf("[PIR] Pedestrian detected on Route %d!\n", ROUTE_ID);

        char pirMsg[60];
        snprintf(pirMsg, sizeof(pirMsg), "{\"route\":%d,\"detected\":true}", ROUTE_ID);
        mqtt.publish(topicPedestrian, pirMsg);
    }
}

// ==================== SETUP ====================

void setup() {
    Serial.begin(115200);
    Serial.printf("\n\n========================================\n");
    Serial.printf("  AI Traffic Light - Route %d (ESP32-CAM)\n", ROUTE_ID);
    Serial.printf("========================================\n\n");

    // Initialize LED pins
    pinMode(RED_PIN, OUTPUT);
    pinMode(YELLOW_PIN, OUTPUT);
    pinMode(GREEN_PIN, OUTPUT);
    pinMode(PIR_PIN, INPUT);

    // Start with RED for safety
    setLed(STATE_RED);

    // Build MQTT topic strings
    buildTopics();

    // Initialize camera
    if (!initCamera()) {
        Serial.println("[ERROR] Camera init failed! Continuing without camera...");
    }

    // Connect WiFi
    connectWiFi();

    // Setup MQTT
    mqtt.setServer(MQTT_SERVER, MQTT_PORT);
    mqtt.setCallback(mqttCallback);
    mqtt.setBufferSize(512);

    connectMQTT();

    Serial.println("[SETUP] Initialization complete!\n");
}

// ==================== MAIN LOOP ====================

void loop() {
    unsigned long now = millis();

    // Maintain WiFi connection
    if (WiFi.status() != WL_CONNECTED) {
        if (now - lastWifiAttempt > WIFI_RETRY_INTERVAL) {
            lastWifiAttempt = now;
            connectWiFi();
        }
    }

    // Maintain MQTT connection
    if (WiFi.status() == WL_CONNECTED) {
        if (!mqtt.connected()) {
            connectMQTT();
        }
        mqtt.loop();
    }

    // Check PIR sensor
    checkPIR();

    // Capture and send camera frame periodically
    if (now - lastCameraCapture >= CAMERA_INTERVAL) {
        lastCameraCapture = now;
        if (WiFi.status() == WL_CONNECTED) {
            captureAndSendFrame();
        }
    }

    // Publish status periodically
    if (now - lastStatusPublish >= STATUS_INTERVAL) {
        lastStatusPublish = now;
        if (mqtt.connected()) {
            publishStatus();
        }
    }
}
