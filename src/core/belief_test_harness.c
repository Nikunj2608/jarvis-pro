#include "belief_test_harness.h"

#ifdef BELIEF_TEST_MODE

#include "events.h"
#include "task.h"
#include "world_state.h"

#define HARNESS_STACK_SIZE   configMINIMAL_STACK_SIZE
#define HARNESS_PAUSE_MS     (10000U)
#define HARNESS_DECAY_MS     (30000U)

static StaticTask_t harness_tcb;
static StackType_t harness_stack[HARNESS_STACK_SIZE];
static TaskHandle_t harness_handle = NULL;

static void belief_test_task(void *params);
static void push_activity_event(ActivityMode mode, uint8_t confidence);
static void push_time_tick(void);
static uint32_t current_time_ms(void);

void belief_test_start(UBaseType_t priority)
{
    if (harness_handle != NULL) {
        return;
    }

    event_queue_init();

    harness_handle = xTaskCreateStatic(
        belief_test_task,
        "belief_test",
        HARNESS_STACK_SIZE,
        NULL,
        priority,
        harness_stack,
        &harness_tcb);
}

static void belief_test_task(void *params)
{
    (void)params;

    vTaskDelay(pdMS_TO_TICKS(2000U));

    for (;;) {
        push_time_tick();
        push_activity_event(ACTIVITY_MODE_FOCUS, 72U);

        vTaskDelay(pdMS_TO_TICKS(HARNESS_PAUSE_MS));
        push_time_tick();

        vTaskDelay(pdMS_TO_TICKS(HARNESS_PAUSE_MS));
        push_activity_event(ACTIVITY_MODE_DISTRACTED, 55U);

        vTaskDelay(pdMS_TO_TICKS(HARNESS_PAUSE_MS));
        push_time_tick();

        vTaskDelay(pdMS_TO_TICKS(HARNESS_DECAY_MS));
    }
}

static void push_activity_event(ActivityMode mode, uint8_t confidence)
{
    Event event = {
        .type = EV_ACTIVITY_CLUE,
        .ts = current_time_ms(),
        .value = (uint8_t)mode,
        .confidence = confidence,
    };

    (void)event_queue_push(&event);
}

static void push_time_tick(void)
{
    Event event = {
        .type = EV_TIME_TICK,
        .ts = current_time_ms(),
        .value = 0U,
        .confidence = 0U,
    };

    (void)event_queue_push(&event);
}

static uint32_t current_time_ms(void)
{
    TickType_t ticks = xTaskGetTickCount();
    return (uint32_t)ticks * (uint32_t)portTICK_PERIOD_MS;
}

#endif /* BELIEF_TEST_MODE */
