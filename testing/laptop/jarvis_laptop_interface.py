"""
JARVIS Laptop Interface - Evidence Provider & Narrator
======================================================

ARCHITECTURE:
    ESP32 C++ Core (Authoritative Intelligence)
         ↑              ↓
    Events        Snapshots
         ↑              ↓
    Laptop (This code - Advisory Only)
    - Vision → EV_ACTIVITY_CLUE
    - Voice → EV_VOICE_COMMAND  
    - LLM → Narration only

CRITICAL: This code does NOT make decisions.
It provides evidence and narrates the C++ core's decisions.
"""

import threading
import queue
import time
import struct
import dataclasses
from enum import IntEnum
from typing import Optional, Dict, Any

import cv2
import numpy as np
import serial
from serial.tools import list_ports

from sensor_providers import DHT11Provider, PIRProvider
from automation_executor import AutomationExecutor, ActionId


# ============ C++ CORE EVENT TYPES (MIRROR) ============

class EventType(IntEnum):
    """Mirror of events.h - DO NOT MODIFY"""
    EV_TIME_TICK = 0
    EV_PRESENCE = 1
    EV_ACTIVITY_CLUE = 2
    EV_OVERRIDE = 3
    EV_ENV_UPDATE = 4
    EV_MODE_CONFIRM = 5
    EV_SESSION_START = 6  # NEW: Session tracking
    EV_FAULT = 7


class EvidenceSource(IntEnum):
    """Mirror of events.h - Evidence source weights"""
    SOURCE_MOTION_PIR = 0
    SOURCE_VISION_LAPTOP = 1
    SOURCE_VOICE_ACTIVITY = 2
    SOURCE_MANUAL_OVERRIDE = 3
    SOURCE_ENV_SENSOR = 4
    SOURCE_TIME_INFERENCE = 5


class ActivityMode(IntEnum):
    """Mirror of world_state.h"""
    ACTIVITY_MODE_IDLE = 0
    ACTIVITY_MODE_FOCUS = 1
    ACTIVITY_MODE_DISTRACTED = 2
    ACTIVITY_MODE_OVERRIDE = 3


class DaySegment(IntEnum):
    """Mirror of world_state.h"""
    DAY_SEGMENT_NIGHT = 0
    DAY_SEGMENT_MORNING = 1
    DAY_SEGMENT_AFTERNOON = 2
    DAY_SEGMENT_EVENING = 3


# ============ SNAPSHOT STRUCTURE (MIRROR C++) ============

@dataclasses.dataclass
class SystemSnapshot:
    """
    Mirror of snapshot_service.h::SystemSnapshot
    Received from ESP32 C++ core.
    This represents the AUTHORITATIVE state.
    """
    # WorldState - TemporalState
    day_segment: DaySegment
    last_sync_ms: int
    
    # WorldState - PhysicalState
    room_occupied: bool
    last_motion_ms: int
    
    # WorldState - ActivityState
    activity_mode: ActivityMode
    mode_start_ms: int
    
    # WorldState - ConfidenceState
    belief: int
    freshness: int
    uncertainty_cause: int  # NEW: UncertaintyCause enum value
    
    # WorldState - SessionState (NEW)
    active_session_id: int
    session_start_ms: int
    session_count_today: int
    
    # WorldState - HabitStats (NEW)
    focus_minutes_today: int
    distraction_count_today: int
    typical_focus_hour: int
    typical_distraction_hour: int
    
    # DecisionExplanation
    decision_permitted: bool
    decision_belief: int
    decision_freshness: int
    decision_reason: str
    
    # ActionIntent
    intent_proposed: bool
    intent_action_id: int
    intent_rationale: str
    
    # Metadata
    timestamp_ms: int


# ============ ESP32 COMMUNICATION ============

