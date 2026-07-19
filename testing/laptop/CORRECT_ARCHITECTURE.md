# JARVIS Correct Architecture - C++ Core Authority

## 🏛️ Architectural Principles

### CRITICAL: Who Decides What

```
┌─────────────────────────────────────────────────────────┐
│           ESP32 C++ CORE (AUTHORITATIVE)                │
│                                                          │
│  Event Queue → Event Reducer → World State              │
│                                    ↓                     │
│                              Decision Gate               │
│                                    ↓                     │
│                              Action Intent               │
│                                    ↓                     │
│                            Snapshot Service              │
│                                    ↓                     │
│                                  UART                    │
└─────────────────────────────────────────────────────────┘
                                     ↕
                     ┌───────────────────────────┐
                     │  LAPTOP (ADVISORY ONLY)    │
                     │                            │
                     │  ↑ Events (Evidence)       │
                     │  ↓ Snapshots (State)       │
                     │                            │
                     │  - Vision → Evidence       │
                     │  - Voice → Evidence        │
                     │  - LLM → Narration         │
                     └────────────────────────────┘
```

---

## 📋 Component Responsibilities

### ESP32 C++ Core (AUTHORITATIVE)

**What it DOES:**
- ✅ Maintains WorldState (single source of truth)
- ✅ Processes all events through EventReducer
- ✅ Updates belief and freshness
- ✅ Makes ALL decisions via DecisionGate
- ✅ Proposes ALL actions via ActionIntent
- ✅ Logs belief evolution
- ✅ Provides snapshots of state

**What it NEVER does:**
- ❌ Accept commands from laptop
- ❌ Let laptop modify WorldState
- ❌ Delegate decision making
- ❌ Block on external I/O

**Files:**
- `src/core/world_state.c/h` - State management
- `src/core/events.c/h` - Event queue
- `src/core/event_reducer.c/h` - State updates
- `src/core/decision_gate.c/h` - Policy engine
- `src/core/action_intent.c/h` - Action proposals
- `src/core/snapshot_service.c/h` - State export
- `src/core/belief_logger.c/h` - Evolution tracking
- `src/main.cpp` - Task orchestration

### Laptop Python (ADVISORY ONLY)

**What it DOES:**
- ✅ Provides evidence via events
  - Vision → `EV_ACTIVITY_CLUE`
  - Voice → `EV_PRESENCE`
  - Sensors → `EV_ENV_UPDATE`
- ✅ Receives snapshots (read-only state)
- ✅ Narrates decisions (LLM explains state)
- ✅ Provides UI/voice output

**What it NEVER does:**
- ❌ Make decisions
- ❌ Maintain parallel world state
- ❌ Override ESP32 decisions
- ❌ Compute belief or freshness
- ❌ Implement decision gate logic

**Files:**
- `testing/laptop/jarvis_laptop_interface.py` - Main interface
- `testing/laptop/serial_client.py` - Serial + LLM (narration only)

---

## 🔄 Data Flow (Correct Architecture)

### 1. Evidence Flow (Laptop → ESP32)

```
Vision Analysis
    ↓
Compute: "No face detected"
    ↓
ESP32Interface.send_event(
    type=EV_ACTIVITY_CLUE,
    value=1,        # 1 = distracted
    confidence=70   # How sure are we
)
    ↓
[UART to ESP32]
    ↓
ESP32 receives: "EVENT 2 1 70\n"
    ↓
Parsed to Event struct
    ↓
event_queue_push(&event)
    ↓
[Event Reducer Task picks it up]
    ↓
world_handle_event(&event)
    ↓
WorldState updated:
  - activity.mode = ACTIVITY_MODE_DISTRACTED
  - confidence.belief += 5
    ↓
[Decision Gate Task evaluates]
    ↓
decision_gate_evaluate()
  → checks belief >= 60
  → checks freshness >= 60
  → applies policies
  → returns DecisionExplanation
    ↓
[Action Intent Task proposes]
    ↓
action_intent_evaluate()
  → sees DISTRACTED mode
  → proposes ACTION_SUGGEST_BREAK
  → returns ActionIntent
    ↓
[Snapshot Service captures state]
    ↓
SystemSnapshot built
```

### 2. State Flow (ESP32 → Laptop)

```
[Snapshot Service Task - periodic]
    ↓
build_snapshot(&snapshot)
  - Copies WorldState
  - Copies DecisionExplanation
  - Copies ActionIntent
    ↓
Serialize to binary frame
    ↓
[UART transmission]
    ↓
Laptop receives frame
    ↓
ESP32Interface.receive_snapshot()
    ↓
Parse SystemSnapshot
    ↓
LLMNarrator.narrate_snapshot(snapshot)
    ↓
LLM generates:
"System detects you're distracted (70% confidence).
 Core recommends taking a break."
    ↓
Text-to-speech output
```

