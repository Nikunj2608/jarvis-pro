"""
JARVIS Core - Unified Real-Time AI System
==========================================

Integrates:
- Voice commands (jarvis_voice.py)
- Vision monitoring (vision_distraction.py)
- Sensor data (serial_client.py)
- LLM reasoning (Phi-2)
- Event-driven decision making

Architecture:
    WorldState → EventReducer → DecisionGate → ActionIntent → LLM Advisor
"""

from __future__ import annotations

import threading
import queue
import time
import dataclasses
import os
from collections import deque
from enum import Enum
from typing import Optional, Dict, Any, Callable
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from serial_client import ESP32Client


# ============ EVENT SYSTEM ============

class EventType(Enum):
    """Mirrors ESP32 event types"""
    TIME_TICK = 0
    PRESENCE = 1
    ACTIVITY_CLUE = 2
    OVERRIDE = 3
    ENV_UPDATE = 4
    MODE_CONFIRM = 5
    FAULT = 6
    VOICE_COMMAND = 7      # New: Voice input
    VISION_UPDATE = 8       # New: Vision analysis


class ActivityMode(Enum):
    """User activity states"""
    IDLE = 0
    FOCUS = 1
    DISTRACTED = 2
    OVERRIDE = 3


class DaySegment(Enum):
    """Time of day context"""
    NIGHT = 0
    MORNING = 1
    AFTERNOON = 2
    EVENING = 3


@dataclasses.dataclass
class Event:
    """Unified event structure"""
    type: EventType
    timestamp: float
    value: int = 0
    confidence: int = 0
    data: Optional[Dict[str, Any]] = None


@dataclasses.dataclass
class WorldState:
    """Central state representation"""
    # Temporal
    day_segment: DaySegment
    last_sync_ms: int
    
    # Physical
    room_occupied: bool
    last_motion_ms: int
    
    # Activity
    activity_mode: ActivityMode
    mode_start_ms: int

    # Optional environment readings
    temperature: Optional[float] = None
    humidity: Optional[float] = None
    distraction_confidence: int = 0
    
    # Confidence
    belief: int = 50           # 0-100 confidence in current state
    freshness: int = 100       # Decay-driven data validity


@dataclasses.dataclass
class DecisionExplanation:
    """Decision gate output"""
    permitted: bool
    belief: int
    freshness: int
    reason: str


@dataclasses.dataclass
class ActionIntent:
    """Proposed action from reasoning"""
    proposed: bool
    action_id: str
    rationale: str
    priority: int = 0


# ============ VISION SYSTEM ============

class VisionMonitor:
    """Real-time vision-based distraction detection"""
    
    def __init__(self, camera_id: int = 0):
        self.camera_id = camera_id
        self.cap = None
        self.face_cascade = None
        self.running = False
        self.last_inference_ts = 0.0
        self.inference_interval = 2.0  # seconds
        self.distraction_history = deque(maxlen=5)
        
        # Load face detector
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            print("[Vision] Face detector loaded")
        except Exception as e:
            print(f"[Vision] Warning: Could not load face detector: {e}")
    
    def start(self):
        """Initialize camera"""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if self.cap.isOpened():
                self.running = True
                print("[Vision] Camera initialized")
                return True
        except Exception as e:
            print(f"[Vision] Error: {e}")
        return False
    
    def stop(self):
        """Release camera"""
        self.running = False
        if self.cap:
            self.cap.release()
    
    def analyze_frame(self) -> Optional[Event]:
        """Analyze current frame for distraction indicators"""
        if not self.cap or not self.cap.isOpened():
            return None
        
        now = time.time()
        if (now - self.last_inference_ts) < self.inference_interval:
            return None
        
        self.last_inference_ts = now
        
        ret, frame = self.cap.read()
        if not ret:
            return None
        
        # Detect faces
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.08,
            minNeighbors=4,
            minSize=(50, 50),
        ) if self.face_cascade else []

        face_present = len(faces) > 0
        gaze_offset = 0.5
        raw_distracted = 1

        if face_present:
            # Use the largest face as the primary subject.
            x, y, w, h = max(faces, key=lambda box: box[2] * box[3])
            face_center_x = x + (w / 2.0)
            frame_center_x = frame.shape[1] / 2.0
            gaze_offset = min(max(abs(face_center_x - frame_center_x) / frame.shape[1], 0.0), 0.5)
            raw_distracted = 1 if gaze_offset > 0.28 else 0

        # Smooth quick fluctuations so activity state is stable.
        self.distraction_history.append(raw_distracted)
        distracted_ratio = sum(self.distraction_history) / max(len(self.distraction_history), 1)
        value = 1 if distracted_ratio >= 0.6 else 0

        if not face_present:
            confidence = 78
        elif value == 1:
            confidence = int(min(92, 65 + (distracted_ratio * 20)))
        else:
            confidence = int(max(65, 90 - (distracted_ratio * 15)))
        
        return Event(
            type=EventType.ACTIVITY_CLUE,
            timestamp=now,
            value=value,
            confidence=confidence,
            data={
                "faces_detected": len(faces),
                "gaze_offset": gaze_offset,
                "distracted_ratio": distracted_ratio,
            }
        )


