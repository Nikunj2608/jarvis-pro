/**
 * JARVIS ESP32 Main - Real-Time Intelligence Core
 * ===============================================
 * 
 * Architecture:
 *   Event Queue → Event Reducer → World State → Decision Gate → Action Intent
 *                                      ↓
 *                               Snapshot Service
 *                                      ↓
 *                                  UART (Laptop)
 * 
 * CRITICAL PRINCIPLES:
 * - This C++ core is the AUTHORITATIVE intelligence
 * - All state changes happen via events
 * - All decisions happen in decision_gate.c
 * - Laptop provides evidence only (events)
 * - Laptop receives snapshots only (read-only state)
 */

#include "Arduino.h"
#include "FreeRTOS.h"
#include "task.h"

// Core modules
#include "core/events.h"
#include "core/event_reducer.h"
#include "core/world_state.h"
#include "core/decision_gate.h"
#include "core/action_intent.h"
#include "core/snapshot_service.h"
#include "core/belief_logger.h"

// Configuration
#define UART_BAUD_RATE          115200
#define MAIN_TASK_PRIORITY      (tskIDLE_PRIORITY + 1)
#define REDUCER_PRIORITY        (tskIDLE_PRIORITY + 3)
#define DECISION_PRIORITY       (tskIDLE_PRIORITY + 2)
#define ACTION_PRIORITY         (tskIDLE_PRIORITY + 2)
#define SNAPSHOT_PRIORITY       (tskIDLE_PRIORITY + 1)

// Time tick generation
#define TIME_TICK_INTERVAL_MS   1000U

// Serial input buffer
#define SERIAL_BUFFER_SIZE      128
static char serial_buffer[SERIAL_BUFFER_SIZE];
static size_t serial_buffer_len = 0;

// Function prototypes
static void main_task(void *params);
static void time_tick_task(void *params);
static void serial_input_task(void *params);
static void process_serial_command(const char *cmd);
static bool parse_event_command(const char *cmd, Event *event);

// Task handles
static TaskHandle_t main_task_handle = NULL;
static TaskHandle_t tick_task_handle = NULL;
static TaskHandle_t serial_task_handle = NULL;

// Task stacks
static StackType_t main_stack[configMINIMAL_STACK_SIZE];
static StaticTask_t main_tcb;
static StackType_t tick_stack[configMINIMAL_STACK_SIZE];
static StaticTask_t tick_tcb;
static StackType_t serial_stack[configMINIMAL_STACK_SIZE * 2];
static StaticTask_t serial_tcb;

/**
 * Arduino setup - Initialize hardware and start FreeRTOS tasks
 */
void setup()
{
    // Initialize serial
    Serial.begin(UART_BAUD_RATE);
    while (!Serial && millis() < 3000) {
        ; // Wait for serial connection (max 3 seconds)
    }
    
    Serial.println("\n========================================");
    Serial.println("JARVIS ESP32 Core - Real-Time Intelligence");
    Serial.println("========================================\n");
    
    // Initialize core subsystems
    Serial.println("[Init] Event queue...");
    event_queue_init();
    
    Serial.println("[Init] Belief logger...");
    belief_logger_init();
    
    // Start FreeRTOS tasks
    Serial.println("[Init] Starting tasks...");
    
    // Event reducer (highest priority - processes events)
    event_reducer_start(REDUCER_PRIORITY);
    Serial.println("  [✓] Event Reducer");
    
    // Decision gate
    decision_gate_start(DECISION_PRIORITY);
    Serial.println("  [✓] Decision Gate");
    
    // Action intent
    action_intent_start(ACTION_PRIORITY);
    Serial.println("  [✓] Action Intent");
    
    // Snapshot service (lowest priority - for laptop interface)
    snapshot_service_start(SNAPSHOT_PRIORITY);
    Serial.println("  [✓] Snapshot Service");
    
    // Time tick generator
    tick_task_handle = xTaskCreateStatic(
        time_tick_task,
        "time_tick",
        configMINIMAL_STACK_SIZE,
        NULL,
        MAIN_TASK_PRIORITY,
        tick_stack,
        &tick_tcb);
    Serial.println("  [✓] Time Tick Generator");
    
    // Serial input processor
    serial_task_handle = xTaskCreateStatic(
        serial_input_task,
        "serial_input",
        configMINIMAL_STACK_SIZE * 2,
        NULL,
        MAIN_TASK_PRIORITY,
        serial_stack,
        &serial_tcb);
    Serial.println("  [✓] Serial Input Processor");
    
    // Main monitoring task
    main_task_handle = xTaskCreateStatic(
        main_task,
        "main",
        configMINIMAL_STACK_SIZE,
        NULL,
        MAIN_TASK_PRIORITY,
        main_stack,
        &main_tcb);
    Serial.println("  [✓] Main Monitor");
    
    Serial.println("\n[System] All tasks started");
    Serial.println("[System] Intelligence core active");
    Serial.println("[System] Waiting for events...\n");
    
    // Start FreeRTOS scheduler (never returns)
    vTaskStartScheduler();
    
    // Should never reach here
    Serial.println("[FATAL] Scheduler failed to start!");
    while (1) {
        delay(1000);
    }
}

/**
 * Arduino loop - Not used (FreeRTOS takes over)
 */
void loop()
{
    // Empty - FreeRTOS scheduler handles everything
}

/**
 * Main monitoring task
 * Logs system state periodically
 */