class ESP32Interface:
    """
    Bidirectional interface with ESP32 C++ core.
    
    SEND: Events (evidence only)
    RECEIVE: Snapshots (authoritative state)
    """
    
    SNAPSHOT_HEADER = 0xA5
    
    def __init__(self, port: str = "COM3", baud: int = 115200):
        self.port = port
        self.baud = baud
        self.ser: Optional[serial.Serial] = None
        self.running = False
        
        # Latest snapshot from C++ core
        self.latest_snapshot: Optional[SystemSnapshot] = None
        self.snapshot_lock = threading.Lock()
        
    def connect(self) -> bool:
        """Establish serial connection"""
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.1)
            print(f"[ESP32] Connected to {self.port}")
            return True
        except Exception as e:
            print(f"[ESP32] Connection failed: {e}")
            return False
    
    def disconnect(self):
        """Close serial connection"""
        if self.ser:
            self.ser.close()
    
    def send_event(self, event_type: EventType, value: int = 0, confidence: int = 0, 
                   source: EvidenceSource = EvidenceSource.SOURCE_VISION_LAPTOP) -> bool:
        """
        Send event to ESP32 C++ core.
        Events are ADVISORY EVIDENCE ONLY.
        NOW includes evidence source for belief fusion.
        """
        if not self.ser or not self.ser.is_open:
            return False
        
        try:
            # Updated protocol: "EVENT <type> <value> <confidence> <source>\n"
            cmd = f"EVENT {event_type} {value} {confidence} {source}\n"
            self.ser.write(cmd.encode('ascii'))
            self.ser.flush()
            return True
        except Exception as e:
            print(f"[ESP32] Event send failed: {e}")
            return False
    
    def request_snapshot(self) -> bool:
        """Request snapshot from ESP32"""
        if not self.ser or not self.ser.is_open:
            return False
        
        try:
            # Send request byte
            self.ser.write(b'\x01')
            self.ser.flush()
            return True
        except Exception as e:
            print(f"[ESP32] Snapshot request failed: {e}")
            return False
    
    def receive_snapshot(self) -> Optional[SystemSnapshot]:
        """
        Receive snapshot from ESP32.
        This is the AUTHORITATIVE state from C++ core.
        """
        if not self.ser or not self.ser.is_open:
            return None
        
        try:
            # Look for header marker
            while self.ser.in_waiting > 0:
                byte = self.ser.read(1)
                if byte[0] == self.SNAPSHOT_HEADER:
                    # Read frame
                    frame_data = self.ser.read(100)  # Adjust size as needed
                    snapshot = self._parse_snapshot(frame_data)
                    
                    if snapshot:
                        with self.snapshot_lock:
                            self.latest_snapshot = snapshot
                        return snapshot
            
            return None
            
        except Exception as e:
            print(f"[ESP32] Snapshot receive failed: {e}")
            return None
    
    def _parse_snapshot(self, data: bytes) -> Optional[SystemSnapshot]:
        """Parse binary snapshot from C++ core"""
        # TODO: Implement binary protocol parsing
        # For now, return None - requires coordination with C++ snapshot format
        return None
    
    def get_latest_snapshot(self) -> Optional[SystemSnapshot]:
        """Get last received snapshot (thread-safe)"""
        with self.snapshot_lock:
            return self.latest_snapshot
    
    def monitor_loop(self):
        """Background thread to receive snapshots"""
        while self.running:
            self.receive_snapshot()
            time.sleep(0.1)


# ============ VISION EVIDENCE PROVIDER ============