# ============ EVENT REDUCER ============

class EventReducer:
    """
    Processes events and updates world state.
    Implements belief updates and state transitions.
    """
    
    BELIEF_THRESHOLD = 60
    FRESHNESS_THRESHOLD = 60
    
    def __init__(self, world_state: WorldState):
        self.world = world_state
    
    def process_event(self, event: Event) -> WorldState:
        """Update world state based on event"""
        
        if event.type == EventType.PRESENCE:
            self.world.room_occupied = bool(event.value)
            self.world.last_motion_ms = int(event.timestamp * 1000)
            self.world.belief = min(100, self.world.belief + 10)
            
        elif event.type == EventType.ACTIVITY_CLUE:
            previous_mode = self.world.activity_mode
            if event.value == 1:  # Distracted
                self.world.distraction_confidence = max(self.world.distraction_confidence, event.confidence)
                if event.confidence >= 55:
                    self.world.activity_mode = ActivityMode.DISTRACTED
            else:  # Focused
                self.world.distraction_confidence = max(0, self.world.distraction_confidence - 20)
                if self.world.distraction_confidence < 40:
                    self.world.activity_mode = ActivityMode.FOCUS

            if self.world.activity_mode != previous_mode:
                self.world.mode_start_ms = int(event.timestamp * 1000)

            self.world.belief = min(100, self.world.belief + 2)
            
        elif event.type == EventType.ENV_UPDATE:
            if event.data:
                self.world.temperature = event.data.get('temperature')
                self.world.humidity = event.data.get('humidity')
            self.world.freshness = 100
            
        elif event.type == EventType.VOICE_COMMAND:
            # Voice command might override state
            self.world.belief = min(100, self.world.belief + 5)
            
        elif event.type == EventType.TIME_TICK:
            # Decay freshness over time
            self.world.freshness = max(0, self.world.freshness - 1)
        
        return self.world


# ============ DECISION GATE ============

class DecisionGate:
    """
    Evaluates whether actions are permitted based on world state.
    Implements confidence thresholds and policy rules.
    """
    
    def evaluate(self, world: WorldState) -> DecisionExplanation:
        """Determine if intervention is permitted"""
        
        permitted = False
        reason = "Insufficient confidence"
        
        # Check belief and freshness thresholds
        if world.belief >= 60 and world.freshness >= 60:
            permitted = True
            reason = "High confidence state"
        
        # Policy: Don't interrupt if user is focused
        if world.activity_mode == ActivityMode.FOCUS:
            permitted = False
            reason = "User is focused - observing silently"
        
        # Policy: Intervene if distracted for too long
        if world.activity_mode == ActivityMode.DISTRACTED:
            if world.distraction_confidence > 70:
                permitted = True
                reason = "High distraction detected"
        
        return DecisionExplanation(
            permitted=permitted,
            belief=world.belief,
            freshness=world.freshness,
            reason=reason
        )


# ============ ACTION INTENT ============

