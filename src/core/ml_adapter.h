#pragma once

#include <stdint.h>

#include "FreeRTOS.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    uint8_t label;
    uint8_t confidence;
} MLInference;

void ml_adapter_start(UBaseType_t priority);

#ifdef __cplusplus
}
#endif