---

## 📊 Event Types (Mirror C++ Definitions)

| Event Type | Source | Purpose | Value | Confidence |
|------------|--------|---------|-------|------------|
| `EV_TIME_TICK` | ESP32 timer | Freshness decay | 0 | 100 |
| `EV_PRESENCE` | Vision/PIR | Room occupancy | 0=absent, 1=present | 0-100 |
| `EV_ACTIVITY_CLUE` | Vision/ML | Focus state | 0=focused, 1=distracted | 0-100 |
| `EV_OVERRIDE` | Voice/button | Manual control | Mode ID | 100 |
| `EV_ENV_UPDATE` | Sensors | Environment | Sensor value | 0-100 |
| `EV_MODE_CONFIRM` | ESP32 | State lock | Mode ID | 100 |
| `EV_FAULT` | Any | Error report | Error code | 0 |

**CRITICAL:** Laptop can ONLY send events, NEVER modify state directly.

---

## 🔐 Decision Authority

### ESP32 C++ Core Decision Gate (`decision_gate.c`)

```c
bool decision_gate_evaluate(DecisionExplanation *explanation)
{
    // Get current world state
    extern WorldState world;
    
    // Policy 1: Require minimum confidence
    if (world.confidence.belief < DECISION_BELIEF_THRESHOLD) {
        explanation->permitted = false;
        explanation->reason = "Insufficient belief";
        return false;
    }
    
    // Policy 2: Require fresh data
    if (world.confidence.freshness < DECISION_FRESHNESS_THRESHOLD) {
        explanation->permitted = false;
        explanation->reason = "Stale data";
        return false;
    }
    
    // Policy 3: Don't interrupt focus
    if (world.activity.mode == ACTIVITY_MODE_FOCUS) {
        explanation->permitted = false;
        explanation->reason = "User focused - silent observation";
        return false;
    }
    
    // Policy 4: Intervene on high distraction
    if (world.activity.mode == ACTIVITY_MODE_DISTRACTED &&
        world.confidence.belief > 70) {
        explanation->permitted = true;
        explanation->reason = "High distraction detected";
        return true;
    }
    
    // Default: permit with caution
    explanation->permitted = true;
    explanation->reason = "Normal monitoring";
    return true;
}
```

**CRITICAL:** This code runs ONLY on ESP32. Laptop NEVER implements this logic.

---

## 🎯 Action Intent (`action_intent.c`)

```c
bool action_intent_evaluate(const DecisionExplanation *decision,
                            ActionIntent *intent)
{
    extern WorldState world;
    
    // No action if not permitted
    if (!decision->permitted) {
        intent->proposed = false;
        intent->action_id = ACTION_NONE;
        return false;
    }
    
    // Propose break if distracted
    if (world.activity.mode == ACTIVITY_MODE_DISTRACTED) {
        intent->proposed = true;
        intent->action_id = ACTION_SUGGEST_BREAK;
        strcpy(intent->rationale, "Distraction detected");
        return true;
    }
    
    // Observe silently
    intent->proposed = false;
    intent->action_id = ACTION_SILENT_OBSERVE;
    strcpy(intent->rationale, "Monitoring");
    return false;
}
```

**CRITICAL:** This runs on ESP32. Laptop only receives the ActionIntent in snapshots.

---

## 📡 Serial Protocol

### Laptop → ESP32 (Events)

```
Format: "EVENT <type> <value> <confidence>\n"

Examples:
  EVENT 2 1 70\n        # Activity clue: distracted (70% confidence)
  EVENT 1 1 90\n        # Presence: occupied (90% confidence)
  EVENT 4 25 100\n      # Environment: 25°C (100% confidence)
```

### ESP32 → Laptop (Snapshots)

```
Binary Protocol:
  [0xA5]              # Header marker
  [2 bytes]           # Length
  [WorldState]        # Binary state
  [Decision]          # Binary decision
  [ActionIntent]      # Binary intent
  [4 bytes]           # Timestamp
  [2 bytes]           # CRC16
```

---

## 🧪 Testing the Correct Architecture

### Test 1: Evidence Injection

