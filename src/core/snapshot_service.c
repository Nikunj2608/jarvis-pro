#include "snapshot_service.h"

#include "task.h"

#include <string.h>

#define SNAPSHOT_PERIOD_MS      (30000U)
#define SNAPSHOT_POLL_MS        (100U)
#define SNAPSHOT_HEADER_MARKER  (0xA5U)

#define SNAPSHOT_PAYLOAD_SIZE   (sizeof(SystemSnapshot))
#define SNAPSHOT_FRAME_SIZE     (1U + 2U + SNAPSHOT_PAYLOAD_SIZE + 2U)

static StaticTask_t snapshot_tcb;
static StackType_t snapshot_stack[configMINIMAL_STACK_SIZE];
static TaskHandle_t snapshot_handle = NULL;

static bool snapshot_pending = false;

static void snapshot_service_task(void *params);
static void poll_serial_request(void);
static bool transmit_snapshot(void);
static void build_snapshot(SystemSnapshot *snapshot);
static void build_frame(uint8_t *frame, const SystemSnapshot *snapshot);
static uint16_t snapshot_crc16(const uint8_t *data, size_t length);

void snapshot_service_start(UBaseType_t priority)
{
    if (snapshot_handle != NULL) {
        return;
    }

    snapshot_handle = xTaskCreateStatic(
        snapshot_service_task,
        "snapshot",
        configMINIMAL_STACK_SIZE,
        NULL,
        priority,
        snapshot_stack,
        &snapshot_tcb);
}

static void snapshot_service_task(void *params)
{
    (void)params;

    TickType_t last_poll = xTaskGetTickCount();
    TickType_t last_periodic = last_poll;

    for (;;) {
        vTaskDelayUntil(&last_poll, pdMS_TO_TICKS(SNAPSHOT_POLL_MS));
        poll_serial_request();

        TickType_t now = xTaskGetTickCount();
        if ((now - last_periodic) >= pdMS_TO_TICKS(SNAPSHOT_PERIOD_MS)) {
            snapshot_pending = true;
            last_periodic = now;
        }

        if (snapshot_pending) {
            if (transmit_snapshot()) {
                snapshot_pending = false;
            }
        }
    }
}

static void poll_serial_request(void)
{
    uint8_t byte;

    while (snapshot_serial_read_byte(&byte)) {
        (void)byte;
        snapshot_pending = true;
    }
}

static bool transmit_snapshot(void)
{
    if (!snapshot_serial_tx_ready()) {
        return false;
    }

    SystemSnapshot snapshot;
    uint8_t frame[SNAPSHOT_FRAME_SIZE];

    build_snapshot(&snapshot);
    build_frame(frame, &snapshot);

    size_t written = snapshot_serial_write(frame, sizeof(frame));
    return written == sizeof(frame);
}

static void build_snapshot(SystemSnapshot *snapshot)
{
    if (snapshot == NULL) {
        return;
    }

    taskENTER_CRITICAL();
    snapshot->state = world;
    snapshot->decision = (DecisionExplanation){0};
    snapshot->intent = (ActionIntent){0};
    taskEXIT_CRITICAL();

    (void)decision_gate_evaluate(&snapshot->decision);
    (void)action_intent_evaluate(&snapshot->decision, &snapshot->intent);

    TickType_t ticks = xTaskGetTickCount();
    snapshot->timestamp_ms = (uint32_t)ticks * (uint32_t)portTICK_PERIOD_MS;
}

static void build_frame(uint8_t *frame, const SystemSnapshot *snapshot)
{
    if ((frame == NULL) || (snapshot == NULL)) {
        return;
    }

    frame[0] = SNAPSHOT_HEADER_MARKER;

    const uint16_t length = (uint16_t)SNAPSHOT_PAYLOAD_SIZE;
    frame[1] = (uint8_t)(length & 0xFFU);
    frame[2] = (uint8_t)((length >> 8) & 0xFFU);

    memcpy(&frame[3], snapshot, sizeof(SystemSnapshot));

    const uint16_t crc = snapshot_crc16(&frame[3], SNAPSHOT_PAYLOAD_SIZE);
    frame[3 + SNAPSHOT_PAYLOAD_SIZE] = (uint8_t)(crc & 0xFFU);
    frame[4 + SNAPSHOT_PAYLOAD_SIZE] = (uint8_t)((crc >> 8) & 0xFFU);
}

static uint16_t snapshot_crc16(const uint8_t *data, size_t length)
{
    uint16_t crc = 0xFFFFU;

    for (size_t i = 0; i < length; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        for (uint8_t bit = 0; bit < 8U; ++bit) {
            if ((crc & 0x8000U) != 0U) {
                crc = (uint16_t)((crc << 1) ^ 0x1021U);
            } else {
                crc <<= 1;
            }
        }
    }

    return crc;
}
