#include "world_state.h"
#include "events.h"

#define DEFAULT_CONFIDENCE 0U
#define DEFAULT_FRESHNESS  0U

WorldState world = {
	.time = {
		.segment = DAY_SEGMENT_NIGHT,
		.last_sync_ms = 0U,
	},
	.physical = {
		.occupied = false,
		.last_motion_ms = 0U,
	},
	.activity = {
		.mode = ACTIVITY_MODE_IDLE,
		.mode_start_ms = 0U,
	},
	.confidence = {
		.belief = DEFAULT_CONFIDENCE,
		.freshness = DEFAULT_FRESHNESS,
		.cause = UNCERTAINTY_NONE,
	},
	.session = {
		.active_session_id = 0U,
		.session_start_ms = 0U,
		.session_count_today = 0U,
	},
	.habits = {
		.focus_minutes_today = 0U,
		.distraction_count_today = 0U,
		.typical_focus_hour = 10U,        /* default 10am */
		.typical_distraction_hour = 15U,  /* default 3pm */
	},
};

static DaySegment compute_day_segment(uint32_t timestamp_ms);
static void decay_confidence(void);
static void diagnose_uncertainty(void);
static uint8_t get_source_weight(EvidenceSource source);
static void handle_time_tick(const Event *event);
static void handle_activity_clue(const Event *event);
static void handle_override(const Event *event);
static void handle_session_start(const Event *event);

const char *world_day_segment_str(DaySegment segment)
{
	switch (segment) {
	case DAY_SEGMENT_NIGHT:
		return "night";
	case DAY_SEGMENT_MORNING:
		return "morning";
	case DAY_SEGMENT_AFTERNOON:
		return "afternoon";
	case DAY_SEGMENT_EVENING:
		return "evening";
	default:
		return "unknown";
	}
}

const char *world_activity_mode_str(ActivityMode mode)
{
	switch (mode) {
	case ACTIVITY_MODE_IDLE:
		return "idle";
	case ACTIVITY_MODE_FOCUS:
		return "focus";
	case ACTIVITY_MODE_DISTRACTED:
		return "distracted";
	case ACTIVITY_MODE_OVERRIDE:
		return "override";
	default:
		return "unknown";
	}
}

void world_handle_event(const Event *event)
{
	if (event == NULL) {
		return;
	}

	switch (event->type) {
	case EV_TIME_TICK:
		handle_time_tick(event);
		break;
	case EV_ACTIVITY_CLUE:
		handle_activity_clue(event);
		break;
	case EV_OVERRIDE:
		handle_override(event);
		break;
	case EV_SESSION_START:
		handle_session_start(event);
		break;
	default:
		break;
	}
	
	diagnose_uncertainty();
}

static DaySegment compute_day_segment(uint32_t timestamp_ms)
{
	if (timestamp_ms == 0U) {
		return DAY_SEGMENT_NIGHT;
	}

	uint32_t total_hours = (timestamp_ms / 3600000U) % 24U;

	if (total_hours < 6U) {
		return DAY_SEGMENT_NIGHT;
	}
	if (total_hours < 12U) {
		return DAY_SEGMENT_MORNING;
	}
	if (total_hours < 18U) {
		return DAY_SEGMENT_AFTERNOON;
	}
	return DAY_SEGMENT_EVENING;
}

static void decay_confidence(void)
{
	const uint8_t decay = 5U;

	if (world.confidence.freshness > decay) {
		world.confidence.freshness -= decay;
	} else {
		world.confidence.freshness = 0U;
	}
}

static void handle_time_tick(const Event *event)
{
	world.time.last_sync_ms = event->ts;
	world.time.segment = compute_day_segment(event->ts);

	if (world.confidence.freshness > 0U) {
		decay_confidence();
	}
}

static ActivityMode value_to_mode(uint8_t value)
{
	switch (value) {
	case ACTIVITY_MODE_FOCUS:
	case ACTIVITY_MODE_DISTRACTED:
	case ACTIVITY_MODE_OVERRIDE:
		return (ActivityMode)value;
	default:
		return ACTIVITY_MODE_IDLE;
	}
}

static void handle_activity_clue(const Event *event)
{
	uint8_t source_weight = get_source_weight(event->source);
	uint8_t weighted_confidence = (event->confidence * source_weight) / 100U;
	
	if (weighted_confidence > world.confidence.belief) {
		world.activity.mode = value_to_mode(event->value);
		world.activity.mode_start_ms = event->ts;
		world.confidence.belief = weighted_confidence;
		world.confidence.freshness = 100U;
		
		/* Track habit statistics */
		if (world.activity.mode == ACTIVITY_MODE_DISTRACTED) {
			world.habits.distraction_count_today++;
		}
	}
}

static void handle_override(const Event *event)
{
	world.activity.mode = value_to_mode(event->value);
	world.activity.mode_start_ms = event->ts;
	world.confidence.belief = 100U;
	world.confidence.freshness = 100U;
	world.confidence.cause = UNCERTAINTY_NONE;
}

static void handle_session_start(const Event *event)
{
	world.session.active_session_id++;
	world.session.session_start_ms = event->ts;
	world.session.session_count_today++;
}

/* Evidence source reliability weights (0-100) */
static uint8_t get_source_weight(EvidenceSource source)
{
	switch (source) {
	case SOURCE_MANUAL_OVERRIDE:
		return 100U;  /* User commands are gospel */
	case SOURCE_MOTION_PIR:
		return 90U;   /* PIR is very reliable */
	case SOURCE_ENV_SENSOR:
		return 85U;   /* BME280 is trustworthy */
	case SOURCE_VISION_LAPTOP:
		return 70U;   /* Vision can have false positives */
	case SOURCE_VOICE_ACTIVITY:
		return 60U;   /* Voice detection is noisy */
	case SOURCE_TIME_INFERENCE:
		return 40U;   /* Clock-based guesses are weak */
	default:
		return 50U;
	}
}

/* Diagnose WHY we're uncertain */
static void diagnose_uncertainty(void)
{
	if (world.confidence.belief >= 80U && world.confidence.freshness >= 80U) {
		world.confidence.cause = UNCERTAINTY_NONE;
		return;
	}
	
	/* Check for stale data */
	const uint32_t now = world.time.last_sync_ms;
	const uint32_t data_age_ms = now - world.activity.mode_start_ms;
	if (data_age_ms > 300000U) {  /* 5 minutes */
		world.confidence.cause = UNCERTAINTY_STALE_DATA;
		return;
	}
	
	/* Check for low signal strength */
	if (world.confidence.belief < 40U) {
		world.confidence.cause = UNCERTAINTY_LOW_SIGNAL;
		return;
	}
	
	/* Check for freshness decay */
	if (world.confidence.freshness < 40U) {
		world.confidence.cause = UNCERTAINTY_STALE_DATA;
		return;
	}
	
	/* Default to unknown context */
	world.confidence.cause = UNCERTAINTY_UNKNOWN_CONTEXT;