```python
from jarvis_laptop_interface import JARVISLaptopInterface, EventType

interface = JARVISLaptopInterface()
interface.start()

# Send evidence (NOT a command)
interface.esp.send_event(
    EventType.EV_ACTIVITY_CLUE,
    value=1,        # Distracted
    confidence=75
)

# Wait for ESP32 to process
time.sleep(1)

# Request snapshot (read state)
interface.esp.request_snapshot()
time.sleep(0.5)

# Narrate what ESP32 decided
narration = interface.get_narration()
print(narration)
```

### Test 2: Vision Evidence Pipeline

```python
# Vision detects no face
# ↓
# VisionEvidenceProvider automatically sends:
esp.send_event(EventType.EV_ACTIVITY_CLUE, value=1, confidence=70)
# ↓
# ESP32 EventReducer updates WorldState
# ↓
# ESP32 DecisionGate evaluates policies
# ↓
# ESP32 ActionIntent proposes action
# ↓
# Snapshot sent back to laptop
# ↓
# LLM narrates: "System detects distraction..."
```

---

## ⚠️ Common Mistakes (DO NOT DO)

### ❌ WRONG: Laptop Makes Decisions

```python
# WRONG - Don't do this!
class LaptopDecisionGate:
    def evaluate(self, world_state):
        if world_state.distraction > 70:
            return "suggest_break"  # ← WRONG! ESP32 decides!
```

### ✅ RIGHT: Laptop Provides Evidence

```python
# RIGHT - Only provide evidence
esp.send_event(EventType.EV_ACTIVITY_CLUE, value=1, confidence=70)
```

### ❌ WRONG: Laptop Maintains State

```python
# WRONG - Don't duplicate state!
class WorldState:
    def __init__(self):
        self.belief = 50  # ← WRONG! ESP32 maintains state!
```

### ✅ RIGHT: Laptop Receives State

```python
# RIGHT - Receive authoritative state
snapshot = esp.get_latest_snapshot()
print(f"Belief (from ESP32): {snapshot.belief}")
```

### ❌ WRONG: LLM Controls System

```python
# WRONG - Don't let LLM decide!
llm_decision = llm.query("Should I intervene?")
if llm_decision == "yes":
    take_action()  # ← WRONG! ESP32 decides!
```

### ✅ RIGHT: LLM Narrates State

```python
# RIGHT - LLM explains what ESP32 decided
snapshot = esp.get_latest_snapshot()
narration = llm.narrate_snapshot(snapshot)
speak(narration)
```

---

## 🔧 Implementation Checklist

### ESP32 C++ Core

- [x] Event queue (`events.c`)
- [x] Event reducer task (`event_reducer.c`)
- [x] World state (`world_state.c`)
- [x] Decision gate task (`decision_gate.c`)
- [x] Action intent task (`action_intent.c`)
- [x] Snapshot service task (`snapshot_service.c`)
- [x] Main task orchestration (`main.cpp`)
- [x] Serial event injection (ASCII protocol)
- [x] Serial snapshot transmission (binary protocol)

### Laptop Python

- [x] ESP32 interface (`jarvis_laptop_interface.py`)
- [x] Vision evidence provider (sends `EV_ACTIVITY_CLUE`)
- [x] LLM narrator (narrates snapshots, not decisions)
- [x] Snapshot receiver (parses binary protocol)
- [x] Event sender (ASCII protocol)
- [ ] Voice interface (sends `EV_PRESENCE` events)
- [ ] Sensor interface (sends `EV_ENV_UPDATE` events)

---

## 🎯 Deployment

### 1. Flash ESP32

```bash
cd src
pio run --target upload
pio device monitor
```

### 2. Run Laptop Interface

```bash
cd testing/laptop
python jarvis_laptop_interface.py
```

### 3. Verify Communication

```
ESP32 Output:
  [Init] Event queue...
  [Init] Starting tasks...
  [System] Intelligence core active
  [Event] Received: type=2 value=1 confidence=70
  [Decision] Evaluating...
  [Action] Proposing: SUGGEST_BREAK

Laptop Output:
  [ESP32] Connected to COM3
  [Vision] Evidence: No face detected (confidence: 70)
  [Narration] System detects distraction. Recommending break.
```

---

## 🏆 Success Criteria

✅ **ESP32 is authoritative** - All decisions made in C++ core  
✅ **Laptop is advisory** - Only sends events, receives snapshots  
✅ **No duplicate logic** - World state exists only on ESP32  
✅ **Real-time safe** - All C++ tasks bounded and deterministic  
✅ **Event-driven** - All state changes via events  
✅ **Explainable** - Snapshots show complete decision chain  
✅ **LLM is narrator** - Explains decisions, doesn't make them  

---

**This is the correct architecture. Intelligence lives in C++.**
