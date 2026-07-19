# GEMINI Instructions for `testing/laptop/`

## Scope
Python runtime for local JARVIS orchestration: voice, vision integration, serial client, testing, and dashboards.

## Primary Entrypoints
- `jarvis_unified.py`: full stack runner (voice + vision + sensors + reasoning)
- `jarvis_core.py`: orchestrator and reasoning loops
- `serial_client.py`: ESP32 serial integration and optional local LLM use
- `../jarvis_dashboard.py`: Streamlit web dashboard
- `../vision_distraction.py`: OpenCV vision evidence UI

## Runtime Defaults to Keep Consistent
- Serial port: `COM8`
- Unified serial baud: `115200`
- Snapshot-based serial parsing should remain compatible with current firmware output

## Parallel Run Pattern (Windows)
From repo root, run in separate terminals:
1. `python3.13.exe testing/laptop/jarvis_unified.py`
2. `python3.13.exe vision_distraction.py --port COM8 --baud 115200 --debug`
3. `python3.13.exe -m streamlit run jarvis_dashboard.py --server.port 8501`

If COM8 conflicts occur, ensure only one serial owner where required and close Arduino serial monitors.

## Voice and Sensor Notes
- Voice capture uses SpeechRecognition + RNNoise path in `jarvis_unified.py`.
- Sensor parsing in `jarvis_core.py` must handle both temperature and humidity safely.
- Keep `serial_client.py` response contract stable for callers (`get_env` output assumptions).

## LLM Behavior
- Local Phi-2 may be unavailable depending on cache/storage state.
- Preserve graceful fallback so core features run even when local LLM cannot load.

## Testing Guidance
- `test_jarvis.py` validates component-level and integration behavior.
- Prefer smoke tests that verify: serial connection, vision loop, reasoning loop, and voice listen loop startup.

## Do Not
- Hardcode machine-specific absolute paths.
- Introduce protocol changes without updating both parser and docs.
- Mix multiple contradictory baud/protocol assumptions in default paths.
