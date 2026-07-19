"""Laptop-side conversational interface for the Jarvis belief core.

Workflow:
    mic -> speech-to-text -> serial snapshot request -> LLM explanation -> TTS
The ESP32 remains the authoritative intelligence layer; this interface only
explains beliefs and intents read from snapshots. No commands are sent.
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import sys
import time
from typing import Dict, Optional

import pyttsx3  # type: ignore
import serial  # type: ignore

try:
    import speech_recognition as sr  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    sr = None  # type: ignore

try:
    from openai import OpenAI  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    OpenAI = None  # type: ignore

try:
    import google.generativeai as genai  # type: ignore
except ImportError:  # pragma: no cover - optional dependency
    genai = None  # type: ignore

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SNAPSHOT_HEADER = 0xA5
SNAPSHOT_POLL_TIMEOUT = 2.0
SNAPSHOT_REQUEST_BYTE = b"?"

PROMPT_HEADER = (
    "You are JARVIS.\n"
    "You are an explanatory interface to a real-time embedded intelligence system.\n"
    "You do NOT control the system.\n"
    "You do NOT make decisions or trigger actions.\n"
    "You explain beliefs, decisions, uncertainty, and intent honestly.\n\n"
    "Never overclaim certainty.\n"
    "Never assume the user’s task.\n"
    "If identity or context is uncertain, say so.\n"
    "If identity is not explicitly confirmed in the snapshot, do not speak in second person.\n"
)

# ---------------------------------------------------------------------------
# ctypes-based snapshot parsing (mirrors ESP32 structs)
# ---------------------------------------------------------------------------

import ctypes


class TemporalState(ctypes.LittleEndianStructure):
    _fields_ = [
        ("segment", ctypes.c_int32),
        ("last_sync_ms", ctypes.c_uint32),
    ]


class PhysicalState(ctypes.LittleEndianStructure):
    _fields_ = [
        ("occupied", ctypes.c_uint8),
        ("_pad", ctypes.c_uint8 * 3),
        ("last_motion_ms", ctypes.c_uint32),
    ]


class ActivityState(ctypes.LittleEndianStructure):
    _fields_ = [
        ("mode", ctypes.c_int32),
        ("mode_start_ms", ctypes.c_uint32),
    ]


class ConfidenceState(ctypes.LittleEndianStructure):
    _fields_ = [
        ("belief", ctypes.c_uint8),
        ("freshness", ctypes.c_uint8),
        ("_pad", ctypes.c_uint8 * 2),
    ]


class WorldStateStruct(ctypes.LittleEndianStructure):
    _fields_ = [
        ("time", TemporalState),
        ("physical", PhysicalState),
        ("activity", ActivityState),
        ("confidence", ConfidenceState),
    ]


class DecisionExplanationStruct(ctypes.LittleEndianStructure):
    _fields_ = [
        ("permitted", ctypes.c_uint8),
        ("belief", ctypes.c_uint8),
        ("freshness", ctypes.c_uint8),
        ("_pad", ctypes.c_uint8),
        ("reason", ctypes.c_char * 64),
    ]


class ActionIntentStruct(ctypes.LittleEndianStructure):
    _fields_ = [
        ("proposed", ctypes.c_uint8),
        ("action_id", ctypes.c_uint8),
        ("_pad", ctypes.c_uint8 * 2),
        ("rationale", ctypes.c_char * 64),
    ]


class SystemSnapshotStruct(ctypes.LittleEndianStructure):
    _fields_ = [
        ("state", WorldStateStruct),
        ("decision", DecisionExplanationStruct),
        ("intent", ActionIntentStruct),
        ("timestamp_ms", ctypes.c_uint32),
    ]


SNAPSHOT_PAYLOAD_SIZE = ctypes.sizeof(SystemSnapshotStruct)
SNAPSHOT_FRAME_SIZE = 1 + 2 + SNAPSHOT_PAYLOAD_SIZE + 2

DAY_SEGMENTS = {
    0: "night",
    1: "morning",
    2: "afternoon",
    3: "evening",
}

ACTIVITY_MODES = {
    0: "idle",
    1: "focus",
    2: "distracted",
    3: "override",
}

ACTION_IDS = {
    0: "none",
    1: "suggest_break",
    2: "remind_water",
    3: "silent_observe",
}


# ---------------------------------------------------------------------------
# Utility dataclasses
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class SystemSnapshot:
    world: Dict[str, object]
    decision: Dict[str, object]
    intent: Dict[str, object]
    timestamp_ms: int


# ---------------------------------------------------------------------------
# Serial snapshot client
# ---------------------------------------------------------------------------


class SerialSnapshotClient:
    def __init__(self, port: str, baud: int, timeout: float) -> None:
        self.serial = serial.Serial(port=port, baudrate=baud, timeout=timeout)

    def request_snapshot(self) -> Optional[SystemSnapshot]:
        self.serial.write(SNAPSHOT_REQUEST_BYTE)
        frame = self.serial.read(SNAPSHOT_FRAME_SIZE)
        if len(frame) < SNAPSHOT_FRAME_SIZE:
            return None
        if frame[0] != SNAPSHOT_HEADER:
            return None
        length = int.from_bytes(frame[1:3], "little")
        if length != SNAPSHOT_PAYLOAD_SIZE:
            return None
        payload = frame[3:3 + SNAPSHOT_PAYLOAD_SIZE]
        crc_expected = int.from_bytes(frame[-2:], "little")
        crc_actual = crc16(payload)
        if crc_expected != crc_actual:
            return None
        snapshot_struct = SystemSnapshotStruct.from_buffer_copy(payload)
        return convert_snapshot(snapshot_struct)


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc


# ---------------------------------------------------------------------------
# Snapshot conversion helpers
# ---------------------------------------------------------------------------


def convert_snapshot(raw: SystemSnapshotStruct) -> SystemSnapshot:
    world = {
        "time": {
            "segment": DAY_SEGMENTS.get(raw.state.time.segment, "unknown"),
            "last_sync_ms": raw.state.time.last_sync_ms,
        },
        "physical": {
            "occupied": bool(raw.state.physical.occupied),
            "last_motion_ms": raw.state.physical.last_motion_ms,
        },
        "activity": {
            "mode": ACTIVITY_MODES.get(raw.state.activity.mode, "unknown"),
            "mode_start_ms": raw.state.activity.mode_start_ms,
        },
        "confidence": {
            "belief": int(raw.state.confidence.belief),
            "freshness": int(raw.state.confidence.freshness),
        },
    }

    decision = {
        "permitted": bool(raw.decision.permitted),
        "belief": int(raw.decision.belief),
        "freshness": int(raw.decision.freshness),
        "reason": raw.decision.reason.rstrip(b"\x00").decode("ascii", errors="ignore"),
    }

    intent = {
        "proposed": bool(raw.intent.proposed),
        "action_id": ACTION_IDS.get(raw.intent.action_id, "unknown"),
        "rationale": raw.intent.rationale.rstrip(b"\x00").decode("ascii", errors="ignore"),
    }

    return SystemSnapshot(world=world, decision=decision, intent=intent, timestamp_ms=raw.timestamp_ms)


# ---------------------------------------------------------------------------
# Speech-to-text interface
# ---------------------------------------------------------------------------


class SpeechInterface:
    def __init__(self) -> None:
        if sr is None:
            self.recognizer = None
            self.microphone = None
            print("speech_recognition not installed; falling back to typed input.")
            return

        self.recognizer = sr.Recognizer()
        self.microphone = sr.Microphone()
        with self.microphone as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)

    def capture(self) -> Optional[str]:
        if sr is None or self.recognizer is None or self.microphone is None:
            try:
                text = input("Type your request: ").strip()
            except EOFError:
                return None
            if text:
                print(f"[USER typed] {text}")
                return text
            return None

        with self.microphone as source:
            print("Speak now...")
            audio = self.recognizer.listen(source)
        try:
            text = self.recognizer.recognize_google(audio)
            print(f"[USER] {text}")
            return text
        except sr.UnknownValueError:
            print("Could not understand audio")
            return None
        except sr.RequestError as exc:
            print(f"Speech recognition service error: {exc}")
            return None


# ---------------------------------------------------------------------------
# LLM client
# ---------------------------------------------------------------------------


class LLMClient:
    def __init__(self, provider: str, model: str, api_key: Optional[str]) -> None:
        self.provider = (provider or "openai").lower()
        self.model = model
        self.api_key = api_key
        self.client = None

        if self.provider == "openai":
            self.enabled = OpenAI is not None and api_key
            if self.enabled:
                self.client = OpenAI(api_key=api_key)
        elif self.provider == "google":
            self.enabled = (genai is not None) and api_key
            if self.enabled:
                genai.configure(api_key=api_key)
        else:
            self.enabled = False

    def generate(self, user_text: str, snapshot_json: str) -> str:
        if not self.enabled:
            return fallback_response(user_text, snapshot_json)

        prompt = (
            f"{PROMPT_HEADER}\nUser said:\n\"{user_text}\"\n\nSystem snapshot:\n"
            f"{snapshot_json}\n\nRespond as JARVIS."
        )

        try:
            if self.provider == "openai" and self.client is not None:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                )
                return completion.choices[0].message.content.strip()
            if self.provider == "google" and genai is not None:
                model = genai.GenerativeModel(self.model)
                response = model.generate_content(prompt)
                if hasattr(response, "text") and response.text:
                    return response.text.strip()
                if response.parts:
                    # join all text parts conservatively
                    text = " ".join(getattr(part, "text", "") for part in response.parts)
                    if text.strip():
                        return text.strip()
        except Exception as exc:  # pragma: no cover
            return f"LLM backend error: {exc}"

        return fallback_response(user_text, snapshot_json)


def fallback_response(user_text: str, snapshot_json: str) -> str:
    return (
        "I cannot reach the LLM backend right now, but here is what I know based on the latest "
        f"system snapshot: {snapshot_json[:200]}..."
    )


# ---------------------------------------------------------------------------
# Text-to-speech output
# ---------------------------------------------------------------------------


class SpeechSynthesizer:
    def __init__(self) -> None:
        self.engine = pyttsx3.init()

    def speak(self, text: str) -> None:
        print(f"[JARVIS] {text}")
        self.engine.say(text)
        self.engine.runAndWait()


# ---------------------------------------------------------------------------
# Main conversational loop
# ---------------------------------------------------------------------------


class JarvisInterface:
    def __init__(self, args: argparse.Namespace) -> None:
        self.speech = SpeechInterface()
        self.serial = SerialSnapshotClient(port=args.port, baud=args.baud, timeout=SNAPSHOT_POLL_TIMEOUT)
        self.llm = LLMClient(provider=args.provider, model=args.model, api_key=args.api_key)
        self.synth = SpeechSynthesizer()

    def run(self) -> None:
        while True:
            user_text = self.speech.capture()
            if not user_text:
                continue

            snapshot = self.serial.request_snapshot()
            if snapshot is None:
                response = "I’m unable to retrieve system state right now."
            else:
                snapshot_json = json.dumps(
                    {
                        "world": snapshot.world,
                        "decision": snapshot.decision,
                        "intent": snapshot.intent,
                        "timestamp_ms": snapshot.timestamp_ms,
                    },
                    indent=2,
                )
                response = self.llm.generate(user_text, snapshot_json)

            self.synth.speak(response)
            time.sleep(0.5)


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Laptop conversational interface for Jarvis core")
    parser.add_argument("--port", default="COM8", help="Serial port connected to ESP32 snapshot service")
    parser.add_argument("--baud", type=int, default=9600, help="Serial baud rate")
    parser.add_argument(
        "--provider",
        choices=["openai", "google"],
        default="openai",
        help="LLM provider to use (openai or google).",
    )
    parser.add_argument("--model", default="gpt-4o-mini", help="LLM model identifier")
    parser.add_argument("--api-key", default=None, help="LLM API key (OpenAI-compatible)")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    interface = JarvisInterface(args)
    interface.run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
