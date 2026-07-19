# Jarvis Belief Core

This repository contains the real-time, local-first belief maintenance core for an ESP32-class assistant. The design is intentionally constrained: every module is deterministic, runs offline, and mutates the World State only through bounded events. There are no actuators, cloud calls, or hidden feedback loops.

## Architectural Overview

```
+------------------+        +-------------------+        +--------------------+
|   ML Adapter     |  -->   |   Event Queue     |  -->   |  Event Reducer     |
|  (evidence)      |        | (bounded ring)    |        |  (world_handle)    |
+------------------+        +-------------------+        +--------------------+
                                                            |
                                                            v
                                                    +----------------+
                                                    |  World State   |
                                                    |  (beliefs)     |
                                                    +----------------+
                                                            |
                 +--------------------+            +--------------------+
                 | Belief Logger      |            | Decision Gate      |
                 | (ground truth)     |            | (permission)       |
                 +--------------------+            +--------------------+
                                                            |
                                                            v
                                                  +---------------------+
                                                  | Action Intent       |
                                                  | (proposed actions)  |
                                                  +---------------------+
                                                            |
                                                            v
                                                  +---------------------+
                                                  | LLM Advisor         |
                                                  | (narration only)    |
                                                  +---------------------+
```

Key principles:
- **Event-driven**: ISR-safe producers enqueue `Event` structs; the reducer is the only writer to `WorldState`.
- **Belief dominance vs. freshness**: `ConfidenceState.belief` chooses the dominant evidence, while `freshness` gates action permission.
- **Explainability**: every step (logger, decision gate, action intent, LLM advisor) prints human-readable rationales.
- **ML as advisor**: the ML adapter only emits `EV_ACTIVITY_CLUE` events. It never acts or overrides the deterministic reducer.

## Modules

| Module | Purpose | Notes |
| --- | --- | --- |
| `world_state.*` | Holds temporal, physical, activity, and confidence contexts | Only mutated via `world_handle_event()` |
| `events.*` | Static FreeRTOS queue for `Event` structs | Fixed length (16) to keep RAM bounded |
| `event_reducer.*` | Drains queue and applies Tier-1 events | Invokes `world_handle_event()` |
| `belief_logger.*` | Prints `[HH:MM] segment | mode | belief | freshness` | Runs every 30 s as proof of belief evolution |
| `belief_test_harness.*` | Optional (`BELIEF_TEST_MODE`) conflicting evidence injector | Demonstrates dominance & decay without overrides |
| `decision_gate.*` | Evaluates `belief >= threshold` AND `freshness >= threshold` | Emits `DecisionExplanation` structs instead of acting |
| `action_intent.*` | Derives non-actuating `ActionIntent` proposals | Requires `DecisionExplanation.permitted == true` |
| `ml_adapter.*` | Synthetic ML perception task | Alternates focus/distracted clues, proving ML is advisory |
| `llm_advisor.*` | Generates single-paragraph explanations for humans/LLMs | Read-only; no RT constraints |

## Event Types (Tiered)

| Tier | Event | Status |
| --- | --- | --- |
| 1 | `EV_TIME_TICK` | Drives day segments & freshness decay |
| 1 | `EV_PRESENCE` | Placeholder for future presence cues |
| 1 | `EV_ACTIVITY_CLUE` | Populated by ML adapter & test harness |
| 1 | `EV_OVERRIDE` | Manual dominance for maintenance |
| 2 | `EV_ENV_UPDATE` | Stubbed for future environmental signals |
| 2 | `EV_MODE_CONFIRM` | Stubbed explicit confirmations |
| 2 | `EV_FAULT` | Stubbed anomaly reporting |

## Build & Bring-Up Checklist

1. **FreeRTOS setup**: ensure `configMINIMAL_STACK_SIZE` accommodates each static task (logger, reducer, decision gate, action intent, ML adapter, optional test harness).
2. **Queue + reducer**: call `event_reducer_start(priority)` early so events have a consumer.
3. **Evidence producers**: start `ml_adapter_start()` (and `belief_test_start()` if `BELIEF_TEST_MODE` is defined) to feed activity clues.
4. **Belief surfaces**: start `belief_logger_start()`, `decision_gate_start()`, and `action_intent_start()` at low priority to observe the belief → permission → intent pipeline.
5. **Explanations**: when needed, call `llm_prepare_explanation()` with snapshots from the logger pipeline to serve UI/CLI demos.

## Demo Logging Targets

- Belief timeline (every 30 s):
  ```
  [07:01] morning | focus | belief=72 | freshness=85
  ```
- Decision gate (45 s cadence):
  ```
  Decision | permitted=false | belief=72 | freshness=40 | Belief strong (72) but freshness 40<60
  ```
- Action intent:
  ```
  Intent | proposed=true | action=1 | Suggest break: focus 52 min during night
  ```

## Safety Boundaries

- No module actuates hardware or calls cloud APIs.
- ML and LLM components are advisory only; they never write `WorldState` or request actions directly.
- Confidence decay relies solely on time ticks, so policy changes (e.g., different decay rates) are expressed via events, not tight loops.

This documentation should live in the repo root so reviewers can see, at a glance, how the core intelligence pipeline maintains beliefs, gates decisions, and produces explainable intents without taking actions.
