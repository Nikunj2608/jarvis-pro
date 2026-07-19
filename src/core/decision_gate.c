#include "decision_gate.h"

#include "world_state.h"

#include "FreeRTOS.h"
#include "task.h"

#include <stdio.h>

#define DECISION_LOG_INTERVAL_MS   (45000U)

static StaticTask_t decision_gate_tcb;
static StackType_t decision_gate_stack[configMINIMAL_STACK_SIZE];
static TaskHandle_t decision_gate_handle = NULL;

static void decision_gate_task(void *params);
static void log_explanation(const DecisionExplanation *explanation);
static void make_reason(DecisionExplanation *explanation,
                        bool belief_ok,
                        bool freshness_ok);

void decision_gate_start(UBaseType_t priority)
{
    if (decision_gate_handle != NULL) {
        return;
    }

    decision_gate_handle = xTaskCreateStatic(
        decision_gate_task,
        "decision_gate",
        configMINIMAL_STACK_SIZE,
        NULL,
        priority,
        decision_gate_stack,
        &decision_gate_tcb);
}

bool decision_gate_evaluate(DecisionExplanation *explanation)
{
    if (explanation == NULL) {
        return false;
    }

    WorldState snapshot;

    taskENTER_CRITICAL();
    snapshot = world;
    taskEXIT_CRITICAL();

    explanation->belief = snapshot.confidence.belief;
    explanation->freshness = snapshot.confidence.freshness;
    explanation->cause = snapshot.confidence.cause;

    bool belief_ok = (snapshot.confidence.belief >= DECISION_BELIEF_THRESHOLD);
    bool freshness_ok = (snapshot.confidence.freshness >= DECISION_FRESHNESS_THRESHOLD);
    explanation->permitted = (belief_ok && freshness_ok);

    make_reason(explanation, belief_ok, freshness_ok);

    return true;
}

static void decision_gate_task(void *params)
{
    (void)params;

    TickType_t last_wake = xTaskGetTickCount();
    DecisionExplanation explanation;

    decision_gate_evaluate(&explanation);
    log_explanation(&explanation);

    for (;;) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(DECISION_LOG_INTERVAL_MS));
        decision_gate_evaluate(&explanation);
        log_explanation(&explanation);
    }
}

static void log_explanation(const DecisionExplanation *explanation)
{
    printf("Decision | permitted=%s | belief=%u | freshness=%u | %s\r\n",
           explanation->permitted ? "true" : "false",
           explanation->belief,
           explanation->freshness,
           explanation->reason);
}

static void make_reason(DecisionExplanation *explanation,
                        bool belief_ok,
                        bool freshness_ok)
{
    if (explanation == NULL) {
        return;
    }

    if (explanation->permitted) {
        (void)snprintf(explanation->reason,
                       sizeof(explanation->reason),
                       "Permitted: belief %u>=%u freshness %u>=%u",
                       explanation->belief,
                       DECISION_BELIEF_THRESHOLD,
                       explanation->freshness,
                       DECISION_FRESHNESS_THRESHOLD);
        return;
    }

    /* Include uncertainty cause in blocked reason */
    const char *cause_str = "unknown";
    switch (explanation->cause) {
        case UNCERTAINTY_STALE_DATA:
            cause_str = "stale data";
            break;
        case UNCERTAINTY_CONFLICTING_EVIDENCE:
            cause_str = "conflicting evidence";
            break;
        case UNCERTAINTY_LOW_SIGNAL:
            cause_str = "low signal";
            break;
        case UNCERTAINTY_UNKNOWN_CONTEXT:
            cause_str = "unknown context";
            break;
        default:
            break;
    }

    if (!belief_ok && !freshness_ok) {
        (void)snprintf(explanation->reason,
                       sizeof(explanation->reason),
                       "Blocked: belief %u<%u freshness %u<%u (%s)",
                       explanation->belief,
                       DECISION_BELIEF_THRESHOLD,
                       explanation->freshness,
                       DECISION_FRESHNESS_THRESHOLD,
                       cause_str);
    } else if (!belief_ok) {
        (void)snprintf(explanation->reason,
                       sizeof(explanation->reason),
                       "Belief too weak (%u<%u, %s) freshness %u",
                       explanation->belief,
                       DECISION_BELIEF_THRESHOLD,
                       cause_str,
                       explanation->freshness);
    } else {
        (void)snprintf(explanation->reason,
                       sizeof(explanation->reason),
                       "Belief strong (%u) but freshness %u<%u (%s)",
                       explanation->belief,
                       explanation->freshness,
                       DECISION_FRESHNESS_THRESHOLD,
                       cause_str);
    }
}
