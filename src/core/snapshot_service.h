#pragma once

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "FreeRTOS.h"

#include "action_intent.h"
#include "decision_gate.h"
#include "world_state.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    WorldState          state;
    DecisionExplanation decision;
    ActionIntent        intent;
    uint32_t            timestamp_ms;
} SystemSnapshot;

void snapshot_service_start(UBaseType_t priority);

bool snapshot_serial_read_byte(uint8_t *byte);
bool snapshot_serial_tx_ready(void);
size_t snapshot_serial_write(const uint8_t *data, size_t length);

#ifdef __cplusplus
}
#endif
