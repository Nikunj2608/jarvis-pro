#include "belief_logger.h"

#include "world_state.h"

#include "FreeRTOS.h"
#include "task.h"

#include <inttypes.h>
#include <stddef.h>
#include <stdio.h>

#define BELIEF_LOG_INTERVAL_MS   (30000U)
#define TIMESTAMP_BUFFER_SIZE    (8U)

static StaticTask_t belief_logger_tcb;
static StackType_t belief_logger_stack[configMINIMAL_STACK_SIZE];
static TaskHandle_t belief_logger_handle = NULL;

static void belief_logger_task(void *params);
static void capture_snapshot(WorldState *snapshot);
static void format_timestamp(uint32_t ms, char *buffer, size_t length);
static void log_snapshot(const WorldState *snapshot);

void belief_logger_start(UBaseType_t priority)
{
    if (belief_logger_handle != NULL) {
        return;
    }

    belief_logger_handle = xTaskCreateStatic(
        belief_logger_task,
        "belief_log",
        configMINIMAL_STACK_SIZE,
        NULL,
        priority,
        belief_logger_stack,
        &belief_logger_tcb);
}

static void belief_logger_task(void *params)
{
    (void)params;

    TickType_t last_wake = xTaskGetTickCount();
    WorldState snapshot;

    capture_snapshot(&snapshot);
    log_snapshot(&snapshot);

    for (;;) {
        vTaskDelayUntil(&last_wake, pdMS_TO_TICKS(BELIEF_LOG_INTERVAL_MS));
        capture_snapshot(&snapshot);
        log_snapshot(&snapshot);
    }
}

static void capture_snapshot(WorldState *snapshot)
{
    taskENTER_CRITICAL();
    *snapshot = world;
    taskEXIT_CRITICAL();
}

static void format_timestamp(uint32_t ms, char *buffer, size_t length)
{
    uint32_t total_seconds = ms / 1000U;
    uint32_t hours = (total_seconds / 3600U) % 24U;
    uint32_t minutes = (total_seconds / 60U) % 60U;

    (void)snprintf(buffer, length, "%02" PRIu32 ":%02" PRIu32, hours, minutes);
}

static void log_snapshot(const WorldState *snapshot)
{
    char timestamp[TIMESTAMP_BUFFER_SIZE];
    format_timestamp(snapshot->time.last_sync_ms, timestamp, sizeof(timestamp));

    printf("[%s] %s | %s | belief=%u | freshness=%u\r\n",
           timestamp,
           world_day_segment_str(snapshot->time.segment),
           world_activity_mode_str(snapshot->activity.mode),
           snapshot->confidence.belief,
           snapshot->confidence.freshness);
}
