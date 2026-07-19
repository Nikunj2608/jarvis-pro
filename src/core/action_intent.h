#pragma once

#include <stdbool.h>
#include <stdint.h>

#include "FreeRTOS.h"

#include "decision_gate.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    ACTION_NONE = 0,
    ACTION_SUGGEST_BREAK,
    ACTION_REMIND_WATER,
    ACTION_SILENT_OBSERVE
} ActionId;

typedef struct {
    bool proposed;
    uint8_t action_id;
    char rationale[64];
} ActionIntent;

void action_intent_start(UBaseType_t priority);
bool action_intent_evaluate(const DecisionExplanation *decision,
                            ActionIntent *intent);

#ifdef __cplusplus
}
#endif
