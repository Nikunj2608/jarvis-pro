import argparse
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pyttsx3
import speech_recognition as sr
from pyrnnoise import RNNoise

from jarvis_core import JARVISCore, Event, EventType, ActionIntent


class ActivityDistractionMonitor:
    """Tail activity log and trigger callback on sustained distraction."""

    def __init__(self, log_path: Path, on_alert, threshold_seconds: float = 12.0, cooldown_seconds: float = 35.0):
        self.log_path = log_path
        self.on_alert = on_alert
        self.threshold_seconds = threshold_seconds
        self.cooldown_seconds = cooldown_seconds
        self.running = False
        self.thread = None
        self._streak_start_ts = None
        self._last_distracted_ts = None
        self._last_alert_ts = 0.0
        self._streak_alerted = False

    def start(self):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        print(f"[Assist] Activity monitor enabled: {self.threshold_seconds:.0f}s distraction threshold")

    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)

    def _loop(self):
        while self.running:
            if not self.log_path.exists():
                time.sleep(0.5)
                continue

            try:
                # Tail from end so old history does not trigger stale alerts.
                with self.log_path.open("r", encoding="utf-8", errors="ignore") as handle:
                    handle.seek(0, 2)
                    while self.running:
                        pos = handle.tell()
                        line = handle.readline()
                        if not line:
                            handle.seek(pos)
                            time.sleep(0.25)
                            continue
                        self._consume(line.strip())
            except OSError:
                time.sleep(0.5)

    def _consume(self, line: str):
        ts, state, confidence = self._parse_line(line)
        if ts is None or state is None:
            return

        if state == "DISTRACTED":
            if self._streak_start_ts is None:
                self._streak_start_ts = ts
                self._streak_alerted = False
            elif self._last_distracted_ts is not None and (ts - self._last_distracted_ts) > 5.0:
                self._streak_start_ts = ts
                self._streak_alerted = False

            self._last_distracted_ts = ts
            duration = ts - self._streak_start_ts
            cooldown_ok = (ts - self._last_alert_ts) >= self.cooldown_seconds
            if duration >= self.threshold_seconds and (not self._streak_alerted) and cooldown_ok:
                self._last_alert_ts = ts
                self._streak_alerted = True
                self.on_alert(duration, confidence)
            return

        if state in {"FOCUSED", "NO_FACE"}:
            self._streak_start_ts = None
            self._last_distracted_ts = None
            self._streak_alerted = False

    @staticmethod
    def _parse_line(line: str):
        if "| state=" not in line:
            return None, None, None

        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 2:
            return None, None, None

        try:
            ts = datetime.strptime(parts[0], "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            return None, None, None

        state = None
        confidence = 0
        for token in parts[1:]:
            if token.startswith("state="):
                state = token.split("=", 1)[1].strip().upper()
            elif token.startswith("confidence="):
                try:
                    confidence = int(token.split("=", 1)[1].strip())
                except ValueError:
                    confidence = 0

        return ts, state, confidence


class VoiceInterface:
    def __init__(self, jarvis_core: JARVISCore):
        self.jarvis = jarvis_core
        self.recognizer = sr.Recognizer()
        self.running = False
        try:
            self.denoiser = RNNoise(sample_rate=48000)
            print("[Voice] RNNoise initialized")
        except Exception as e:
            print(f"[Voice] RNNoise not available: {e}")
            self.denoiser = None

    def denoise_audio(self, raw_data):
        if self.denoiser is None:
            return raw_data
        try:
            audio_np = np.frombuffer(raw_data, dtype=np.int16).copy()
            frame_size = 480
            rem = len(audio_np) % frame_size
            if rem:
                audio_np = np.pad(audio_np, (0, frame_size - rem), mode="constant")
            out = []
            for i in range(0, len(audio_np), frame_size):
                frame = audio_np[i : i + frame_size]
                try:
                    result = self.denoiser.denoise_frame(frame)
                    if result is None:
                        out.append(frame)
                        continue
                    _prob, den = result
                    out.append(np.asarray(den if den is not None else frame, dtype=np.int16))
                except Exception:
                    out.append(frame)
            if not out:
                return raw_data
            return np.concatenate(out).astype(np.int16).tobytes()
        except Exception:
            return raw_data

    def speak(self, text: str):
        print(f"JARVIS: {text}")

        def _speak():
            try:
                engine = pyttsx3.init(driverName="sapi5")
                engine.setProperty("rate", 170)
                engine.setProperty("volume", 1.0)
                engine.say(text)
                engine.runAndWait()
                engine.stop()
            except Exception as e:
                print(f"[TTS] Error: {e}")

        t = threading.Thread(target=_speak, daemon=True)
        t.start()
        t.join(timeout=10)

    def listen_loop(self):
        print("[Voice] Starting voice interface...")
        self.speak("JARVIS systems online. All subsystems ready.")
        try:
            with sr.Microphone(sample_rate=48000) as source:
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
                print("[Voice] Calibration complete. Listening for commands.\n")
                while self.running:
                    try:
                        print("[Listening...]")
                        audio = self.recognizer.listen(source, phrase_time_limit=5, timeout=10)
                        clean = self.denoise_audio(audio.get_raw_data())
                        text = self.recognizer.recognize_google(sr.AudioData(clean, 48000, 2))
                        print(f"You: {text}")
                        response = self.process_command(text)
                        self.speak(response)
                    except sr.WaitTimeoutError:
                        continue
                    except sr.UnknownValueError:
                        continue
                    except Exception as e:
                        print(f"[Voice] Error: {e}")
        except Exception as e:
            print(f"[Voice] Fatal error: {e}")

    def process_command(self, text: str) -> str:
        text_lower = text.lower()
        if any(x in text_lower for x in ["exit", "quit", "stop", "shutdown"]):
            self.running = False
            return "Understood. Shutting down all systems. Goodbye."

        if any(x in text_lower for x in ["status", "report", "how are you"]):
            state = self.jarvis.get_world_state()
            temp_text = state.temperature if state.temperature is not None else "unknown"
            hum_text = state.humidity if state.humidity is not None else "unknown"
            return (
                f"All systems operational. Activity mode: {state.activity_mode.name}. "
                f"Environment: {temp_text} degrees, {hum_text} percent humidity. "
                f"System confidence: {state.belief} percent."
            )

        if any(x in text_lower for x in ["temperature", "humidity", "environment", "sensor"]):
            state = self.jarvis.get_world_state()
            if state.temperature is not None and state.humidity is not None:
                self.jarvis.emit_event(Event(type=EventType.VOICE_COMMAND, timestamp=time.time(), data={"command": text}))
                sensor_data = f"Temperature: {state.temperature} C, Humidity: {state.humidity}%"
                resp = self.jarvis.esp.analyze_with_llm(sensor_data, task_type="sensor_analysis")
                return resp if resp else f"Current temperature is {state.temperature} and humidity is {state.humidity}."
            return "Environmental sensors are not currently available."

        return self.jarvis.process_voice_command(text)

    def start(self):
        self.running = True
        self.listen_loop()

    def stop(self):
        self.running = False


class JARVISUnified:
    def __init__(self, esp_port: str = "COM8", camera_id: int = 0, enable_core_vision: bool = True):
        self.core = JARVISCore(esp_port=esp_port, camera_id=camera_id, enable_vision=enable_core_vision)
        self.enable_core_vision = enable_core_vision
        self.voice = VoiceInterface(self.core)
        self.activity_monitor = ActivityDistractionMonitor(
            log_path=Path(__file__).with_name("activity_log.txt"),
            on_alert=self._on_sustained_distraction,
            threshold_seconds=12.0,
            cooldown_seconds=35.0,
        )
        self._setup_callbacks()

    def _on_sustained_distraction(self, duration_sec: float, confidence: int):
        msg = (
            f"I noticed you were distracted for {duration_sec:.0f} seconds at {confidence} percent confidence. "
            "Quick reset: shoulders back, one deep breath, and refocus on one next action."
        )
        print(f"[Assist] {msg}")
        self.voice.speak(msg)

    def _setup_callbacks(self):
        def on_break(_intent: ActionIntent, explanation: str):
            self.voice.speak(f"I suggest taking a break. {explanation}")

        def on_temp(_intent: ActionIntent, explanation: str):
            self.voice.speak(f"Temperature alert. {explanation}")

        def on_observe(_intent: ActionIntent, explanation: str):
            print(f"[JARVIS] Silent observation: {explanation}")

        self.core.register_action_callback("SUGGEST_BREAK", on_break)
        self.core.register_action_callback("ALERT_TEMPERATURE", on_temp)
        self.core.register_action_callback("OBSERVE", on_observe)

    def start(self):
        print("\n" + "=" * 70)
        print("               JARVIS UNIFIED SYSTEM")
        print("          Real-Time AI Assistant")
        print("=" * 70)
        if self.enable_core_vision:
            print("  [Vision] Core OpenCV loop enabled")
        else:
            print("  [Vision] External UI mode enabled")
        print("=" * 70 + "\n")

        self.core.start()
        self.activity_monitor.start()

        try:
            self.voice.start()
        finally:
            self.stop()

    def stop(self):
        print("\n[System] Initiating shutdown sequence...")
        self.activity_monitor.stop()
        self.voice.stop()
        self.core.stop()
        print("[System] JARVIS terminated.\n")


def parse_args(argv):
    parser = argparse.ArgumentParser(description="JARVIS unified launcher")
    parser.add_argument("--esp-port", default="COM8", help="ESP32 serial port")
    parser.add_argument("--camera-id", type=int, default=0, help="Camera device id")
    parser.add_argument(
        "--disable-core-vision",
        action="store_true",
        help="Disable built-in vision loop when running standalone vision UI in parallel",
    )
    return parser.parse_args(argv)


if __name__ == "__main__":
    args = parse_args(sys.argv[1:])
    jarvis = JARVISUnified(
        esp_port=args.esp_port,
        camera_id=args.camera_id,
        enable_core_vision=not args.disable_core_vision,
    )

    def signal_handler(_sig, _frame):
        print("\n[System] Shutdown signal received")
        jarvis.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    try:
        jarvis.start()
    except Exception as e:
        print(f"[System] Fatal error: {e}")
        jarvis.stop()
