#pragma once

#include <stdbool.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    DAY_SEGMENT_NIGHT = 0,
    DAY_SEGMENT_MORNING,
    DAY_SEGMENT_AFTERNOON,
    DAY_SEGMENT_EVENING
} DaySegment;

typedef struct {
    DaySegment segment;
    uint32_t last_sync_ms;
} TemporalState;

typedef struct {
    bool occupied;
    uint32_t last_motion_ms;
} PhysicalState;

typedef enum {
    ACTIVITY_MODE_IDLE = 0,
    ACTIVITY_MODE_FOCUS,
    ACTIVITY_MODE_DISTRACTED,
    ACTIVITY_MODE_OVERRIDE
} ActivityMode;

typedef struct {
    ActivityMode mode;
    uint32_t mode_start_ms;
} ActivityState;

typedef enum {
    UNCERTAINTY_NONE = 0,
    UNCERTAINTY_STALE_DATA,
    UNCERTAINTY_CONFLICTING_EVIDENCE,
    UNCERTAINTY_LOW_SIGNAL,
    UNCERTAINTY_UNKNOWN_CONTEXT
} UncertaintyCause;

typedef struct {
    uint8_t belief;           /* confidence in current belief */
    uint8_t freshness;        /* decay-driven permissibility */
    UncertaintyCause cause;   /* WHY we're uncertain */
} ConfidenceState;

// Session tracking for multi-user identity (without biometrics)
typedef struct {
    uint8_t active_session_id;    /* increments on arrival */
    uint32_t session_start_ms;     /* when current session began */
    uint16_t session_count_today;  /* how many sessions today */
} SessionState;

// Temporal memory: patterns, habits, statistics
typedef struct {
    uint16_t focus_minutes_today;      /* accumulated deep work time */
    uint16_t distraction_count_today;  /* interruption tally */
    uint8_t typical_focus_hour;        /* hour of day (0-23) with best focus */
    uint8_t typical_distraction_hour;  /* hour with most distractions */
} HabitStats;

typedef struct {
    TemporalState time;
    PhysicalState physical;
    ActivityState activity;
    ConfidenceState confidence;
    SessionState session;
    HabitStats habits;
} WorldState;

extern WorldState world;

const char *world_day_segment_str(DaySegment segment);
const char *world_activity_mode_str(ActivityMode mode);
struct Event;
void world_handle_event(const struct Event *event);

#ifdef __cplusplus
}
#endif
