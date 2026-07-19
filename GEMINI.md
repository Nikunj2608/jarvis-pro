# GEMINI Project Instructions

## Repository Purpose
This repository contains a local-first JARVIS ecosystem with two major tracks:
- ESP32 C/C++ belief core under `src/` (event-driven, FreeRTOS)
- Laptop orchestration and interfaces under `testing/laptop/` (voice, vision, serial, dashboard)

## Critical Architecture Context
- Treat the ESP32 core as the source of truth for world state and decisions.
- Laptop-side Python should provide evidence and UI, not override deterministic core logic.
- Keep event-driven flow intact: Events -> Reducer -> World State -> Decision Gate -> Action Intent.

## Protocol Reality (Important)
This repo contains two ESP32 firmware variants with different serial protocols:
1. `src/main.cpp` stack:
   - Baud: `115200`
   - Snapshot-oriented architecture
2. `testing/esp32/jarvis_esp32.ino` stack:
   - Baud: `9600`
   - `GET_ENV` -> `TEMP:x,HUM:y` style

Before changing serial code, confirm which firmware is on the board.

## Current Laptop Runtime Assumptions
- Port: `COM8`
- Preferred baud for unified stack: `115200`
- Main entrypoint: `testing/laptop/jarvis_unified.py`

## Common Run Commands (Windows)
From repo root:
- Unified JARVIS: `python3.13.exe testing/laptop/jarvis_unified.py`
- Vision UI: `python3.13.exe vision_distraction.py --port COM8 --baud 115200 --debug`
- Dashboard: `python3.13.exe -m streamlit run jarvis_dashboard.py --server.port 8501`

## Serial Port Safety
- Only one process can own COM8 at a time.
- Close Arduino Serial Monitor before running Python serial clients.
- If locked, stop Python/Arduino processes and retry.

## Editing Guidelines
- Keep behavior deterministic in core logic files.
- Preserve backward compatibility when practical for protocol changes.
- Prefer small, focused edits and avoid unrelated refactors.
- Update docs near changed behavior (especially protocol defaults).

## Known Runtime Caveat
Phi-2 model loading may be unavailable locally depending on disk/cache state; laptop components may run in fallback mode without local LLM while serial/vision/voice continue.
