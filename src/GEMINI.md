# GEMINI Instructions for `src/`

## Scope
This folder is the embedded C/C++ intelligence core for ESP32.

## Core Design Constraints
- Keep event flow deterministic and bounded.
- `WorldState` should be mutated through reducer/event handling paths, not ad hoc writes.
- Avoid introducing blocking or heavy work in high-priority tasks.

## Key Files
- `main.cpp`: task startup, UART, integration orchestration
- `core/events.*`: event definitions and queue
- `core/event_reducer.*`: state update pipeline
- `core/world_state.*`: world state model
- `core/decision_gate.*`: permission logic
- `core/action_intent.*`: action proposal logic
- `core/snapshot_service.*`: host snapshot interface

## Serial Settings in This Track
- `UART_BAUD_RATE` in `src/main.cpp` is `115200`.
- Keep host-side code aligned with this if this firmware is flashed.

## Change Checklist
When editing core behavior:
1. Confirm event type semantics in `events.h`.
2. Validate reducer impact on belief/freshness.
3. Re-check decision gate thresholds and action intent outcomes.
4. Ensure UART/snapshot output remains parseable by laptop-side clients.

## Performance Guidance
- Prefer fixed-size buffers and bounded queues.
- Avoid heap-heavy patterns in real-time loops.
- Keep task priorities meaningful (reducer above observers).

## Do Not
- Add cloud/network dependencies here.
- Move authoritative state decisions to laptop/UI code.
- Break snapshot compatibility without coordinated laptop updates.
