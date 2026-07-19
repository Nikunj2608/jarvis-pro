#include "action_intent.h"

#include "world_state.h"

#include "FreeRTOS.h"
#include "task.h"

#include <inttypes.h>
#include <stdio.h>

#define INTENT_LOG_INTERVAL_MS   (45000U)
#define FOCUS_LONG_MS            (45U * 60U * 1000U)

static StaticTask_t action_intent_tcb;
static StackType_t action_intent_stack[configMINIMAL_STACK_SIZE];
static TaskHandle_t action_intent_handle = NULL;

static void action_intent_task(void *params);
static ActionId infer_action(const WorldState *state);
static void format_rationale(ActionIntent *intent,
                             const WorldState *state);
static void log_intent(const ActionIntent *intent);

void action_intent_start(UBaseType_t priority)
{
    if (action_intent_handle != NULL) {
        return;
    }

    action_intent_handle = xTaskCreateStatic(
        action_intent_task,
        "action_intent",
        configMINIMAL_STACK_SIZE,
        NULL,
        priority,
        action_intent_stack,
        &action_intent_tcb);
}

bool action_intent_evaluate(const DecisionExplanation *decision,
                            ActionIntent *intent)
{
    if ((decision == NULL) || (intent == NULL)) {
        return false;
    }

    intent->proposed = false;
    intent->action_id = ACTION_NONE;
    intent->rationale[0] = '\0';

    if (!decision->permitted) {
        return true;
    }

    WorldState snapshot;
    taskENTER_CRITICAL();
    snapshot = world;
    taskEXIT_CRITICAL();

    ActionId action = infer_action(&snapshot);

    if (action == ACTION_NONE) {
        (void)snprintf(intent->rationale,
                       sizeof(intent->rationale),
                       "No intent: state=%s freshness=%u",
                       world_activity_mode_str(snapshot.activity.mode),
                       snapshot.confidence.freshness);
        return true;
    }

    intent->proposed = true;
    intent->action_id = (uint8_t)action;
    format_rationale(intent, &snapshot);
    return true;
}

static void action_intent_task(void *params)
{
    (void)params;

    TickType_t last_wake = xTaskGetTickCount();
    DecisionExplanation decision;
    ActionIntent intent;

    decision_gate_evaluate(&decision);
    action_intent_evaluate(&decision, &intent);
    log_intent(&intent);

    for (;;) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(INTENT_LOG_INTERVAL_MS));
        decision_gate_evaluate(&decision);
        action_intent_evaluate(&decision, &intent);
        log_intent(&intent);
    }
}

static ActionId infer_action(const WorldState *state)
{
    if (state == NULL) {
        return ACTION_NONE;
    }

    uint32_t focus_duration = 0U;
    if (state->activity.mode == ACTIVITY_MODE_FOCUS) {
        if (state->time.last_sync_ms >= state->activity.mode_start_ms) {
            focus_duration = state->time.last_sync_ms - state->activity.mode_start_ms;
        }
    }

    if ((state->activity.mode == ACTIVITY_MODE_FOCUS) &&
        (focus_duration >= FOCUS_LONG_MS) &&
        (state->time.segment == DAY_SEGMENT_NIGHT)) {
        return ACTION_SUGGEST_BREAK;
    }

    if ((state->activity.mode == ACTIVITY_MODE_FOCUS) &&
        (state->time.segment == DAY_SEGMENT_AFTERNOON)) {
        return ACTION_REMIND_WATER;
    }

    if (state->activity.mode == ACTIVITY_MODE_DISTRACTED) {
        return ACTION_SILENT_OBSERVE;
    }

    return ACTION_NONE;
}

static void format_rationale(ActionIntent *intent,
                             const WorldState *state)
{
    if ((intent == NULL) || (state == NULL)) {
        return;
    }

    switch ((ActionId)intent->action_id) {
    case ACTION_SUGGEST_BREAK: {
        uint32_t minutes = 0U;
        if (state->time.last_sync_ms >= state->activity.mode_start_ms) {
            minutes = (state->time.last_sync_ms - state->activity.mode_start_ms) / 60000U;
        }
        (void)snprintf(intent->rationale,
                       sizeof(intent->rationale),
                       "Suggest break: focus %" PRIu32 " min during %s",
                       minutes,
                       world_day_segment_str(state->time.segment));
        break;
    }
    case ACTION_REMIND_WATER:
        (void)snprintf(intent->rationale,
                       sizeof(intent->rationale),
                       "Remind hydration: focus during %s",
                       world_day_segment_str(state->time.segment));
        break;
    case ACTION_SILENT_OBSERVE:
        (void)snprintf(intent->rationale,
                       sizeof(intent->rationale),
                       "Observe: distracted mode, waiting for stability");
        break;
    default:
        intent->rationale[0] = '\0';
        break;
    }
}

static void log_intent(const ActionIntent *intent)
{
    printf("Intent | proposed=%s | action=%u | %s\r\n",
           intent->proposed ? "true" : "false",
           intent->action_id,
           intent->rationale);
}
