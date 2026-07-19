#pragma once

#include "FreeRTOS.h"

#ifdef __cplusplus
extern "C" {
#endif

#ifdef BELIEF_TEST_MODE
void belief_test_start(UBaseType_t priority);
#else
static inline void belief_test_start(UBaseType_t priority)
{
    (void)priority;
}
#endif

#ifdef __cplusplus
}
#endif
