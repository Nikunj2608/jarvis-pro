# Migration Guide: From Incorrect to Correct Architecture

## 🚨 Problem: Architecture Violation

The previously created files (`jarvis_core.py`, `jarvis_unified.py`) **violate** the system architecture by:

1. ❌ Duplicating intelligence logic in Python
2. ❌ Making decisions on laptop instead of ESP32
3. ❌ Maintaining parallel world state
4. ❌ Bypassing the C++ core

## ✅ Solution: Respect C++ Core Authority

Use the new **correct** architecture:
- ESP32 C++ core makes ALL decisions
- Laptop provides evidence ONLY
- LLM narrates, doesn't decide

---

## 📁 File Status

### ❌ DEPRECATED (Do Not Use)

These files implement intelligence on the laptop (WRONG):

- `jarvis_core.py` - Duplicates C++ event_reducer, decision_gate, action_intent
- `jarvis_unified.py` - Makes decisions independently
- Old `test_jarvis.py` - Tests wrong architecture

**Action:** Do not use these files. They violate the architecture.

### ✅ CORRECT (Use These)

New files that respect C++ core authority:

- `jarvis_laptop_interface.py` - Evidence provider + narrator ONLY
- `src/main.cpp` - ESP32 C++ core (authoritative)
- `CORRECT_ARCHITECTURE.md` - Architecture documentation

---

## 🔄 Migration Steps

### Step 1: Stop Using Old Files

```bash
# Rename to indicate they're deprecated
mv jarvis_core.py jarvis_core_DEPRECATED.py
mv jarvis_unified.py jarvis_unified_DEPRECATED.py
```

### Step 2: Use New Laptop Interface

```python
# OLD (WRONG):
from jarvis_unified import JARVISUnified
jarvis = JARVISUnified()
jarvis.start()  # ← Makes decisions on laptop!

# NEW (CORRECT):
from jarvis_laptop_interface import JARVISLaptopInterface
interface = JARVISLaptopInterface()
interface.start()  # ← Only provides evidence
```

### Step 3: Flash ESP32 Core

```bash
cd src
# Build and upload C++ core
pio run --target upload

# Monitor serial output
pio device monitor
```

### Step 4: Test Communication

```python
from jarvis_laptop_interface import JARVISLaptopInterface, EventType
import time

interface = JARVISLaptopInterface(esp_port="COM3")
if interface.start():
    # Send evidence
    interface.esp.send_event(EventType.EV_ACTIVITY_CLUE, value=1, confidence=70)
    
    # Wait for processing
    time.sleep(1)
    
    # Get narration
    narration = interface.get_narration()
    print(narration)
```

---

## 🔍 Code Comparison

### Decision Making

**❌ WRONG (jarvis_core.py):**
```python
class DecisionGate:
    def evaluate(self, world: WorldState) -> DecisionExplanation:
        # Laptop makes decision - WRONG!
        if world.belief >= 60 and world.freshness >= 60:
            return DecisionExplanation(permitted=True, ...)
```

**✅ CORRECT (ESP32 C++ core):**
```cpp
// decision_gate.c - runs on ESP32
bool decision_gate_evaluate(DecisionExplanation *explanation) {
    // ESP32 makes decision - CORRECT!
    if (world.confidence.belief >= 60 && world.confidence.freshness >= 60) {
        explanation->permitted = true;
    }
}
```

**✅ CORRECT (Laptop):**
```python
# Laptop receives decision, doesn't make it
snapshot = esp.get_latest_snapshot()
print(f"Decision (from ESP32): {snapshot.decision_permitted}")
```

### State Management

**❌ WRONG (jarvis_core.py):**
```python
class WorldState:
    def __init__(self):
        self.belief = 50  # Laptop maintains state - WRONG!
        self.activity_mode = ActivityMode.IDLE
```

**✅ CORRECT (ESP32 C++ core):**
```cpp
// world_state.c - runs on ESP32
WorldState world = {
    .confidence = { .belief = 0 },  // ESP32 maintains state - CORRECT!
    .activity = { .mode = ACTIVITY_MODE_IDLE }
};
```

**✅ CORRECT (Laptop):**
```python
# Laptop receives state, doesn't maintain it
snapshot = esp.get_latest_snapshot()
print(f"Activity mode (from ESP32): {snapshot.activity_mode}")
```

### Event Processing

**❌ WRONG (jarvis_core.py):**
```python
class EventReducer:
    def process_event(self, event: Event) -> WorldState:
        # Laptop processes events - WRONG!
        if event.type == EventType.ACTIVITY_CLUE:
            self.world.activity_mode = ActivityMode.DISTRACTED
```

**✅ CORRECT (ESP32 C++ core):**
```cpp
// event_reducer.c - runs on ESP32
static void event_reducer_task(void *params) {
    Event event;
    for (;;) {
        if (event_queue_pop(&event, portMAX_DELAY)) {
            world_handle_event(&event);  // ESP32 processes - CORRECT!
        }
    }
}
```

**✅ CORRECT (Laptop):**
```python
# Laptop sends events, doesn't process them
interface.esp.send_event(EventType.EV_ACTIVITY_CLUE, value=1, confidence=70)
```

---

## 🎯 LLM Role Change

### ❌ WRONG: LLM Makes Decisions

```python
# OLD jarvis_core.py
class LLMAdvisor:
    def generate_explanation(self, world, decision, intent):
        # LLM involved in decision making - WRONG!
        response = llm.query("Should we intervene?")
        return response
```

