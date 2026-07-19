"""Laptop-side distraction evidence emitter.

Captures webcam frames, runs lightweight OpenCV heuristics, and sends
probabilistic EV_ACTIVITY_CLUE events to the ESP32 core over UART.
The ESP32 never receives commands—only advisory evidence lines.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import sys
import time
from pathlib import Path
from typing import Deque, Optional, Tuple

import cv2  # type: ignore
import serial  # type: ignore

# ----------------------------- Tunables ------------------------------------
FRAME_INTERVAL_SEC = 0.2          # sample video roughly 5 FPS for low CPU
WINDOW_SECONDS = 10               # rolling window for heuristics
INFERENCE_PERIOD_SEC = 2.0        # recompute metrics every ~2 seconds
EVENT_MIN_PERIOD_SEC = 15.0       # do not spam ESP32 more often than this
HEAD_MOTION_THRESHOLD = 35.0      # pixels/sec effective motion threshold
GAZE_OFFSET_THRESHOLD = 0.25      # normalized offset (0-0.5)
FACE_MISSING_THRESHOLD = 0.30     # ratio of missing-face samples in rolling window
CONFIDENCE_MIN = 40               # do not emit below this confidence
PORT_DEFAULT = "COM8"
BAUD_DEFAULT = 115200

# ----------------------------- Data Models ---------------------------------

@dataclasses.dataclass
class FrameSample:
    timestamp: float
    face_present: bool
    face_center: Optional[Tuple[float, float]]  # (x, y) in pixels
    gaze_offset: float                          # normalized 0-0.5


@dataclasses.dataclass
class Evidence:
    state: str
    confidence: int
    summary: str


# ----------------------------- Heuristics ----------------------------------

class DistractionEstimator:
    """Tracks face continuity & motion to derive distraction evidence."""

    def __init__(
        self,
        window_seconds: float,
        head_motion_threshold: float,
        gaze_offset_threshold: float,
        face_missing_threshold: float,
    ) -> None:
        self.window_seconds = window_seconds
        self.head_motion_threshold = head_motion_threshold
        self.gaze_offset_threshold = gaze_offset_threshold
        self.face_missing_threshold = face_missing_threshold
        self.samples: Deque[FrameSample] = collections.deque()
        self.last_inference_ts: float = 0.0
        self.last_emit_ts: float = 0.0

    def add_sample(self, sample: FrameSample) -> None:
        self.samples.append(sample)
        cutoff = sample.timestamp - self.window_seconds
        while self.samples and self.samples[0].timestamp < cutoff:
            self.samples.popleft()

    def ready_for_inference(self, now: float) -> bool:
        return (now - self.last_inference_ts) >= INFERENCE_PERIOD_SEC

    def infer(self, now: float) -> Optional[Evidence]:
        self.last_inference_ts = now
        if not self.samples:
            return None

        face_present_count = sum(1 for s in self.samples if s.face_present)
        total = len(self.samples)
        face_missing_ratio = 1.0 - (face_present_count / float(total))

        if face_present_count == 0:
            summary = (
                f"face_missing={face_missing_ratio:.2f} head_motion=0.0 "
                f"gaze_off=1.00"
            )
            return Evidence(state="NO_FACE", confidence=40, summary=summary)

        head_motion_rate = self._compute_head_motion_rate()
        gaze_off_ratio = self._compute_gaze_offset_ratio()

        if face_missing_ratio >= 0.85 and head_motion_rate < 25.0:
            summary = (
                f"face_missing={face_missing_ratio:.2f} head_motion={head_motion_rate:.1f} "
                f"gaze_off={gaze_off_ratio:.2f}"
            )
            return Evidence(state="NO_FACE", confidence=40, summary=summary)

        score = 0
        if face_missing_ratio > self.face_missing_threshold:
            score += 1
        if head_motion_rate > self.head_motion_threshold:
            score += 1
        if gaze_off_ratio > 0.4:
            score += 1

        if score == 0:
            confidence = 85 if face_missing_ratio < 0.15 else 75
            summary = (
                f"face_missing={face_missing_ratio:.2f} head_motion={head_motion_rate:.1f} "
                f"gaze_off={gaze_off_ratio:.2f}"
            )
            return Evidence(state="FOCUSED", confidence=confidence, summary=summary)

        confidence = self._map_score_to_confidence(score)

        summary = (
            f"face_missing={face_missing_ratio:.2f} head_motion={head_motion_rate:.1f} "
            f"gaze_off={gaze_off_ratio:.2f}"
        )
        return Evidence(state="DISTRACTED", confidence=confidence, summary=summary)

    def should_emit(self, now: float) -> bool:
        return (now - self.last_emit_ts) >= EVENT_MIN_PERIOD_SEC

    def mark_emitted(self, now: float) -> None:
        self.last_emit_ts = now

    def _compute_head_motion_rate(self) -> float:
        centers = [s.face_center for s in self.samples if s.face_center]
        if len(centers) < 2:
            return 0.0
        total_motion = 0.0
        for (x0, y0), (x1, y1) in zip(centers, centers[1:]):
            dx = x1 - x0
            dy = y1 - y0
            total_motion += (dx * dx + dy * dy) ** 0.5
        duration = self.samples[-1].timestamp - self.samples[0].timestamp
        if duration <= 0.0:
            return 0.0
        return total_motion / duration

    def _compute_gaze_offset_ratio(self) -> float:
        if not self.samples:
            return 0.0
        off_frames = sum(1 for s in self.samples if s.gaze_offset > self.gaze_offset_threshold)
        return off_frames / float(len(self.samples))

    @staticmethod
    def _map_score_to_confidence(score: int) -> int:
        if score <= 1:
            return 45
        if score == 2:
            return 55
        return 63  # capped below 70


# ----------------------------- Serial I/O ----------------------------------

class EvidenceTransport:
    """Sends distraction clues to ESP32 via UART."""

    def __init__(self, port: str, baud: int) -> None:
        self.serial = None
        try:
            self.serial = serial.Serial(port=port, baudrate=baud, timeout=0)
        except Exception as exc:
            print(f"[Vision] Serial disabled ({exc}); running camera UI only.")

    def send_evidence(self, evidence: Evidence) -> None:
        if self.serial is None:
            return
        payload = f"EV_ACTIVITY_CLUE,DISTRACTED,{evidence.confidence}\n"
        self.serial.write(payload.encode("ascii"))


class EvidenceLogger:
    """Persists evidence summaries for the dashboard to read."""

    def __init__(self, logfile: Optional[str]) -> None:
        path = Path(logfile) if logfile else None
        self.logfile = path if path and path.name else None

    def log(self, evidence: Evidence) -> None:
        if not self.logfile:
            return
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        line = f"{timestamp} | state={evidence.state} | confidence={evidence.confidence} | {evidence.summary}\n"
        try:
            with self.logfile.open("a", encoding="utf-8") as handle:
                handle.write(line)
        except OSError:
            pass


# ----------------------------- Vision Loop ---------------------------------

class VisionDistractionRunner:
    def __init__(self, args: argparse.Namespace) -> None:
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            raise RuntimeError("Cannot open webcam")
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        self.detector = cv2.CascadeClassifier(cascade_path)
        self.scale_factor = args.scale_factor
        self.min_neighbors = args.min_neighbors
        self.min_face_size = args.min_face_size
        self.estimator = DistractionEstimator(
            window_seconds=WINDOW_SECONDS,
            head_motion_threshold=args.head_motion_threshold,
            gaze_offset_threshold=args.gaze_threshold,
            face_missing_threshold=args.face_missing_threshold,
        )
        self.transport = EvidenceTransport(port=args.port, baud=args.baud)
        self.logger = EvidenceLogger(args.log_file)
        self.show_debug = args.debug
        self.last_evidence: Optional[Evidence] = None

        print(
            "[Vision] tuning"
            f" distance={args.distance} angle={args.camera_angle}"
            f" gaze_threshold={args.gaze_threshold:.2f}"
            f" head_motion_threshold={args.head_motion_threshold:.1f}"
            f" face_missing_threshold={args.face_missing_threshold:.2f}"
            f" min_face_size={args.min_face_size}"
        )

    def run(self) -> None:
        try:
            while True:
                start = time.time()
                ret, frame = self.cap.read()
                if not ret:
                    continue
                sample = self._process_frame(frame, start)
                self.estimator.add_sample(sample)

                if self.estimator.ready_for_inference(start):
                    evidence = self.estimator.infer(start)
                    if evidence:
                        self.last_evidence = evidence
                        self.logger.log(evidence)
                        print(f"[VISION] {evidence.state} {evidence.confidence}% :: {evidence.summary}")

                        if (
                            evidence.state == "DISTRACTED"
                            and evidence.confidence >= CONFIDENCE_MIN
                            and self.estimator.should_emit(start)
                        ):
                            self.transport.send_evidence(evidence)
                            self.estimator.mark_emitted(start)
                            print(f"[EVIDENCE] sent confidence={evidence.confidence}")

                if self.show_debug:
                    self._show_debug_frame(frame, sample)

                elapsed = time.time() - start
                sleep_time = FRAME_INTERVAL_SEC - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
        finally:
            self.cap.release()
            cv2.destroyAllWindows()

    def _process_frame(self, frame, timestamp: float) -> FrameSample:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.detector.detectMultiScale(
            gray,
            scaleFactor=self.scale_factor,
            minNeighbors=self.min_neighbors,
            minSize=(self.min_face_size, self.min_face_size),
        )
        if len(faces) == 0:
            return FrameSample(timestamp, False, None, 0.5)

        # Select the largest face
        x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
        center = (x + w / 2.0, y + h / 2.0)
        frame_center = (frame.shape[1] / 2.0, frame.shape[0] / 2.0)
        offset = abs(center[0] - frame_center[0]) / frame.shape[1]
        gaze_offset = min(max(offset, 0.0), 0.5)

        if self.show_debug:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

        return FrameSample(timestamp, True, center, gaze_offset)

    def _show_debug_frame(self, frame, sample: FrameSample) -> None:
        label = "face" if sample.face_present else "no face"
        state = self.last_evidence.state if self.last_evidence else "ANALYZING"
        conf = self.last_evidence.confidence if self.last_evidence else 0
        info = f"{label} gaze={sample.gaze_offset:.2f} | {state} {conf}%"
        if state == "FOCUSED":
            color = (0, 200, 0)
        elif state == "DISTRACTED":
            color = (0, 0, 255)
        elif state == "NO_FACE":
            color = (0, 165, 255)
        else:
            color = (0, 200, 200)
        cv2.putText(frame, info, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 2)
        cv2.imshow("Distraction Monitor", frame)
        if cv2.waitKey(1) & 0xFF == ord("q"):
            raise KeyboardInterrupt


# ----------------------------- CLI ----------------------------------------

def _derive_tuning(distance: str, camera_angle: str) -> tuple[float, float, float, int]:
    """Return gaze, head_motion, face_missing, min_face_size presets."""
    presets = {
        "near": (0.23, 38.0, 0.28, 70),
        "mid": (0.27, 35.0, 0.30, 50),
        "far": (0.32, 35.0, 0.40, 30),
    }
    gaze, motion, missing, min_face_size = presets[distance]
    if camera_angle == "offcenter":
        gaze = min(0.45, gaze + 0.06)
    return gaze, motion, missing, min_face_size


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="OpenCV distraction evidence emitter")
    parser.add_argument("--port", default=PORT_DEFAULT, help="UART/USB port for ESP32")
    parser.add_argument("--baud", type=int, default=BAUD_DEFAULT, help="Serial baud rate")
    parser.add_argument("--debug", action="store_true", help="Show debug preview window")
    parser.add_argument(
        "--distance",
        choices=["near", "mid", "far"],
        default="far",
        help="Approximate camera-to-user distance preset",
    )
    parser.add_argument(
        "--camera-angle",
        choices=["center", "offcenter"],
        default="center",
        help="Camera position relative to user",
    )
    parser.add_argument(
        "--gaze-threshold",
        type=float,
        default=None,
        help="Override gaze offset threshold (0.0-0.5)",
    )
    parser.add_argument(
        "--head-motion-threshold",
        type=float,
        default=None,
        help="Override head motion threshold (pixels/sec)",
    )
    parser.add_argument(
        "--face-missing-threshold",
        type=float,
        default=None,
        help="Override missing-face ratio threshold (0.0-1.0)",
    )
    parser.add_argument(
        "--min-face-size",
        type=int,
        default=None,
        help="Override minimum face size in pixels for detection",
    )
    parser.add_argument(
        "--scale-factor",
        type=float,
        default=1.08,
        help="Haar cascade scale factor",
    )
    parser.add_argument(
        "--min-neighbors",
        type=int,
        default=4,
        help="Haar cascade minNeighbors",
    )
    parser.add_argument(
        "--log-file",
        default="vision_evidence.log",
        help="File to append evidence summaries for the dashboard (empty to disable)",
    )

    args = parser.parse_args(argv)

    preset_gaze, preset_motion, preset_missing, preset_min_face_size = _derive_tuning(
        args.distance,
        args.camera_angle,
    )
    args.gaze_threshold = args.gaze_threshold if args.gaze_threshold is not None else preset_gaze
    args.head_motion_threshold = (
        args.head_motion_threshold if args.head_motion_threshold is not None else preset_motion
    )
    args.face_missing_threshold = (
        args.face_missing_threshold if args.face_missing_threshold is not None else preset_missing
    )
    args.min_face_size = args.min_face_size if args.min_face_size is not None else preset_min_face_size

    return args


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    runner = VisionDistractionRunner(args)
    runner.run()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