class ActionIntentEngine:
    """
    Proposes actions based on decision gate output and world state.
    """
    
    def evaluate(self, world: WorldState, decision: DecisionExplanation) -> ActionIntent:
        """Generate action proposal"""
        
        if not decision.permitted:
            return ActionIntent(
                proposed=False,
                action_id="NONE",
                rationale="No action needed",
                priority=0
            )
        
        # Suggest break if distracted
        if world.activity_mode == ActivityMode.DISTRACTED:
            return ActionIntent(
                proposed=True,
                action_id="SUGGEST_BREAK",
                rationale=f"Distraction detected ({world.distraction_confidence}% confidence)",
                priority=7
            )
        
        # Environmental comfort check
        if world.temperature and world.temperature > 28:
            return ActionIntent(
                proposed=True,
                action_id="ALERT_TEMPERATURE",
                rationale=f"Temperature high: {world.temperature}°C",
                priority=5
            )
        
        return ActionIntent(
            proposed=False,
            action_id="OBSERVE",
            rationale="Monitoring state",
            priority=0
        )


# ============ LLM ADVISOR ============

class LLMAdvisor:
    """
    Uses Phi-2 to generate natural language explanations and advice.
    Integrates world state, decisions, and actions into coherent responses.
    """
    
    def __init__(self, esp_client: ESP32Client):
        self.esp = esp_client
    
    def generate_explanation(self, world: WorldState, decision: DecisionExplanation, 
                           intent: ActionIntent) -> str:
        """Generate natural language explanation using Phi-2"""
        
        # Construct context for LLM
        context = f"""Current System State:
- Activity: {world.activity_mode.name}
- Distraction Level: {world.distraction_confidence}%
- Room Occupied: {world.room_occupied}
- Environment: {world.temperature}°C, {world.humidity}% humidity
- Belief: {world.belief}/100
- Freshness: {world.freshness}/100

Decision: {decision.reason}
Action Proposed: {intent.action_id} - {intent.rationale}

Provide a brief, actionable summary for the user."""
        
        if self.esp.use_llm:
            response = self.esp.query_jarvis(context)
            return response if response else "System monitoring active."
        else:
            return intent.rationale if intent.proposed else "All systems normal."


# ============ JARVIS CORE ============