class VisionEvidenceProvider:
    """
    Provides visual evidence to ESP32 core via EV_ACTIVITY_CLUE events.
    Does NOT make decisions - only provides observations.
    """
    
    def __init__(self, esp: ESP32Interface, camera_id: int = 0):
        self.esp = esp
        self.camera_id = camera_id
        self.cap: Optional[cv2.VideoCapture] = None
        self.face_cascade = None
        self.running = False
        
        # Load detector
        try:
            cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
            self.face_cascade = cv2.CascadeClassifier(cascade_path)
            print("[Vision] Face detector loaded")
        except Exception as e:
            print(f"[Vision] Detector load failed: {e}")
    
    def start(self) -> bool:
        """Initialize camera"""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            if self.cap.isOpened():
                self.running = True
                print("[Vision] Camera initialized")
                return True
        except Exception as e:
            print(f"[Vision] Camera init failed: {e}")
        return False
    
    def stop(self):
        """Release camera"""
        self.running = False
        if self.cap:
            self.cap.release()
    
    def evidence_loop(self):
        """
        Continuously analyze frames and send evidence to ESP32.
        Evidence = EV_ACTIVITY_CLUE events.
        """
        last_inference = 0.0
        inference_interval = 2.0  # seconds
        
        while self.running:
            now = time.time()
            
            if (now - last_inference) < inference_interval:
                time.sleep(0.1)
                continue
            
            last_inference = now
            
            # Capture frame
            ret, frame = self.cap.read()
            if not ret:
                continue
            
            # Detect faces
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 4) if self.face_cascade else []
            
            # Compute evidence
            face_present = len(faces) > 0
            
            if not face_present:
                # No face = potential distraction
                # Send as ADVISORY EVIDENCE to ESP32 with SOURCE_VISION_LAPTOP
                confidence = 70
                self.esp.send_event(
                    EventType.EV_ACTIVITY_CLUE, 
                    value=1, 
                    confidence=confidence,
                    source=EvidenceSource.SOURCE_VISION_LAPTOP
                )
                print(f"[Vision] Evidence: No face detected (confidence: {confidence})")
            else:
                # Face present = focused
                confidence = 80
                self.esp.send_event(
                    EventType.EV_ACTIVITY_CLUE, 
                    value=0, 
                    confidence=confidence,
                    source=EvidenceSource.SOURCE_VISION_LAPTOP
                )
                print(f"[Vision] Evidence: Face detected (confidence: {confidence})")


# ============ LLM NARRATOR (NOT DECISION MAKER) ============

