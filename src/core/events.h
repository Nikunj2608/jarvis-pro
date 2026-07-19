#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "FreeRTOS.h"

#ifdef __cplusplus
extern "C" {
#endif

#define EVENT_QUEUE_LENGTH 16U

typedef enum {
    EV_TIME_TICK = 0,
    EV_PRESENCE,
    EV_ACTIVITY_CLUE,
    EV_OVERRIDE,
    EV_ENV_UPDATE,
    EV_MODE_CONFIRM,
    EV_SESSION_START,  /* New session detected */
    EV_FAULT
} EventType;

// Evidence source tracking for belief fusion
typedef enum {
    SOURCE_MOTION_PIR = 0,   /* PIR sensor (high reliability) */
    SOURCE_VISION_LAPTOP,    /* Webcam face detection (medium reliability) */
    SOURCE_VOICE_ACTIVITY,   /* Voice detection (low reliability) */
    SOURCE_MANUAL_OVERRIDE,  /* User explicit command (maximum reliability) */
    SOURCE_ENV_SENSOR,       /* BME280 readings (high reliability) */
    SOURCE_TIME_INFERENCE    /* Clock-based inference (low reliability) */
} EvidenceSource;

typedef struct {
    EventType type;
    uint32_t ts;
    uint8_t value;
    uint8_t confidence;
    EvidenceSource source;  /* WHO provided this evidence */
} Event;

void event_queue_init(void);
bool event_queue_push(const Event *event);
bool event_queue_pop(Event *event, TickType_t wait_ticks);

#ifdef __cplusplus
}
#endif
