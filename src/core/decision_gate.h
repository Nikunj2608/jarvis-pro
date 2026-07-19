#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "FreeRTOS.h"
#include "world_state.h"  /* For UncertaintyCause */

#ifdef __cplusplus
extern "C" {
#endif

#define DECISION_BELIEF_THRESHOLD      (60U)
#define DECISION_FRESHNESS_THRESHOLD   (60U)

typedef struct {
    bool permitted;
    uint8_t belief;
    uint8_t freshness;
    UncertaintyCause cause;  /* WHY decision was uncertain */
    char reason[64];
} DecisionExplanation;

void decision_gate_start(UBaseType_t priority);
bool decision_gate_evaluate(DecisionExplanation *explanation);

#ifdef __cplusplus
}
#endif
