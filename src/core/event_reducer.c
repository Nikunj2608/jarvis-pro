#include "event_reducer.h"

#include "events.h"
#include "task.h"
#include "world_state.h"

static StaticTask_t reducer_tcb;
static StackType_t reducer_stack[configMINIMAL_STACK_SIZE];
static TaskHandle_t reducer_handle = NULL;

static void event_reducer_task(void *params);

void event_reducer_start(UBaseType_t priority)
{
    if (reducer_handle != NULL) {
        return;
    }

    event_queue_init();

    reducer_handle = xTaskCreateStatic(
        event_reducer_task,
        "event_reducer",
        configMINIMAL_STACK_SIZE,
        NULL,
        priority,
        reducer_stack,
        &reducer_tcb);
}

static void event_reducer_task(void *params)
{
    (void)params;

    Event event;

    for (;;) {
        if (event_queue_pop(&event, portMAX_DELAY)) {
            world_handle_event(&event);
        }
    }
}
