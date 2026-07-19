# JARVIS Quick Start Guide

## 🚀 Getting Started in 5 Minutes

### Step 1: Install Dependencies

```bash
# Core dependencies
pip install transformers torch accelerate
pip install opencv-python pyserial
pip install SpeechRecognition pyttsx3 pyrnnoise

# Intel CPU optimization (recommended for better performance)
pip install intel_extension_for_pytorch
```

### Step 2: Verify Installation

```bash
cd testing/laptop
python test_jarvis.py
```

This will test all components individually.

### Step 3: Configure Hardware

Edit `jarvis_unified.py`:
```python
ESP_PORT = "COM3"     # Change to your ESP32 port
CAMERA_ID = 0         # Change if using external webcam
```

Find your ESP32 port:
```python
from serial.tools import list_ports
print([p.device for p in list_ports.comports()])
```

### Step 4: Run JARVIS

```bash
python jarvis_unified.py
```

---

## 🎤 Voice Commands

Once running, try these commands:

| Command | Response |
|---------|----------|
| "What's the temperature?" | Gets sensor data + AI analysis |
| "System status" | Full state report |
| "How are you?" | Health check |
| "Exit" | Graceful shutdown |

---

## 🔧 Component Testing

### Test Individual Components

```bash
# Test serial client + LLM only
python serial_client.py

# Test core system without voice
python jarvis_core.py

# Test full integration
python jarvis_unified.py
```

### Quick LLM Test

```python
from serial_client import ESP32Client

client = ESP32Client(port="COM3", use_llm=True)
response = client.query_jarvis("What should I do if I'm feeling distracted?")
print(response)
```

---

## 📊 System Monitoring

### Watch Real-Time State

Add this to `jarvis_unified.py` main loop:

```python
while True:
    state = jarvis.core.get_world_state()
    print(f"Mode: {state.activity_mode.name} | "
          f"Belief: {state.belief} | "
          f"Temp: {state.temperature}°C")
    time.sleep(5)
```

### Enable Debug Logging

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

---

## 🐛 Common Issues

### Issue 1: Model Download Slow
**Solution:** First run downloads ~5GB. Be patient. Uses HuggingFace cache.

### Issue 2: Out of Memory
**Solution:** Close other apps. Phi-2 needs ~5GB RAM.

```python
# Use smaller model if needed
self.tokenizer = AutoTokenizer.from_pretrained("microsoft/phi-1_5")
```

### Issue 3: Camera Not Working
**Solution:** Check camera permissions and device ID.

```python
import cv2
cap = cv2.VideoCapture(0)  # Try 0, 1, 2...
print(cap.isOpened())
```

### Issue 4: Serial Port Busy
**Solution:** Close Arduino IDE, PuTTY, or other serial monitors.

```bash
# Windows: Check with Device Manager
# Find "Ports (COM & LPT)" section
```

### Issue 5: Slow LLM Inference
**Solution:** Install Intel Extension for PyTorch

```bash
pip install intel_extension_for_pytorch
```

Expected speeds:
- First inference: 10-20 seconds
- Subsequent: 5-10 seconds

---

## ⚙️ Configuration Options

### Adjust Vision Inference Rate

In `jarvis_core.py`:
```python
class VisionMonitor:
    def __init__(self, camera_id: int = 0):
        self.inference_interval = 2.0  # Change to 5.0 for less frequent
```

### Adjust Action Cooldown

In `jarvis_core.py`:
```python
class JARVISCore:
    def _reasoning_loop(self):
        action_cooldown = 15.0  # Change to 30.0 for less frequent
```

### Adjust Decision Thresholds

In `jarvis_core.py`:
```python
class EventReducer:
    BELIEF_THRESHOLD = 60      # Lower = more sensitive
    FRESHNESS_THRESHOLD = 60   # Lower = accepts older data
```

### Adjust Distraction Detection

In `jarvis_core.py`:
```python
class VisionMonitor:
    def analyze_frame(self):
        if not face_present:
            confidence = 70  # Lower = less aggressive
```

---

## 🎯 Usage Examples

### Example 1: Morning Routine

```python
from jarvis_unified import JARVISUnified

jarvis = JARVISUnified(esp_port="COM3")

# Custom morning greeting
def morning_greeting(intent, explanation):
    jarvis.voice.speak("Good morning! Ready to start the day?")

jarvis.core.register_action_callback("MORNING", morning_greeting)
jarvis.start()
```

### Example 2: Focus Timer

```python
import time
from jarvis_core import Event, EventType

jarvis = JARVISCore()
jarvis.start()

# Start focus session
jarvis.emit_event(Event(
    type=EventType.OVERRIDE,
    timestamp=time.time(),
    value=1,  # Focus mode
    data={"duration": 1500}  # 25 minutes
))

# JARVIS will monitor and alert if distracted
```

### Example 3: Custom Sensor Analysis

```python
from serial_client import ESP32Client

client = ESP32Client(port="COM3", use_llm=True)

# Get sensor data with custom prompt
custom_prompt = """
Analyze this sensor data from a home office.
Suggest optimal settings for productivity.

Data: {sensor_data}

Response:"""

data = client.get_env(analyze=False)
analysis = client.analyze_with_llm(data, prompt=custom_prompt)
print(analysis)
```

---

## 📈 Performance Optimization

### For Intel CPUs (11th gen+)

```python
# Already implemented in serial_client.py
import intel_extension_for_pytorch as ipex
model = ipex.optimize(model, dtype=torch.bfloat16)
```

### For AMD CPUs

```python
# Use float16 instead of bfloat16
self.model = AutoModelForCausalLM.from_pretrained(
    "microsoft/phi-2",
    torch_dtype=torch.float16,
    trust_remote_code=True
)
```

### For Low-End Systems

```python
# Reduce max_length for faster generation
outputs = self.model.generate(
    **inputs,
    max_length=100,  # Was 200
    num_beams=1
)
```

---

## 🔐 Privacy & Security

### All Data Stays Local
- No cloud services
- No telemetry
- No data transmission
- Phi-2 runs on your device

### Disable Components

```python
# Disable vision monitoring
jarvis = JARVISCore(camera_id=-1)  # No camera

# Disable LLM
client = ESP32Client(use_llm=False)

# Disable voice
# Just use jarvis_core.py without jarvis_unified.py
```

---

## 📚 Next Steps

1. **Read** [README_UNIFIED.md](README_UNIFIED.md) for full architecture
2. **Explore** `jarvis_core.py` to understand reasoning pipeline
3. **Customize** action callbacks for your workflow
4. **Integrate** with calendar, task manager, or smart home
5. **Contribute** improvements and share your setup!

---

## 💡 Pro Tips

1. **First run is slow** - Model downloads and loads. Be patient!
2. **Test components separately** - Use `test_jarvis.py` first
3. **Adjust thresholds** - Fine-tune for your environment
4. **Use Intel optimizations** - 2-3x faster inference
5. **Monitor system resources** - Keep Task Manager open initially
6. **Start simple** - Disable vision first, add it later
7. **Check serial port** - Most common issue
8. **Calibrate voice** - Let it adjust for ambient noise

---

## 🆘 Need Help?

1. Run diagnostics: `python test_jarvis.py`
2. Check logs for error messages
3. Verify hardware connections
4. Review [README_UNIFIED.md](README_UNIFIED.md)
5. Test individual components first

---

**Happy JARVIS-ing! 🤖**
