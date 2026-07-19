#pragma once

#include <stddef.h>

#include "action_intent.h"
#include "decision_gate.h"
#include "world_state.h"

#ifdef __cplusplus
extern "C" {
#endif

void llm_prepare_explanation(const WorldState *world,
                             const DecisionExplanation *decision,
                             const ActionIntent *intent,
                             char *out_buf,
                             size_t out_len);

#ifdef __cplusplus
}
#endif
