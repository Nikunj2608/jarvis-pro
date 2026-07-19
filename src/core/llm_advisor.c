#include "llm_advisor.h"

#include <stdio.h>

void llm_prepare_explanation(const WorldState *world,
                             const DecisionExplanation *decision,
                             const ActionIntent *intent,
                             char *out_buf,
                             size_t out_len)
{
    if ((out_buf == NULL) || (out_len == 0U)) {
        return;
    }

    out_buf[0] = '\0';

    if ((world == NULL) || (decision == NULL) || (intent == NULL)) {
        (void)snprintf(out_buf,
                       out_len,
                       "Explanation unavailable: missing inputs.");
        return;
    }

    const char *segment = world_day_segment_str(world->time.segment);
    const char *mode = world_activity_mode_str(world->activity.mode);

    const char *intent_state = intent->proposed ? "intent proposed" : "no intent";

    (void)snprintf(out_buf,
                   out_len,
                   "At %s during %s mode, belief=%u freshness=%u making decision %s; %s (action %u) because %s",
                   segment,
                   mode,
                   decision->belief,
                   decision->freshness,
                   decision->permitted ? "permitted" : "denied",
                   intent_state,
                   intent->action_id,
                   intent->rationale);
}
