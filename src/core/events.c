#include "events.h"

#include "queue.h"

static StaticQueue_t event_queue_struct;
static uint8_t event_queue_storage[EVENT_QUEUE_LENGTH * sizeof(Event)];
static QueueHandle_t event_queue_handle = NULL;

void event_queue_init(void)
{
    if (event_queue_handle != NULL) {
        return;
    }

    event_queue_handle = xQueueCreateStatic(
        EVENT_QUEUE_LENGTH,
        sizeof(Event),
        event_queue_storage,
        &event_queue_struct);
}

bool event_queue_push(const Event *event)
{
    if ((event_queue_handle == NULL) || (event == NULL)) {
        return false;
    }

    return xQueueSend(event_queue_handle, event, 0U) == pdPASS;
}

bool event_queue_pop(Event *event, TickType_t wait_ticks)
{
    if ((event_queue_handle == NULL) || (event == NULL)) {
        return false;
    }

    return xQueueReceive(event_queue_handle, event, wait_ticks) == pdPASS;
}
