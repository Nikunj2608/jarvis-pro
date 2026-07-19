# JARVIS Unified System
## Real-Time AI Assistant with Multi-Modal Intelligence

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    JARVIS UNIFIED SYSTEM                     │
└─────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        │                     │                     │
   ┌────▼────┐          ┌────▼────┐          ┌────▼────┐
   │  Voice  │          │ Vision  │          │ Sensors │
   │Interface│          │ Monitor │          │ (ESP32) │
   └────┬────┘          └────┬────┘          └────┬────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              │
                        ┌────▼────┐
                        │  Event  │
                        │  Queue  │
                        └────┬────┘
                              │
                    ┌─────────▼─────────┐
                    │  Event Reducer    │
                    │ (State Updates)   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   World State     │
                    │  (Central State)  │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Decision Gate    │
                    │ (Policy Engine)   │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Action Intent    │
                    │ (Propose Actions) │
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   LLM Advisor     │
                    │   (Phi-2 LLM)     │
                    └─────────┬─────────┘
                              │
                        ┌─────▼─────┐
                        │  Execute  │
                        │  Actions  │
                        └───────────┘
```

---

## Core Components

### 1. **JARVIS Core** (`jarvis_core.py`)
Central orchestrator implementing the event-driven reasoning pipeline.

**Key Features:**
- Event-driven architecture
- Real-time state management
- Multi-threaded execution
- Policy-based decision making

**Main Classes:**
- `WorldState` - Central state representation
- `EventReducer` - Updates state from events
- `DecisionGate` - Evaluates action permissions
- `ActionIntentEngine` - Proposes actions
- `LLMAdvisor` - Generates natural language explanations

### 2. **Voice Interface** (`jarvis_unified.py`)
Speech recognition and TTS with noise reduction.

**Features:**
- RNNoise audio cleanup
- Google Speech Recognition
- SAPI5 text-to-speech
- Command routing

### 3. **Vision Monitor** (`jarvis_core.py`)
Real-time distraction detection using OpenCV.

**Features:**
- Face detection (Haar Cascades)
- Distraction inference
- Confidence scoring
- Low-latency processing (~5 FPS)

### 4. **Sensor Integration** (`serial_client.py`)
ESP32 environmental sensor interface with Phi-2 LLM.

**Features:**
- UART serial communication
- Temperature & humidity monitoring
- LLM-powered analysis
- Intel CPU optimization

---

## System Flow

### Event Processing Pipeline

1. **Input Sources** → Generate events
   - Voice commands
   - Vision analysis
   - Sensor readings
   - Time ticks

2. **Event Queue** → Central event buffer

3. **Event Reducer** → Updates world state
   - Processes events
   - Updates beliefs
   - Manages freshness decay

4. **Decision Gate** → Evaluates policy
   - Checks confidence thresholds
   - Applies behavioral rules
   - Determines action permission

5. **Action Intent** → Proposes actions
   - Analyzes world state
   - Prioritizes actions
   - Generates rationale

6. **LLM Advisor** → Natural language
   - Uses Phi-2 for reasoning
   - Generates explanations
   - Provides context-aware advice

7. **Action Execution** → Callbacks
   - Voice notifications
   - Silent logging
   - System interventions

---

## World State Model

```python
WorldState:
  ├─ Temporal
  │  ├─ day_segment (night/morning/afternoon/evening)
  │  └─ last_sync_ms
  │
  ├─ Physical
  │  ├─ room_occupied (bool)
  │  ├─ last_motion_ms
  │  ├─ temperature (°C)
  │  └─ humidity (%)
  │
  ├─ Activity
  │  ├─ activity_mode (idle/focus/distracted/override)
  │  ├─ mode_start_ms
  │  └─ distraction_confidence (0-100)
  │
  └─ Confidence
     ├─ belief (0-100)
     └─ freshness (0-100, decays over time)
```

---

## Event Types

| Event Type       | Source        | Purpose                          |
|------------------|---------------|----------------------------------|
| `TIME_TICK`      | System        | Periodic state updates           |
| `PRESENCE`       | Vision        | Room occupancy detection         |
| `ACTIVITY_CLUE`  | Vision        | Focus/distraction indicators     |
| `OVERRIDE`       | Voice         | User manual override             |
| `ENV_UPDATE`     | Sensors       | Temperature/humidity readings    |
| `MODE_CONFIRM`   | System        | State transition confirmation    |
| `FAULT`          | Any           | Error reporting                  |
| `VOICE_COMMAND`  | Voice         | User verbal input                |
| `VISION_UPDATE`  | Vision        | Video analysis results           |

---

## Decision Policies

### Intervention Rules

1. **High Confidence Required**
   - `belief >= 60` and `freshness >= 60`

2. **Respect Focus Mode**
   - Never interrupt when `activity_mode == FOCUS`

3. **Distraction Threshold**
   - Intervene if `distraction_confidence > 70`

4. **Action Cooldown**
   - Minimum 15 seconds between actions

5. **Environmental Alerts**
   - Temperature > 28°C triggers comfort alert
   - Humidity < 30% or > 70% triggers alert

---

## LLM Integration (Phi-2)

### System Prompt (JARVIS Identity)

```
You are JARVIS — a local-first, privacy-respecting, intelligent assistant.