### ✅ CORRECT: LLM Narrates Decisions

```python
# NEW jarvis_laptop_interface.py
class LLMNarrator:
    def narrate_snapshot(self, snapshot: SystemSnapshot) -> str:
        # LLM explains what ESP32 decided - CORRECT!
        context = f"""
        The ESP32 core has decided:
        - Activity: {snapshot.activity_mode}
        - Decision: {snapshot.decision_reason}
        - Action: {snapshot.intent_rationale}
        
        Explain this to the user naturally.
        """
        return llm.query(context)
```

---

## 📊 Architecture Comparison

### OLD (WRONG)

```
┌─────────────────────────────────┐
│   Laptop (jarvis_core.py)       │
│                                  │
│   ┌──────────────────────────┐  │
│   │ WorldState               │  │  ← WRONG!
│   │ EventReducer             │  │
│   │ DecisionGate             │  │
│   │ ActionIntentEngine       │  │
│   │ LLMAdvisor               │  │
│   └──────────────────────────┘  │
│                                  │
│   Vision → Decision → Action     │  ← WRONG!
└─────────────────────────────────┘
         ↓
    ESP32 (ignored)
```

### NEW (CORRECT)

```
┌─────────────────────────────────────┐
│   ESP32 C++ Core (AUTHORITATIVE)    │
│                                      │
│   Event Queue → Event Reducer        │
│                      ↓               │
│                 WorldState           │
│                      ↓               │
│               Decision Gate          │
│                      ↓               │
│               Action Intent          │
│                      ↓               │
│             Snapshot Service         │
└───────────────────┬──────────────────┘
                    ↕
┌───────────────────────────────────────┐
│   Laptop (jarvis_laptop_interface.py) │
│                                        │
│   Vision → Evidence → [ESP32]          │
│   [ESP32] → Snapshot → LLM Narration   │
└────────────────────────────────────────┘
```

---

## 🧪 Testing

### Test 1: Verify ESP32 Authority

```python
from jarvis_laptop_interface import JARVISLaptopInterface, EventType
import time

interface = JARVISLaptopInterface(esp_port="COM3")
interface.start()

# Send contradictory evidence
interface.esp.send_event(EventType.EV_ACTIVITY_CLUE, value=0, confidence=50)  # Focused
time.sleep(0.5)
interface.esp.send_event(EventType.EV_ACTIVITY_CLUE, value=1, confidence=90)  # Distracted

# ESP32 core resolves this based on its policies
time.sleep(1)
snapshot = interface.esp.get_latest_snapshot()

# ESP32 decision is authoritative
print(f"ESP32 decided: {snapshot.activity_mode}")
print(f"Belief: {snapshot.belief}")
```

### Test 2: Verify LLM is Narrator Only

```python
# Send evidence
interface.esp.send_event(EventType.EV_ACTIVITY_CLUE, value=1, confidence=75)
time.sleep(1)

# Get narration (not decision)
narration = interface.get_narration()

# Verify narration reflects ESP32 decision, not LLM decision
print(narration)
# Should say something like: "The system has detected..."
# NOT: "I think you should..."
```

---

## 📋 Checklist

Before using the system, verify:

### ESP32 Side
- [ ] `src/main.cpp` compiled and uploaded
- [ ] Serial monitor shows: "Intelligence core active"
- [ ] Event queue initialized
- [ ] All tasks started
- [ ] Can receive "EVENT" commands
- [ ] Can send snapshots

### Laptop Side
- [ ] NOT using `jarvis_core.py` or `jarvis_unified.py`
- [ ] Using `jarvis_laptop_interface.py`
- [ ] Serial connection established
- [ ] Can send events to ESP32
- [ ] Can receive snapshots from ESP32
- [ ] LLM loaded (for narration only)

### Integration
- [ ] Laptop sends `EV_ACTIVITY_CLUE` events
- [ ] ESP32 processes events → updates state
- [ ] ESP32 evaluates decision gate
- [ ] ESP32 proposes action intent
- [ ] Snapshot transmitted to laptop
- [ ] Laptop narrates ESP32's decisions
- [ ] NO decision logic on laptop

---

## 🎓 Key Principles (Remember These)

1. **ESP32 is authoritative** - It makes ALL decisions
2. **Laptop is advisory** - It provides evidence only
3. **Events flow up** - Laptop → ESP32
4. **Snapshots flow down** - ESP32 → Laptop
5. **LLM narrates** - It explains, doesn't decide
6. **WorldState is singular** - Lives only on ESP32
7. **No duplicate logic** - Intelligence in C++ only

---

## 📚 Documentation

Read these in order:
1. `CORRECT_ARCHITECTURE.md` - Architectural principles
2. `src/main.cpp` - ESP32 implementation
3. `jarvis_laptop_interface.py` - Laptop implementation
4. This migration guide

---

## 🚀 Quick Start (Correct Way)

```bash
# Terminal 1: ESP32
cd src
pio run --target upload
pio device monitor

# Terminal 2: Laptop
cd testing/laptop
python jarvis_laptop_interface.py
```

**You should see:**
- ESP32: Event processing, state updates, decisions
- Laptop: Evidence sending, snapshot receiving, narration

**Intelligence flows from ESP32. Laptop explains it.**

---

**Remember: The system is intelligent because beliefs evolve in C++ — not because an LLM speaks.**