class LLMNarrator:
    """
    Uses LLM to NARRATE decisions made by ESP32 C++ core.
    Does NOT make decisions.
    Receives snapshots and explains them in natural language.
    """
    
    def __init__(self):
        self.model = None
        self.tokenizer = None
        self.use_llm = False
        
        try:
            from transformers import AutoModelForCausalLM, AutoTokenizer
            import torch
            
            print("[LLM] Loading Phi-2 for narration...")
            self.tokenizer = AutoTokenizer.from_pretrained("microsoft/phi-2", trust_remote_code=True)
            self.model = AutoModelForCausalLM.from_pretrained(
                "microsoft/phi-2",
                torch_dtype=torch.bfloat16,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                device_map="cpu"
            )
            self.model.eval()
            
            # Intel optimization
            try:
                import intel_extension_for_pytorch as ipex
                self.model = ipex.optimize(self.model, dtype=torch.bfloat16)
                print("[LLM] Intel optimization enabled")
            except ImportError:
                pass
            
            self.use_llm = True
            print("[LLM] Phi-2 loaded successfully")
            
        except Exception as e:
            print(f"[LLM] Load failed: {e}")
            self.use_llm = False
    
    def narrate_snapshot(self, snapshot: SystemSnapshot) -> str:
        """
        Generate natural language narration of C++ core's state and decisions.
        This explains WHAT THE CORE DECIDED, not what should be decided.
        
        CRITICAL: Implements refusal logic - refuses to narrate when uncertainty is too high.
        """
        if not self.use_llm or not snapshot:
            return self._simple_narration(snapshot)
        
        # JARVIS-LEVEL IMPROVEMENT #5: Refusal logic
        # Refuse to narrate when belief/freshness are below critical thresholds
        REFUSAL_BELIEF_THRESHOLD = 40
        REFUSAL_FRESHNESS_THRESHOLD = 40
        
        if snapshot.belief < REFUSAL_BELIEF_THRESHOLD or snapshot.freshness < REFUSAL_FRESHNESS_THRESHOLD:
            return self._generate_refusal(snapshot)
        
        # Build context from authoritative snapshot
        context = f"""System State (from ESP32 core):
Activity Mode: {ActivityMode(snapshot.activity_mode).name}
Belief: {snapshot.belief}/100
Freshness: {snapshot.freshness}/100
Room Occupied: {snapshot.room_occupied}

Decision (from core):
Permitted: {snapshot.decision_permitted}
Reason: {snapshot.decision_reason}

Action Intent (from core):
Proposed: {snapshot.intent_proposed}
Action: {snapshot.intent_action_id}
Rationale: {snapshot.intent_rationale}

Provide a brief, natural language summary of this system state for the user."""
        
        try:
            import torch
            
            inputs = self.tokenizer(context, return_tensors="pt", return_attention_mask=False)
            
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=150,
                    temperature=0.6,
                    do_sample=True,
                    top_p=0.85,
                    num_beams=1,
                    pad_token_id=self.tokenizer.eos_token_id
                )
            
            response = self.tokenizer.batch_decode(outputs)[0]
            # Extract generated part
            if "summary" in response.lower():
                parts = response.lower().split("summary")
                if len(parts) > 1:
                    response = parts[1].strip()
            
            response = response.replace("<|endoftext|>", "").strip()
            return response if response else self._simple_narration(snapshot)
            
        except Exception as e:
            print(f"[LLM] Narration failed: {e}")
            return self._simple_narration(snapshot)
    
    def _generate_refusal(self, snapshot: SystemSnapshot) -> str:
        """
        JARVIS-LEVEL: Refuse to narrate when confidence is too low.
        Explains WHY we're uncertain instead of making something up.
        """
        # Parse uncertainty cause from snapshot decision reason
        reason = getattr(snapshot, 'decision_reason', '').lower()
        
        if 'stale data' in reason:
            return (f"I cannot provide reliable analysis right now. "
                   f"My sensor data is too old (belief: {snapshot.belief}%, freshness: {snapshot.freshness}%). "
                   f"Waiting for fresh inputs...")
        
        elif 'conflicting evidence' in reason:
            return (f"I'm receiving contradictory information from different sensors. "
                   f"I'd rather not guess. Confidence is only {snapshot.belief}%.")
        
        elif 'low signal' in reason:
            return (f"Sensor signal strength is too weak (belief: {snapshot.belief}%). "
                   f"I need stronger evidence before making conclusions.")
        
        elif 'unknown context' in reason:
            return (f"I don't have enough context to understand the current situation. "
                   f"Confidence is {snapshot.belief}%, which is below my threshold.")
        
        else:
            return (f"My confidence is too low to provide analysis (belief: {snapshot.belief}%, "
                   f"freshness: {snapshot.freshness}%). I'd rather say nothing than mislead you.")
    
    def _simple_narration(self, snapshot: SystemSnapshot) -> str:
        """Fallback narration without LLM"""
        if not snapshot:
            return "No system data available."
        
        mode = ActivityMode(snapshot.activity_mode).name
        belief = snapshot.belief
        
        # Check for refusal even in simple mode
        if belief < 40 or snapshot.freshness < 40:
            return f"Insufficient confidence ({belief}%) to provide status."
        
        if snapshot.intent_proposed:
            return f"System is in {mode} mode (confidence: {belief}%). {snapshot.intent_rationale}"
        else:
            return f"System is in {mode} mode (confidence: {belief}%). All systems normal."


# ============ MAIN INTEGRATION ============