class JARVISCore:
    """
    Main orchestrator - coordinates all subsystems.
    Implements event loop and decision pipeline.
    """
    
    def __init__(self, esp_port: str = "COM8", camera_id: int = 0, enable_vision: bool = True):
        # Initialize subsystems
        self.esp = ESP32Client(port=esp_port, use_llm=True)
        self.vision = VisionMonitor(camera_id=camera_id)
        force_disable_vision = os.getenv("JARVIS_DISABLE_CORE_VISION", "").strip().lower() in {
            "1", "true", "yes", "on"
        }
        self.enable_vision = enable_vision and not force_disable_vision
        
        # Initialize state and reasoning
        self.world = WorldState(
            day_segment=DaySegment.AFTERNOON,
            last_sync_ms=int(time.time() * 1000),
            room_occupied=False,
            last_motion_ms=0,
            activity_mode=ActivityMode.IDLE,
            mode_start_ms=int(time.time() * 1000)
        )
        
        self.event_reducer = EventReducer(self.world)
        self.decision_gate = DecisionGate()
        self.action_engine = ActionIntentEngine()
        self.llm_advisor = LLMAdvisor(self.esp)
        
        # Event queue
        self.event_queue: queue.Queue[Event] = queue.Queue(maxsize=100)
        
        # Control
        self.running = False
        self.threads = []
        
        # Callbacks
        self.action_callbacks: Dict[str, Callable] = {}
        self.activity_log_path = Path(__file__).with_name("activity_log.txt")
        self.activity_log_lock = threading.Lock()
        self.last_state_log_ts = 0.0

    def _log_activity(self, message: str):
        """Write activity logs to console and a rolling text log file."""
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | {message}"
        print(f"[ACTIVITY] {message}")
        try:
            with self.activity_log_lock:
                with self.activity_log_path.open("a", encoding="utf-8") as handle:
                    handle.write(line + "\n")
        except OSError:
            pass
    
    def register_action_callback(self, action_id: str, callback: Callable):
        """Register callback for specific action"""
        self.action_callbacks[action_id] = callback
    
    def emit_event(self, event: Event):
        """Add event to queue"""
        try:
            self.event_queue.put(event, block=False)
        except queue.Full:
            print("[JARVIS] Warning: Event queue full, dropping event")
    
    def _vision_loop(self):
        """Vision monitoring thread"""
        print("[JARVIS] Vision loop started")
        while self.running:
            try:
                event = self.vision.analyze_frame()
                if event:
                    vision_state = "DISTRACTED" if event.value == 1 else "FOCUSED"
                    faces = event.data.get("faces_detected", 0) if event.data else 0
                    gaze = event.data.get("gaze_offset", 0.0) if event.data else 0.0
                    ratio = event.data.get("distracted_ratio", 0.0) if event.data else 0.0
                    self._log_activity(
                        f"vision={vision_state} confidence={event.confidence}% "
                        f"faces={faces} gaze_offset={gaze:.2f} distracted_ratio={ratio:.2f}"
                    )
                    self.emit_event(event)
                time.sleep(0.2)  # ~5 FPS
            except Exception as e:
                print(f"[Vision] Error: {e}")
                time.sleep(1)
    
    def _sensor_loop(self):
        """Sensor monitoring thread"""
        print("[JARVIS] Sensor loop started")
        while self.running:
            try:
                # Get environmental data
                data = self.esp.get_env(analyze=False)
                if data and isinstance(data, str):
                    # Parse sensor data
                    # Assuming format: "TEMP:25.5,HUM:60"
                    event_data = {}
                    if "TEMP:" in data:
                        try:
                            temp = float(data.split("TEMP:")[1].split(",")[0])
                            event_data['temperature'] = temp
                        except:
                            pass
                    if "HUM:" in data:
                        try:
                            hum = float(data.split("HUM:")[1].split(",")[0])
                            event_data['humidity'] = hum
                        except:
                            pass
                    
                    if event_data:
                        self.emit_event(Event(
                            type=EventType.ENV_UPDATE,
                            timestamp=time.time(),
                            data=event_data
                        ))

                        temp_str = f"{event_data.get('temperature', 'n/a')}"
                        hum_str = f"{event_data.get('humidity', 'n/a')}"
                        self._log_activity(f"sensor temp={temp_str}C humidity={hum_str}%")

                    if "OCC:" in data:
                        try:
                            occ = int(data.split("OCC:")[1].split(",")[0])
                            self.emit_event(Event(
                                type=EventType.PRESENCE,
                                timestamp=time.time(),
                                value=occ,
                                confidence=80,
                            ))
                            self._log_activity(f"presence={'OCCUPIED' if occ else 'EMPTY'}")
                        except Exception:
                            pass
                
                time.sleep(5)  # Update every 5 seconds
            except Exception as e:
                print(f"[Sensor] Error: {e}")
                time.sleep(5)
    
    def _time_tick_loop(self):
        """Time tick generator"""
        while self.running:
            self.emit_event(Event(
                type=EventType.TIME_TICK,
                timestamp=time.time()
            ))
            time.sleep(1)
    
    def _reasoning_loop(self):
        """Main reasoning and decision loop"""
        print("[JARVIS] Reasoning loop started")
        last_action_time = 0
        action_cooldown = 15.0  # Don't spam actions
        
        while self.running:
            try:
                # Get next event
                event = self.event_queue.get(timeout=1)
                
                # Update world state
                self.world = self.event_reducer.process_event(event)
                
                # Evaluate decision
                decision = self.decision_gate.evaluate(self.world)
                
                # Generate action intent
                intent = self.action_engine.evaluate(self.world, decision)
                
                # Execute action if proposed and cooldown expired
                now = time.time()

                if (now - self.last_state_log_ts) >= 3.0:
                    decision_state = "PERMITTED" if decision.permitted else "BLOCKED"
                    temp = self.world.temperature if self.world.temperature is not None else "n/a"
                    hum = self.world.humidity if self.world.humidity is not None else "n/a"
                    self._log_activity(
                        f"mode={self.world.activity_mode.name} distraction={self.world.distraction_confidence}% "
                        f"belief={self.world.belief}% freshness={self.world.freshness}% "
                        f"temp={temp}C humidity={hum}% decision={decision_state}"
                    )
                    self.last_state_log_ts = now

                if intent.proposed and (now - last_action_time) > action_cooldown:
                    print(f"\n[JARVIS] Action Proposed: {intent.action_id}")
                    print(f"[JARVIS] Rationale: {intent.rationale}")
                    self._log_activity(f"action_proposed={intent.action_id} rationale={intent.rationale}")
                    
                    # Generate LLM explanation
                    explanation = self.llm_advisor.generate_explanation(
                        self.world, decision, intent
                    )
                    print(f"[JARVIS] Explanation: {explanation}")
                    
                    # Execute callback if registered
                    if intent.action_id in self.action_callbacks:
                        self.action_callbacks[intent.action_id](intent, explanation)
                    
                    last_action_time = now
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"[Reasoning] Error: {e}")
    
    def start(self):
        """Start all subsystems"""
        print("\n" + "="*60)
        print("JARVIS CORE SYSTEM - Real-Time AI")
        print("="*60)
        
        self.running = True
        
        # Start vision
        if self.enable_vision:
            if self.vision.start():
                vision_thread = threading.Thread(target=self._vision_loop, daemon=True)
                vision_thread.start()
                self.threads.append(vision_thread)
        else:
            self._log_activity("core_vision=DISABLED external_vision_ui=EXPECTED")
        
        # Start sensor monitoring
        sensor_thread = threading.Thread(target=self._sensor_loop, daemon=True)
        sensor_thread.start()
        self.threads.append(sensor_thread)
        
        # Start time tick
        tick_thread = threading.Thread(target=self._time_tick_loop, daemon=True)
        tick_thread.start()
        self.threads.append(tick_thread)
        
        # Start reasoning loop
        reasoning_thread = threading.Thread(target=self._reasoning_loop, daemon=True)
        reasoning_thread.start()
        self.threads.append(reasoning_thread)
        
        print("[JARVIS] All systems online")
        print("="*60 + "\n")
    
    def stop(self):
        """Stop all subsystems"""
        print("\n[JARVIS] Shutting down...")
        self.running = False
        if self.enable_vision:
            self.vision.stop()
        
        # Wait for threads
        for thread in self.threads:
            thread.join(timeout=2)
        
        print("[JARVIS] All systems terminated")
    
    def get_world_state(self) -> WorldState:
        """Get current world state"""
        return self.world
    
    def process_voice_command(self, command: str) -> str:
        """Process voice command and get response"""
        # Emit voice command event
        self.emit_event(Event(
            type=EventType.VOICE_COMMAND,
            timestamp=time.time(),
            data={"command": command}
        ))
        
        # Get LLM response with current context
        decision = self.decision_gate.evaluate(self.world)
        intent = self.action_engine.evaluate(self.world, decision)
        
        # Use LLM for response
        response = self.esp.query_jarvis(f"User said: {command}\n\nProvide a helpful response.")
        return response if response else "Understood."


# ============ EXAMPLE USAGE ============

if __name__ == "__main__":
    import signal
    
    # Initialize JARVIS
    jarvis = JARVISCore(esp_port="COM8", camera_id=0)
    
    # Register action callbacks
    def on_break_suggestion(intent: ActionIntent, explanation: str):
        print(f"\n>>> JARVIS suggests: {explanation}")
    
    def on_temperature_alert(intent: ActionIntent, explanation: str):
        print(f"\n>>> JARVIS alerts: {explanation}")
    
    jarvis.register_action_callback("SUGGEST_BREAK", on_break_suggestion)
    jarvis.register_action_callback("ALERT_TEMPERATURE", on_temperature_alert)
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        jarvis.stop()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start system
    jarvis.start()
    
    # Keep running
    try:
        while True:
            time.sleep(1)
            # Optionally print state
            # state = jarvis.get_world_state()
            # print(f"[State] Mode: {state.activity_mode.name}, Belief: {state.belief}")
    except KeyboardInterrupt:
        jarvis.stop()
