#include "ml_adapter.h"

#include "events.h"
#include "world_state.h"

#include "FreeRTOS.h"
#include "task.h"

#define ML_ADAPTER_INTERVAL_MS   (20000U)

static StaticTask_t ml_adapter_tcb;
static StackType_t ml_adapter_stack[configMINIMAL_STACK_SIZE];
static TaskHandle_t ml_adapter_handle = NULL;

static void ml_adapter_task(void *params);
static void emit_inference(const MLInference *inference);
static uint32_t adapter_now_ms(void);

void ml_adapter_start(UBaseType_t priority)
{
    if (ml_adapter_handle != NULL) {
        return;
    }

    event_queue_init();

    ml_adapter_handle = xTaskCreateStatic(
        ml_adapter_task,
        "ml_adapter",
        configMINIMAL_STACK_SIZE,
        NULL,
        priority,
        ml_adapter_stack,
        &ml_adapter_tcb);
}

static void ml_adapter_task(void *params)
{
    (void)params;

    TickType_t last_wake = xTaskGetTickCount();
    MLInference inference = { .label = ACTIVITY_MODE_FOCUS, .confidence = 70U };

    for (;;) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(ML_ADAPTER_INTERVAL_MS));

        emit_inference(&inference);

        if (inference.label == ACTIVITY_MODE_FOCUS) {
            inference.label = ACTIVITY_MODE_DISTRACTED;
            inference.confidence = 55U;
        } else {
            inference.label = ACTIVITY_MODE_FOCUS;
            inference.confidence = 72U;
        }
    }
}

static void emit_inference(const MLInference *inference)
{
    if (inference == NULL) {
        return;
    }

    Event event = {
        .type = EV_ACTIVITY_CLUE,
        .ts = adapter_now_ms(),
        .value = inference->label,
        .confidence = inference->confidence,
    };

    (void)event_queue_push(&event);
}

static uint32_t adapter_now_ms(void)
{
    TickType_t ticks = xTaskGetTickCount();
    return (uint32_t)ticks * (uint32_t)portTICK_PERIOD_MS;
}