class JARVISLaptopInterface:
    """
    Laptop-side interface to ESP32 C++ core.
    
    ROLE: Evidence provider & narrator ONLY.
    DOES NOT: Make decisions, maintain world state, or control actions.
    """
    
    def __init__(self, esp_port: str = "COM3", camera_id: int = 0, 
                 dht11_pin: int = 4, pir_pin: int = 17,
                 light_pin: int = None, fan_pin: int = None):
        # ESP32 interface
        self.esp = ESP32Interface(port=esp_port)
        
        # Evidence providers
        self.vision = VisionEvidenceProvider(self.esp, camera_id=camera_id)
        self.dht11 = DHT11Provider(self.esp, pin=dht11_pin)
        self.pir = PIRProvider(self.esp, pin=pir_pin)
        
        # Narrator
        self.narrator = LLMNarrator()
        
        # NEW: Automation executor
        self.automation = AutomationExecutor(light_pin=light_pin, fan_pin=fan_pin)
        
        # Control
        self.running = False
        self.threads = []
    
    def start(self):
        """Start all evidence providers and automation"""
        print("\n" + "="*70)
        print(" " * 20 + "JARVIS LAPTOP INTERFACE")
        print(" " * 10 + "Evidence Provider, Automation & Narrator")
        print("="*70)
        print("\nArchitecture:")
        print("  ESP32 C++ Core  ← Events (Evidence)")
        print("         ↓")
        print("  Snapshots (Authoritative State + Action Commands)")
        print("         ↓")
        print("  Laptop (This)   → Narration + Automation Execution")
        print("="*70 + "\n")
        
        # Connect to ESP32
        if not self.esp.connect():
            print("[ERROR] Cannot connect to ESP32. Exiting.")
            return False
        
        self.running = True
        
        # Start ESP32 monitor thread
        esp_thread = threading.Thread(target=self.esp.monitor_loop, daemon=True)
        esp_thread.start()
        self.threads.append(esp_thread)
        
        # Start DHT11 sensor
        self.dht11.running = True
        dht_thread = threading.Thread(target=self.dht11.evidence_loop, daemon=True)
        dht_thread.start()
        self.threads.append(dht_thread)
        
        # Start PIR sensor
        self.pir.running = True
        pir_thread = threading.Thread(target=self.pir.evidence_loop, daemon=True)
        pir_thread.start()
        self.threads.append(pir_thread)
        
        # Start vision evidence provider
        if self.vision.start():
            vision_thread = threading.Thread(target=self.vision.evidence_loop, daemon=True)
            vision_thread.start()
            self.threads.append(vision_thread)
        
        # NEW: Start automation snapshot monitor
        automation_thread = threading.Thread(target=self.monitor_snapshots_for_actions, daemon=True)
        automation_thread.start()
        self.threads.append(automation_thread)
        
        print("[System] All providers + automation started")
        print("[System] Listening for snapshots from ESP32 core...\n")
        
        return True
    
    def stop(self):
        """Stop all providers"""
        print("\n[System] Shutting down...")
        self.running = False
        self.vision.stop()
        self.esp.disconnect()
        
        for thread in self.threads:
            thread.join(timeout=2)
        
        print("[System] Terminated")
    
    def send_voice_evidence(self, text: str):
        """
        Send voice command as evidence to ESP32.
        The C++ core will decide what to do with it.
        """
        # Voice input is just evidence - let core interpret it
        # For now, treat as presence confirmation
        self.esp.send_event(EventType.EV_PRESENCE, value=1, confidence=90)
        print(f"[Voice] Evidence sent: '{text}'")
    
    def get_narration(self) -> str:
        """
        Get natural language narration of current system state.
        Based on latest snapshot from ESP32 core.
        """
        snapshot = self.esp.get_latest_snapshot()
        if not snapshot:
            self.esp.request_snapshot()
            time.sleep(0.5)
            snapshot = self.esp.get_latest_snapshot()
        
        if snapshot:
            return self.narrator.narrate_snapshot(snapshot)
        else:
            return "Waiting for system state from ESP32 core..."
    
    def handle_action_command(self, action_id: int, value: int, rationale: str):
        """
        Handle automation action command from ESP32 C++ core.
        Called when snapshot contains proposed action.
        """
        try:
            success = self.automation.execute_action(action_id, value, rationale)
            
            # Report status back to ESP32
            if success:
                self.esp.send_event(
                    EventType.EV_MODE_CONFIRM, 
                    value=action_id, 
                    confidence=100,
                    source=EvidenceSource.SOURCE_MANUAL_OVERRIDE
                )
                print(f"[System] ✓ Action confirmed to ESP32")
            else:
                self.esp.send_event(
                    EventType.EV_FAULT, 
                    value=action_id, 
                    confidence=0,
                    source=EvidenceSource.SOURCE_MANUAL_OVERRIDE
                )
                print(f"[System] ✗ Action failure reported to ESP32")
        except Exception as e:
            print(f"[System] Action handling error: {e}")
    
    def monitor_snapshots_for_actions(self):
        """
        Background thread monitoring snapshots for automation actions.
        Executes actions commanded by ESP32 C++ core.
        """
        print("[Automation] Snapshot monitor started")
        
        last_action_id = None
        last_action_time = 0
        
        while self.running:
            try:
                snapshot = self.esp.get_latest_snapshot()
                
                if snapshot and snapshot.intent_proposed:
                    action_id = snapshot.intent_action_id
                    
                    # Prevent duplicate execution (debounce 5 seconds)
                    current_time = time.time()
                    if action_id == last_action_id and (current_time - last_action_time) < 5:
                        time.sleep(1)
                        continue
                    
                    last_action_id = action_id
                    last_action_time = current_time
                    
                    # Extract value from snapshot or use defaults
                    value = 0
                    if action_id >= 10 and action_id <= 12:  # Light actions
                        value = 100 if action_id == 10 else 50 if action_id == 12 else 0
                    elif action_id >= 20 and action_id <= 22:  # AC actions
                        value = 24 if action_id in [20, 22] else 0
                    elif action_id >= 30 and action_id <= 32:  # Fan actions
                        value = 50 if action_id in [30, 32] else 0
                    
                    rationale = snapshot.intent_rationale
                    
                    print(f"\n[Automation] ╔═══════════════════════════════")
                    print(f"[Automation] ║ ESP32 Core Commanded Action")
                    print(f"[Automation] ╚═══════════════════════════════")
                    self.handle_action_command(action_id, value, rationale)
                
            except Exception as e:
                if self.running:
                    print(f"[Automation] Monitor error: {e}")
            
            time.sleep(1)  # Check every second
        
        print("[Automation] Snapshot monitor stopped")
    
    def get_device_status(self) -> Dict[str, Any]:
        """Get current status of all automation devices"""
        return self.automation.get_device_status()
    
    def print_device_status(self):
        """Print current device status"""
        self.automation.print_status()