CORE IDENTITY
- Calm, precise, and engineering-driven
- Think before speaking
- Prioritize correctness, safety, and efficiency

OPERATING PRINCIPLES
1. First Principles Thinking
2. Context Awareness
3. Execution-Oriented
4. Local & Privacy-First
5. Voice & Interaction Behavior

You are not an entertainer. You are a reliable system.
```

### Task Types

- **Sensor Analysis** - Engineering-focused environmental assessment
- **General Query** - Context-aware user assistance
- **Decision Explanation** - Rationale for system actions

---

## Installation & Setup

### Requirements

```bash
pip install transformers torch accelerate intel_extension_for_pytorch
pip install opencv-python pyserial SpeechRecognition pyttsx3 pyrnnoise
```

### Hardware Requirements

- **RAM**: 8GB minimum, 16GB+ recommended (Phi-2 needs ~5GB)
- **CPU**: Modern Intel/AMD (Intel Iris Xe GPU supported)
- **Camera**: USB webcam for vision monitoring
- **Serial**: ESP32 on COM port for sensors

### Configuration

Edit `jarvis_unified.py`:
```python
ESP_PORT = "COM3"     # Your ESP32 serial port
CAMERA_ID = 0         # Webcam device ID
```

---

## Usage

### Start Unified System

```bash
cd testing/laptop
python jarvis_unified.py
```

### Voice Commands

- **"What's the temperature?"** → Sensor + LLM analysis
- **"System status"** → Full state report
- **"How are you?"** → Health check
- **"Exit"** → Graceful shutdown

### Programmatic Interface

```python
from jarvis_unified import JARVISUnified

# Initialize
jarvis = JARVISUnified(esp_port="COM3", camera_id=0)

# Register custom actions
def my_action(intent, explanation):
    print(f"Action: {intent.action_id}")
    print(f"Why: {explanation}")

jarvis.core.register_action_callback("MY_ACTION", my_action)

# Start
jarvis.start()
```

---

## Performance Optimization

### Intel CPU Optimization

```python
import intel_extension_for_pytorch as ipex
model = ipex.optimize(model, dtype=torch.bfloat16)
```

### Vision Processing
- Runs at ~5 FPS (configurable)
- Face detection only (lightweight)
- Inference every 2 seconds

### LLM Inference
- First run: 10-20 seconds (model load)
- Subsequent: 5-10 seconds per query
- Uses `bfloat16` for CPU efficiency

---

## System Behavior

### Silent Observation Mode
When user is focused:
- Vision monitoring continues
- No voice interruptions
- Logs distraction events
- Maintains world state

### Active Intervention Mode
When thresholds exceeded:
- Voice notifications
- LLM-generated explanations
- Respects cooldown period
- Logs all actions

### Adaptive Behavior
- Belief increases with consistent events
- Freshness decays over time
- Mode transitions based on evidence
- Context-aware decision making

---

## Architecture Principles

### 1. **Event-Driven**
All state changes originate from events, ensuring deterministic behavior.

### 2. **Separation of Concerns**
- Perception (vision, sensors, voice)
- State management (world state)
- Reasoning (decision gate, action intent)
- Execution (callbacks, TTS)

### 3. **Privacy-First**
- All processing local (no cloud)
- Phi-2 runs on device
- No data transmission by default

### 4. **Fail-Safe Design**
- Graceful degradation
- Fallback mechanisms
- Error isolation

### 5. **Extensible**
- Plugin architecture for actions
- Event-based integration
- Modular components

---

## Troubleshooting

### Phi-2 Model Loading Issues
```bash
# Check PyTorch installation
python -c "import torch; print(torch.__version__)"

# Verify Intel extension
python -c "import intel_extension_for_pytorch as ipex; print('OK')"
```

### Camera Not Working
```python
# Test camera
import cv2
cap = cv2.VideoCapture(0)
print(cap.isOpened())
```

### Serial Port Issues
```python
# List available ports
from serial.tools import list_ports
print([p.device for p in list_ports.comports()])
```

---

## Future Enhancements

- [ ] Multi-user profile support
- [ ] Persistent memory (belief logging)
- [ ] Web dashboard for monitoring
- [ ] Mobile app integration
- [ ] Advanced ML models (gesture recognition)
- [ ] Calendar/schedule integration
- [ ] Habit tracking and analysis

---

## License

MIT License - Local-first AI for everyone.

---

## Credits

**JARVIS** - Just A Rather Very Intelligent System  
Built with: Phi-2, OpenCV, PyTorch, RNNoise, SpeechRecognition