static void main_task(void *params)
{
    (void)params;
    
    TickType_t last_wake = xTaskGetTickCount();
    const TickType_t period = pdMS_TO_TICKS(10000); // 10 second logging
    
    for (;;) {
        vTaskDelayUntil(&last_wake, period);
        
        // Log current state
        extern WorldState world; // Defined in world_state.c
        
        Serial.println("\n--- System State ---");
        Serial.print("Activity: ");
        Serial.println(world_activity_mode_str(world.activity.mode));
        Serial.print("Belief: ");
        Serial.print(world.confidence.belief);
        Serial.println("/100");
        Serial.print("Freshness: ");
        Serial.print(world.confidence.freshness);
        Serial.println("/100");
        Serial.print("Day Segment: ");
        Serial.println(world_day_segment_str(world.time.segment));
        Serial.print("Occupied: ");
        Serial.println(world.physical.occupied ? "Yes" : "No");
        Serial.println("-------------------\n");
    }
}

/**
 * Time tick generator
 * Emits EV_TIME_TICK events periodically for freshness decay
 */
static void time_tick_task(void *params)
{
    (void)params;
    
    TickType_t last_wake = xTaskGetTickCount();
    const TickType_t period = pdMS_TO_TICKS(TIME_TICK_INTERVAL_MS);
    
    for (;;) {
        vTaskDelayUntil(&last_wake, period);
        
        Event tick_event = {
            .type = EV_TIME_TICK,
            .ts = (uint32_t)millis(),
            .value = 0,
            .confidence = 100,
            .source = SOURCE_TIME_INFERENCE
        };
        
        if (!event_queue_push(&tick_event)) {
            Serial.println("[Warning] Time tick dropped (queue full)");
        }
    }
}

/**
 * Serial input processor
 * Receives commands from laptop and converts to events
 */
static void serial_input_task(void *params)
{
    (void)params;
    
    for (;;) {
        // Read available serial data
        while (Serial.available() > 0) {
            char c = Serial.read();
            
            // Handle line endings
            if (c == '\n' || c == '\r') {
                if (serial_buffer_len > 0) {
                    serial_buffer[serial_buffer_len] = '\0';
                    process_serial_command(serial_buffer);
                    serial_buffer_len = 0;
                }
            }
            // Buffer character
            else if (serial_buffer_len < (SERIAL_BUFFER_SIZE - 1)) {
                serial_buffer[serial_buffer_len++] = c;
            }
            // Buffer overflow - reset
            else {
                Serial.println("[Error] Serial buffer overflow");
                serial_buffer_len = 0;
            }
        }
        
        // Yield to other tasks
        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

/**
 * Process serial command from laptop
 * Commands are converted to events for the core
 */
static void process_serial_command(const char *cmd)
{
    Event event;
    
    // Try to parse as event command
    if (parse_event_command(cmd, &event)) {
        if (event_queue_push(&event)) {
            Serial.print("[Event] Received: type=");
            Serial.print(event.type);
            Serial.print(" value=");
            Serial.print(event.value);
            Serial.print(" confidence=");
            Serial.println(event.confidence);
        } else {
            Serial.println("[Error] Event queue full - dropped event");
        }
        return;
    }
    
    // Handle special commands
    if (strcmp(cmd, "STATUS") == 0) {
        // Trigger immediate snapshot
        // (snapshot_service will handle this via request polling)
        Serial.println("[Command] Status request received");
        return;
    }
    
    if (strcmp(cmd, "RESET") == 0) {
        Serial.println("[Command] Reset requested - rebooting...");
        delay(100);
        ESP.restart();
        return;
    }
    
    Serial.print("[Error] Unknown command: ");
    Serial.println(cmd);
}

/**
 * Parse event command from laptop
 * Format: "EVENT <type> <value> <confidence> <source>"
 */
static bool parse_event_command(const char *cmd, Event *event)
{
    if (strncmp(cmd, "EVENT ", 6) != 0) {
        return false;
    }
    
    int type, value, confidence, source = 0;
    int parsed = sscanf(cmd + 6, "%d %d %d %d", &type, &value, &confidence, &source);
    
    // Support old protocol (3 args) and new protocol (4 args)
    if (parsed < 3) {
        return false;
    }
    
    // Validate ranges
    if (type < 0 || type > EV_FAULT) {
        Serial.println("[Error] Invalid event type");
        return false;
    }
    
    if (value < 0 || value > 255) {
        Serial.println("[Error] Invalid event value");
        return false;
    }
    
    if (confidence < 0 || confidence > 100) {
        Serial.println("[Error] Invalid confidence");
        return false;
    }
    
    if (source < 0 || source > SOURCE_TIME_INFERENCE) {
        source = SOURCE_VISION_LAPTOP;  // Default fallback
    }
    
    // Build event
    event->type = (EventType)type;
    event->ts = (uint32_t)millis();
    event->value = (uint8_t)value;
    event->confidence = (uint8_t)confidence;
    event->source = (EvidenceSource)source;
    
    return true;
}

/**
 * Snapshot service serial interface implementation
 * Required by snapshot_service.c
 */
bool snapshot_serial_read_byte(uint8_t *byte)
{
    if (Serial.available() > 0) {
        *byte = Serial.read();
        return true;
    }
    return false;
}

bool snapshot_serial_tx_ready(void)
{
    return Serial.availableForWrite() > 0;
}

size_t snapshot_serial_write(const uint8_t *data, size_t length)
{
    return Serial.write(data, length);
}