# ============ EXAMPLE USAGE ============

if __name__ == "__main__":
    import signal
    import sys
    
    # Initialize with device pins (update these for your hardware)
    interface = JARVISLaptopInterface(
        esp_port="COM3", 
        camera_id=0,
        dht11_pin=4,      # DHT11 sensor GPIO pin
        pir_pin=17,       # PIR sensor GPIO pin
        light_pin=None,   # Light relay GPIO pin (None = simulation mode)
        fan_pin=None      # Fan control GPIO pin (None = simulation mode)
    )
    
    def signal_handler(sig, frame):
        print("\n[Main] Shutting down gracefully...")
        interface.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    if not interface.start():
        sys.exit(1)
    
    # Main monitoring loop
    try:
        print("\n[Main] System running. Press Ctrl+C to exit.")
        print("[Main] Monitoring ESP32 for automation commands...\n")
        
        while True:
            time.sleep(10)
            
            # Request snapshot
            interface.esp.request_snapshot()
            time.sleep(0.5)
            
            # Get and print narration
            narration = interface.get_narration()
            print(f"\n[Narration] {narration}")
            
            # Print device status
            interface.print_device_status()
            
    except KeyboardInterrupt:
        print("\n[Main] Keyboard interrupt detected")
        interface.stop()
        print(f"\n[Narration] {narration}\n")
            
    except KeyboardInterrupt:
        interface.stop()
