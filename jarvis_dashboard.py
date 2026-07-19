"""Streamlit dashboard for the Jarvis belief core.

Combines three host-side views:
    1. Continuous snapshot monitor (read-only over serial)
    2. Vision evidence feed (from vision_distraction.py log)
    3. Push-to-talk conversational layer (STT -> snapshot -> LLM -> TTS)

This script never mutates ESP32 intelligence. All interactions are
read-only snapshot requests or evidence visualizations.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import serial  # type: ignore
import streamlit as st

try:
    from streamlit_autorefresh import st_autorefresh  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    st_autorefresh = None  # type: ignore

from jarvis_interface import (  # type: ignore
    LLMClient,
    SerialSnapshotClient,
    SpeechInterface,
    SpeechSynthesizer,
    SystemSnapshot,
)

SNAPSHOT_TIMEOUT = 0.2
DEFAULT_REFRESH_MS = 1000
DEFAULT_VISION_LOG = "vision_evidence.log"
DEFAULT_ACTIVITY_LOG = "testing/laptop/activity_log.txt"
DEFAULT_OLLAMA_URL = os.getenv("JARVIS_OLLAMA_URL", "http://127.0.0.1:11434")
DEFAULT_OLLAMA_MODEL = os.getenv("JARVIS_OLLAMA_MODEL", "qwen2.5:1.5b")


def init_state() -> None:
    st.session_state.setdefault("serial_client", None)
    st.session_state.setdefault("serial_settings", (None, None))
    st.session_state.setdefault("serial_error", None)
    st.session_state.setdefault("last_snapshot", None)
    st.session_state.setdefault("last_snapshot_ts", None)
    st.session_state.setdefault("conversation", [])
    st.session_state.setdefault("speech_interface", None)
    st.session_state.setdefault("speech_error", None)
    st.session_state.setdefault("llm_client", None)
    st.session_state.setdefault("llm_settings", (None, None, None))
    st.session_state.setdefault("tts", None)
    st.session_state.setdefault("activity_analysis", "")
    st.session_state.setdefault("activity_schedule", "")


def ensure_serial_client(port: str, baud: int) -> Optional[SerialSnapshotClient]:
    key = (port, baud)
    client = st.session_state.get("serial_client")
    if client and st.session_state.get("serial_settings") != key:
        try:
            client.serial.close()
        except Exception:  # pragma: no cover
            pass
        client = None
        st.session_state["serial_client"] = None

    if client is None:
        try:
            client = SerialSnapshotClient(port=port, baud=baud, timeout=SNAPSHOT_TIMEOUT)
            st.session_state["serial_client"] = client
            st.session_state["serial_settings"] = key
            st.session_state["serial_error"] = None
        except serial.SerialException as exc:  # pragma: no cover
            st.session_state["serial_error"] = str(exc)
            st.session_state["serial_client"] = None
            return None
    return client


def fetch_snapshot() -> Optional[SystemSnapshot]:
    client: Optional[SerialSnapshotClient] = st.session_state.get("serial_client")
    if client is None:
        return None
    try:
        snapshot = client.request_snapshot()
    except serial.SerialException as exc:  # pragma: no cover
        st.session_state["serial_error"] = str(exc)
        st.session_state["serial_client"] = None
        return None

    if snapshot is not None:
        st.session_state["last_snapshot"] = snapshot
        st.session_state["last_snapshot_ts"] = time.time()
    return snapshot


def get_snapshot_for_display() -> Tuple[Optional[SystemSnapshot], bool]:
    snapshot = fetch_snapshot()
    online = snapshot is not None
    if not online:
        snapshot = st.session_state.get("last_snapshot")
    return snapshot, online


def load_vision_log(path: str, limit: int = 5) -> List[str]:
    if not path:
        return []
    file = Path(path)
    if not file.exists():
        return []
    try:
        lines = [line.strip() for line in file.open("r", encoding="utf-8") if line.strip()]
    except OSError:  # pragma: no cover
        return []
    return lines[-limit:]


def load_activity_log(path: str, limit: int = 200) -> List[str]:
    if not path:
        return []
    file = Path(path)
    if not file.exists():
        return []
    try:
        lines = [line.strip() for line in file.open("r", encoding="utf-8") if line.strip()]
    except OSError:
        return []
    return lines[-limit:]


def _extract_float(pattern: str, text: str) -> Optional[float]:
    m = re.search(pattern, text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def summarize_activity(lines: List[str]) -> Dict[str, Any]:
    focused = 0
    distracted = 0
    no_face = 0
    head_motion_samples: List[float] = []
    gaze_samples: List[float] = []
    face_missing_samples: List[float] = []

    for line in lines:
        if "state=FOCUSED" in line:
            focused += 1
        elif "state=DISTRACTED" in line:
            distracted += 1
        elif "state=NO_FACE" in line:
            no_face += 1

        hm = _extract_float(r"head_motion=([0-9]+(?:\.[0-9]+)?)", line)
        if hm is not None:
            head_motion_samples.append(hm)

        gaze = _extract_float(r"gaze_off=([0-9]+(?:\.[0-9]+)?)", line)
        if gaze is not None:
            gaze_samples.append(gaze)

        face_missing = _extract_float(r"face_missing=([0-9]+(?:\.[0-9]+)?)", line)
        if face_missing is not None:
            face_missing_samples.append(face_missing)

    total_states = focused + distracted + no_face
    focus_ratio = (focused / total_states) if total_states else 0.0
    distracted_ratio = (distracted / total_states) if total_states else 0.0
    no_face_ratio = (no_face / total_states) if total_states else 0.0

    avg_head_motion = (sum(head_motion_samples) / len(head_motion_samples)) if head_motion_samples else 0.0
    avg_gaze = (sum(gaze_samples) / len(gaze_samples)) if gaze_samples else 0.0
    avg_face_missing = (sum(face_missing_samples) / len(face_missing_samples)) if face_missing_samples else 0.0

    if no_face_ratio > 0.45:
        posture_state = "camera_tracking_low"
    elif avg_head_motion > 35 or avg_gaze > 0.35:
        posture_state = "posture_unstable"
    elif focus_ratio > 0.6 and avg_head_motion < 18:
        posture_state = "posture_stable"
    else:
        posture_state = "posture_mixed"

    return {
        "focused": focused,
        "distracted": distracted,
        "no_face": no_face,
        "focus_ratio": focus_ratio,
        "distracted_ratio": distracted_ratio,
        "no_face_ratio": no_face_ratio,
        "avg_head_motion": avg_head_motion,
        "avg_gaze": avg_gaze,
        "avg_face_missing": avg_face_missing,
        "posture_state": posture_state,
    }


def _compact_prompt(prompt: str, max_chars: int = 2000) -> str:
    return " ".join(prompt.split())[-max_chars:]


def _llm_error_text(text: str) -> bool:
    return text.startswith("Local LLM ")


def local_ollama_generate(prompt: str, model: str, base_url: str) -> str:
    def _request(payload: Dict[str, Any], timeout_sec: float) -> str:
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            text = body.get("response", "").strip()
            return text or "No response from local model."

    attempts = [
        (prompt, 40.0, 220),
        (prompt[-2200:], 25.0, 140),
        (_compact_prompt(prompt, 1200), 15.0, 90),
    ]
    last_error: Optional[Exception] = None

    for attempt_prompt, timeout_sec, num_predict in attempts:
        payload = {
            "model": model,
            "prompt": attempt_prompt,
            "stream": False,
            "options": {
                "temperature": 0.35,
                "num_predict": num_predict,
            },
            "keep_alive": "30m",
        }
        try:
            return _request(payload, timeout_sec=timeout_sec)
        except Exception as exc:
            last_error = exc

    if isinstance(last_error, urllib.error.URLError):
        return f"Local LLM connection error: {last_error}"
    return f"Local LLM error: {last_error}"


def build_activity_context(summary: Dict[str, Any], recent_lines: List[str], snapshot: Optional[SystemSnapshot]) -> str:
    snapshot_text = "none"
    if snapshot is not None:
        snapshot_text = json.dumps(
            {
                "activity_mode": snapshot.world.get("activity", {}).get("mode"),
                "belief": snapshot.world.get("confidence", {}).get("belief"),
                "freshness": snapshot.world.get("confidence", {}).get("freshness"),
                "presence": snapshot.world.get("physical", {}).get("occupied"),
            }
        )

    recent_block = "\n".join(recent_lines[-12:]) if recent_lines else "no recent activity lines"
    return (
        f"Posture summary: {json.dumps(summary)}\n"
        f"Current snapshot: {snapshot_text}\n"
        f"Recent activity log lines:\n{recent_block}"
    )


def fallback_activity_analysis(summary: Dict[str, Any]) -> str:
    posture_cue = {
        "posture_stable": "Posture is generally stable. Keep your neck neutral and shoulders relaxed.",
        "posture_unstable": "Posture is unstable. Add short reset drills: chin tuck, shoulder roll, and seated spine reset.",
        "camera_tracking_low": "Face tracking is low. Reposition camera and improve lighting before judging focus quality.",
        "posture_mixed": "Posture quality is mixed. Use frequent mini-resets to avoid drift.",
    }.get(summary["posture_state"], "Maintain a neutral seated posture and periodic movement.")

    improvements = [
        "Use 45-60 minute deep-work blocks with 5-minute movement breaks.",
        "Trigger a 2-minute reset if head motion spikes or attention drops.",
        "Keep screen at eye level and elbows close to 90 degrees.",
        "Do one breathing reset (4-4-6) before each major task block.",
        "Reduce context switching by grouping similar tasks together.",
    ]

    return (
        "Local model timed out. Fallback coaching applied.\n\n"
        f"Focus ratio: {summary['focus_ratio'] * 100:.1f}% | "
        f"Distracted ratio: {summary['distracted_ratio'] * 100:.1f}% | "
        f"Posture state: {summary['posture_state']}\n"
        f"Posture cue: {posture_cue}\n\n"
        "Top improvements:\n"
        + "\n".join(f"{i + 1}. {tip}" for i, tip in enumerate(improvements))
    )


def fallback_adaptive_schedule(summary: Dict[str, Any], goal: str, schedule_hours: int) -> str:
    start = datetime.now().replace(second=0, microsecond=0)
    minutes_left = schedule_hours * 60

    if summary["focus_ratio"] >= 0.65:
        work_block = 50
        short_break = 8
    elif summary["focus_ratio"] >= 0.45:
        work_block = 40
        short_break = 8
    else:
        work_block = 30
        short_break = 10

    posture_cue = {
        "posture_stable": "Maintain neutral spine, shoulders down, chin level.",
        "posture_unstable": "Reset posture before each block; reduce neck flexion.",
        "camera_tracking_low": "Center your face in frame and improve lighting.",
        "posture_mixed": "Do a posture check at block start and midpoint.",
    }.get(summary["posture_state"], "Maintain relaxed neutral posture.")

    trigger = "Take a 2-minute reset if head_motion > 22 or distraction appears twice in a row."
    lines = [
        "Local model timed out. Fallback adaptive schedule applied.",
        f"Goal: {goal}",
        f"Horizon: {schedule_hours} hour(s)",
        "",
    ]

    block_idx = 1
    current = start
    while minutes_left > 0:
        work_minutes = min(work_block, minutes_left)
        work_end = current + timedelta(minutes=work_minutes)
        lines.append(
            f"{block_idx}. {current.strftime('%H:%M')} - {work_end.strftime('%H:%M')} | "
            f"Deep work ({work_minutes}m) | Posture cue: {posture_cue}"
        )
        minutes_left -= work_minutes
        current = work_end
        if minutes_left <= 0:
            break

        break_minutes = min(short_break if block_idx % 3 else 15, minutes_left)
        break_end = current + timedelta(minutes=break_minutes)
        lines.append(
            f"   Break: {current.strftime('%H:%M')} - {break_end.strftime('%H:%M')} ({break_minutes}m) | "
            f"Trigger: {trigger}"
        )
        minutes_left -= break_minutes
        current = break_end
        block_idx += 1

    lines.append("")
    lines.append("Review checkpoint: note focus quality and adjust next block length by +/-10 minutes.")
    return "\n".join(lines)


def get_speech_interface() -> Optional[SpeechInterface]:
    speech = st.session_state.get("speech_interface")
    if speech is None:
        try:
            speech = SpeechInterface()
            st.session_state["speech_interface"] = speech
            st.session_state["speech_error"] = None
        except Exception as exc:  # pragma: no cover
            st.session_state["speech_error"] = str(exc)
            return None
    return speech


def get_llm_client(provider: str, model: str, api_key: Optional[str]) -> LLMClient:
    key = (provider, model, api_key)
    if st.session_state.get("llm_settings") != key:
        st.session_state["llm_client"] = LLMClient(provider=provider, model=model, api_key=api_key)
        st.session_state["llm_settings"] = key
    return st.session_state["llm_client"]


def get_tts() -> Optional[SpeechSynthesizer]:
    tts = st.session_state.get("tts")
    if tts is None:
        try:
            tts = SpeechSynthesizer()
            st.session_state["tts"] = tts
        except Exception:  # pragma: no cover
            return None
    return tts


def speak(text: str) -> None:
    tts = get_tts()
    if tts:
        tts.speak(text)


def append_message(speaker: str, text: str) -> None:
    st.session_state["conversation"].append({
        "speaker": speaker,
        "text": text,
        "timestamp": time.time(),
    })


def format_snapshot_json(snapshot: SystemSnapshot) -> str:
    payload = {
        "world": snapshot.world,
        "decision": snapshot.decision,
        "intent": snapshot.intent,
        "timestamp_ms": snapshot.timestamp_ms,
    }
    return json.dumps(payload, indent=2)


def render_status(online: bool) -> None:
    status_col, age_col = st.columns(2)
    label = "ONLINE" if online else "BRAIN OFFLINE"
    status_col.metric("ESP32 Core", label)
    last_ts = st.session_state.get("last_snapshot_ts")
    if last_ts:
        age = time.time() - last_ts
        age_col.metric("Snapshot age", f"{age:.1f} s")
    else:
        age_col.metric("Snapshot age", "-", "")


def render_belief_panel(snapshot: SystemSnapshot) -> None:
    world = snapshot.world
    st.subheader("Belief State")
    cols = st.columns(2)
    cols[0].metric("Day segment", world["time"].get("segment", "unknown"))
    cols[1].metric("Presence", "occupied" if world["physical"].get("occupied") else "likely empty")
    cols = st.columns(2)
    cols[0].metric("Activity mode", world["activity"].get("mode", "unknown"))
    cols[1].metric("Belief strength", f"{world['confidence'].get('belief', 0)} %")
    st.progress(world["confidence"].get("freshness", 0) / 100.0)
    st.caption("Identity: unavailable (not in snapshot)")


def render_decision_panel(snapshot: SystemSnapshot) -> None:
    decision = snapshot.decision
    st.subheader("Decision Gate")
    cols = st.columns(2)
    cols[0].metric("Permitted", "Yes" if decision.get("permitted") else "No")
    cols[1].metric("Freshness", f"{decision.get('freshness', 0)} %")
    st.write(decision.get("reason", "No decision reason available."))


def render_intent_panel(snapshot: SystemSnapshot) -> None:
    intent = snapshot.intent
    st.subheader("Action Intent")
    cols = st.columns(2)
    cols[0].metric("Proposed", "Yes" if intent.get("proposed") else "No")
    cols[1].metric("Action", intent.get("action_id", "none"))
    rationale = intent.get("rationale") or "No rationale available."
    st.write(rationale)


def render_vision_panel(log_path: str) -> None:
    st.subheader("Vision Evidence (latest)")
    entries = load_vision_log(log_path)
    if not entries:
        st.caption("No evidence entries. Ensure vision_distraction.py is running with logging enabled.")
        return
    for line in entries:
        st.write(line)


def render_activity_panel(activity_log: str, snapshot: Optional[SystemSnapshot], ollama_model: str, ollama_url: str) -> None:
    st.subheader("Activity Intelligence")
    lines = load_activity_log(activity_log, limit=300)
    if not lines:
        st.caption("No activity log entries yet. Start unified + vision first.")
        return

    summary = summarize_activity(lines)

    cols = st.columns(4)
    cols[0].metric("Focused", str(summary["focused"]))
    cols[1].metric("Distracted", str(summary["distracted"]))
    cols[2].metric("No Face", str(summary["no_face"]))
    cols[3].metric("Posture State", summary["posture_state"])

    cols = st.columns(3)
    cols[0].metric("Focus Ratio", f"{summary['focus_ratio'] * 100:.1f}%")
    cols[1].metric("Avg Head Motion", f"{summary['avg_head_motion']:.1f} px/s")
    cols[2].metric("Avg Gaze Offset", f"{summary['avg_gaze']:.2f}")

    st.caption("Recent activity stream")
    for line in lines[-25:]:
        st.write(line)

    st.divider()
    st.subheader("Local LLM Coach")
    goal = st.text_input("Goal for schedule", "Deep focus + less distraction")
    schedule_hours = st.slider("Schedule horizon (hours)", 1, 8, 4)

    context = build_activity_context(summary, lines, snapshot)

    action_cols = st.columns(2)
    if action_cols[0].button("Analyze Posture + Activity", type="primary"):
        prompt = (
            "You are a performance coach. Analyze posture/activity trends and provide concise guidance.\n"
            "Focus on posture quality, distraction patterns, and top 5 high-impact improvements.\n\n"
            f"{context}"
        )
        analysis = local_ollama_generate(prompt, ollama_model, ollama_url)
        if _llm_error_text(analysis):
            analysis = fallback_activity_analysis(summary)
        st.session_state["activity_analysis"] = analysis

    if action_cols[1].button("Generate Adaptive Schedule"):
        prompt = (
            "You are a scheduling optimizer. Build a practical schedule with short blocks and recovery breaks.\n"
            f"Create a {schedule_hours}-hour schedule aligned to this goal: {goal}.\n"
            "Use measured posture/distraction patterns and provide timestamps relative to now.\n"
            "Include: block type, duration, posture cue, and break trigger.\n\n"
            f"{context}"
        )
        schedule = local_ollama_generate(prompt, ollama_model, ollama_url)
        if _llm_error_text(schedule):
            schedule = fallback_adaptive_schedule(summary, goal, schedule_hours)
        st.session_state["activity_schedule"] = schedule

    if st.session_state.get("activity_analysis"):
        st.markdown("**LLM Activity Analysis**")
        st.write(st.session_state["activity_analysis"])

    if st.session_state.get("activity_schedule"):
        st.markdown("**LLM Adaptive Schedule**")
        st.write(st.session_state["activity_schedule"])


def run_push_to_talk(provider: str, model: str, api_key: Optional[str]) -> None:
    speech = get_speech_interface()
    if speech is None:
        st.warning(f"Microphone unavailable: {st.session_state.get('speech_error')}")
        return

    try:
        user_text = speech.capture()
    except Exception as exc:  # pragma: no cover
        append_message("system", f"Audio capture error: {exc}")
        return
    if not user_text:
        append_message("system", "Could not understand audio input.")
        return

    append_message("user", user_text)

    client = st.session_state.get("serial_client")
    if client is None:
        response = "I can’t access system state right now."
        append_message("jarvis", response)
        speak(response)
        return

    try:
        snapshot = client.request_snapshot()
    except serial.SerialException as exc:  # pragma: no cover
        response = f"Serial error while retrieving state: {exc}"
        append_message("jarvis", response)
        speak(response)
        return
    if snapshot is None:
        response = "I’m unable to retrieve system state right now."
        append_message("jarvis", response)
        speak(response)
        return

    llm = get_llm_client(provider, model, api_key)
    response = llm.generate(user_text, format_snapshot_json(snapshot))
    append_message("jarvis", response)
    speak(response)


def render_conversation_log() -> None:
    st.subheader("Conversation")
    for message in st.session_state["conversation"][-10:]:
        speaker = message["speaker"].capitalize()
        st.markdown(f"**{speaker}:** {message['text']}")


def main() -> None:
    st.set_page_config(page_title="Jarvis Dashboard", layout="wide")
    init_state()

    with st.sidebar:
        st.header("Connections")
        port = st.text_input("Serial port", "COM8")
        baud = st.number_input("Baud rate", min_value=9600, max_value=921600, value=115200, step=9600)
        refresh_ms = st.slider("Snapshot refresh (ms)", 500, 2000, DEFAULT_REFRESH_MS, 100)
        vision_log = st.text_input("Vision log file", DEFAULT_VISION_LOG)
        activity_log = st.text_input("Activity log file", DEFAULT_ACTIVITY_LOG)
        ollama_url = st.text_input("Local LLM URL", DEFAULT_OLLAMA_URL)
        ollama_model = st.text_input("Local LLM Model", DEFAULT_OLLAMA_MODEL)
        st.header("LLM")
        provider = st.selectbox("Provider", ["openai", "google"], index=0)
        model = st.text_input("Model", "gpt-4o-mini")
        api_key = st.text_input("API key", value="", type="password") or None
        st.header("Status")
        serial_error = st.session_state.get("serial_error")
        if serial_error:
            st.error(f"Serial error: {serial_error}")

    if st_autorefresh:
        st_autorefresh(interval=refresh_ms, key="snapshot_refresh")
    else:
        st.caption("Auto-refresh helper not installed; press R to rerun or install streamlit-autorefresh.")

    client = ensure_serial_client(port, baud)
    snapshot, online = get_snapshot_for_display()

    st.title("Jarvis Cognitive Dashboard")
    render_status(online)

    belief_col, decision_col, intent_col = st.columns(3)
    with belief_col:
        if snapshot:
            render_belief_panel(snapshot)
        else:
            st.info("No snapshot available.")
    with decision_col:
        if snapshot:
            render_decision_panel(snapshot)
        else:
            st.info("Decision data unavailable.")
    with intent_col:
        if snapshot:
            render_intent_panel(snapshot)
        else:
            st.info("Intent data unavailable.")

    st.divider()
    lower_cols = st.columns(3)
    with lower_cols[0]:
        render_vision_panel(vision_log)
    with lower_cols[1]:
        render_activity_panel(activity_log, snapshot, ollama_model, ollama_url)
    with lower_cols[2]:
        st.subheader("Push-to-Talk")
        if st.button("Push to Talk", type="primary"):
            run_push_to_talk(provider, model, api_key)
        render_conversation_log()



if __name__ == "__main__":
    main()
