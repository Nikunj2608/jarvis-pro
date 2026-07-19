#include <Arduino.h>

// Set to 1 when DHT sensor is wired and verified.
#define ENABLE_DHT 1

#if ENABLE_DHT
#include <DHT.h>
#endif

// Stable JARVIS snapshot firmware for ESP32.
// Streams newline-delimited snapshots at 115200 and accepts simple advisory events.

#define SERIAL_BAUD 115200
#define DHTPIN 4
#define DHTTYPE DHT11

// Optional occupancy pins. Set to -1 to disable a pin.
#define PIR1_PIN 34
#define PIR2_PIN 35

#define SENSOR_INTERVAL_MS 2000UL
#define SNAPSHOT_INTERVAL_MS 1000UL
#define PRESENCE_TIMEOUT_MS 15000UL

#if ENABLE_DHT
DHT dht(DHTPIN, DHTTYPE);
#endif

struct State {
  float temperature = 0.0f;
  float humidity = 0.0f;
  bool roomOccupied = false;
  int activity = 0;     // 0 focus/idle, 1 distracted
  int belief = 30;      // 0..100
  int freshness = 0;    // 0..100
  uint32_t sessionId = 0;
  uint32_t lastGoodSensorMs = 0;
  uint32_t lastPresenceMs = 0;
};

State g;

static char cmdBuf[128];
static size_t cmdLen = 0;

void clampState() {
  if (g.belief < 0) g.belief = 0;
  if (g.belief > 100) g.belief = 100;
  if (g.freshness < 0) g.freshness = 0;
  if (g.freshness > 100) g.freshness = 100;
}

void sendSnapshot(uint32_t nowMs) {
  int occ = g.roomOccupied ? 1 : 0;
  // DEC/ACT_ID/ACT_VAL are included for compatibility with the laptop parser.
  Serial.printf(
    "SNAP|%lu|T:%.1f|H:%.1f|OCC:%d|ACT:%d|BEL:%d|FRESH:%d|SID:%lu|DEC:0|ACT_ID:0|ACT_VAL:0\n",
    (unsigned long)nowMs,
    g.temperature,
    g.humidity,
    occ,
    g.activity,
    g.belief,
    g.freshness,
    (unsigned long)g.sessionId
  );
}

void updateSensor(uint32_t nowMs) {
  static uint32_t lastSensorMs = 0;
  if ((nowMs - lastSensorMs) < SENSOR_INTERVAL_MS) {
    return;
  }
  lastSensorMs = nowMs;

#if ENABLE_DHT
  float t = dht.readTemperature();
  float h = dht.readHumidity();

  if (!isnan(t) && !isnan(h)) {
    g.temperature = t;
    g.humidity = h;
    g.lastGoodSensorMs = nowMs;
    g.freshness = 100;
  } else {
    // Slow decay on failed read; avoids stale high-confidence values.
    g.freshness = max(0, g.freshness - 10);
  }
#else
  // Keep stable default values when no sensor is wired.
  g.lastGoodSensorMs = nowMs;
  g.freshness = 100;
#endif
}

void updatePresence(uint32_t nowMs) {
  bool motionDetected = false;

  if (PIR1_PIN >= 0 && digitalRead(PIR1_PIN) == HIGH) {
    motionDetected = true;
  }
  if (PIR2_PIN >= 0 && digitalRead(PIR2_PIN) == HIGH) {
    motionDetected = true;
  }

  if (motionDetected) {
    g.roomOccupied = true;
    g.lastPresenceMs = nowMs;
  }

  if (g.roomOccupied && (nowMs - g.lastPresenceMs) > PRESENCE_TIMEOUT_MS) {
    g.roomOccupied = false;
  }
}

void applyActivityClue(int isDistracted, int confidence) {
  if (isDistracted > 0) {
    g.activity = 1;
    g.belief = max(g.belief, confidence);
  } else {
    g.activity = 0;
    g.belief = max(30, g.belief - 5);
  }
  clampState();
}

void handleCommand(const char *line) {
  if (line == nullptr || line[0] == '\0') {
    return;
  }

  // Legacy poll command support.
  if (strcmp(line, "GET_ENV") == 0) {
    Serial.printf("TEMP:%.1f,HUM:%.1f,OCC:%d\n", g.temperature, g.humidity, g.roomOccupied ? 1 : 0);
    return;
  }

  // Vision UI advisory format:
  // EV_ACTIVITY_CLUE,DISTRACTED,55
  if (strncmp(line, "EV_ACTIVITY_CLUE,", 17) == 0) {
    const char *payload = line + 17;
    const char *comma = strchr(payload, ',');
    if (!comma) return;

    int conf = atoi(comma + 1);
    bool distracted = (strncmp(payload, "DISTRACTED", 10) == 0);
    applyActivityClue(distracted ? 1 : 0, conf);
    return;
  }

  // Optional event format:
  // EVENT <type> <value> <confidence> <source>
  if (strncmp(line, "EVENT ", 6) == 0) {
    int type = -1;
    int value = 0;
    int confidence = 0;
    int parsed = sscanf(line, "EVENT %d %d %d", &type, &value, &confidence);
    if (parsed >= 3) {
      if (type == 2) { // ACTIVITY_CLUE
        applyActivityClue(value, confidence);
      } else if (type == 1) { // PRESENCE
        g.roomOccupied = (value != 0);
        if (g.roomOccupied) {
          g.lastPresenceMs = millis();
        }
      }
    }
    return;
  }
}

void processSerial() {
  while (Serial.available() > 0) {
    char c = (char)Serial.read();
    if (c == '\r') {
      continue;
    }
    if (c == '\n') {
      cmdBuf[cmdLen] = '\0';
      handleCommand(cmdBuf);
      cmdLen = 0;
      continue;
    }

    if (cmdLen < (sizeof(cmdBuf) - 1)) {
      cmdBuf[cmdLen++] = c;
    } else {
      // Buffer overflow protection; drop current line.
      cmdLen = 0;
    }
  }
}

void setup() {
  Serial.begin(SERIAL_BAUD);
#if ENABLE_DHT
  dht.begin();
#endif

  if (PIR1_PIN >= 0) {
    pinMode(PIR1_PIN, INPUT);
  }
  if (PIR2_PIN >= 0) {
    pinMode(PIR2_PIN, INPUT);
  }

  delay(200);
  g.sessionId = (uint32_t)esp_random();
  g.lastGoodSensorMs = millis();
  g.lastPresenceMs = millis();

  Serial.println("JARVIS-ESP32 READY");
}

void loop() {
  uint32_t nowMs = millis();

  processSerial();
  updateSensor(nowMs);
  updatePresence(nowMs);

  static uint32_t lastSnapMs = 0;
  if ((nowMs - lastSnapMs) >= SNAPSHOT_INTERVAL_MS) {
    lastSnapMs = nowMs;

    if (g.lastGoodSensorMs > 0) {
      uint32_t age = nowMs - g.lastGoodSensorMs;
      int decay = (int)(age / 1000UL);
      g.freshness = max(0, 100 - decay);
    }

    clampState();
    sendSnapshot(nowMs);
  }

  // Keep loop responsive to avoid watchdog starvation.
  delay(5);
}
