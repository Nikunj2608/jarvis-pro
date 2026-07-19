# JARVIS Deployment Checklist

## 📋 Pre-Deployment Verification

### ✅ Environment Setup

- [ ] Python 3.8+ installed
- [ ] All dependencies installed:
  ```bash
  pip install transformers torch accelerate
  pip install opencv-python pyserial
  pip install SpeechRecognition pyttsx3 pyrnnoise
  pip install intel_extension_for_pytorch  # Optional but recommended
  ```

### ✅ Hardware Verification

- [ ] **ESP32 Connected**
  - [ ] Port identified (COM3, COM4, etc.)
  - [ ] Drivers installed
  - [ ] No other programs using the port
  - [ ] Test command: 
    ```python
    from serial.tools import list_ports
    print([p.device for p in list_ports.comports()])
    ```

- [ ] **Webcam Available**
  - [ ] Camera connected
  - [ ] Permissions granted
  - [ ] Test command:
    ```python
    import cv2
    cap = cv2.VideoCapture(0)
    print(f"Camera working: {cap.isOpened()}")
    ```

- [ ] **Microphone Working**
  - [ ] Default input device set
  - [ ] Permissions granted
  - [ ] Test with Windows Sound settings

### ✅ Model Download (First Time Only)

- [ ] Phi-2 model downloads on first run (~5GB)
- [ ] Sufficient disk space (10GB recommended)
- [ ] Stable internet connection
- [ ] Model cache location: `~/.cache/huggingface/`

### ✅ Configuration

- [ ] Edit `jarvis_unified.py`:
  ```python
  ESP_PORT = "COM3"      # ← Your ESP32 port
  CAMERA_ID = 0          # ← Your camera ID
  ```

- [ ] Test individual components first:
  ```bash
  python test_jarvis.py
  ```

---

## 🚀 Deployment Steps

### Step 1: Component Testing (15 minutes)

```bash
cd testing/laptop

# Test 1: Serial Client + LLM
python serial_client.py
# Expected: Model loads, connects to ESP32, gets sensor data

# Test 2: Core System
python jarvis_core.py
# Expected: All threads start, vision/sensors active

# Test 3: Full Test Suite
python test_jarvis.py
# Expected: All tests pass (or skip camera if unavailable)
```

**Success Criteria:**
- ✅ Phi-2 loads without errors
- ✅ Serial connection established
- ✅ Camera initializes (or gracefully skips)
- ✅ No import errors

### Step 2: Configuration Tuning (10 minutes)

Edit `jarvis_core.py` thresholds:

```python
# Vision sensitivity
class VisionMonitor:
    inference_interval = 2.0  # ← Adjust FPS (lower = faster)

# Action frequency
class JARVISCore:
    action_cooldown = 15.0    # ← Seconds between actions

# Decision sensitivity
class EventReducer:
    BELIEF_THRESHOLD = 60     # ← Lower = more sensitive
    FRESHNESS_THRESHOLD = 60  # ← Lower = accepts older data
```

### Step 3: Dry Run (10 minutes)

```bash
python jarvis_unified.py
```

**What to Watch:**
1. **Startup** (10-20s)
   - All threads should start
   - Model loads successfully
   - Camera/serial connects

2. **Voice Commands** (try these)
   - "System status"
   - "What's the temperature?"
   - "How are you?"

3. **Monitoring**
   - Check console output
   - Verify events are flowing
   - Watch for errors

**If Issues:**
- Check terminal output for errors
- Verify hardware connections
- Review configuration
- Run test_jarvis.py again

### Step 4: Production Run

Once dry run successful:

```bash
# Start JARVIS
python jarvis_unified.py

# Let it run for 30 minutes
# Test various scenarios:
# - Voice commands
# - Looking away from screen
# - Environmental changes
# - Exit command
```

---

## ⚙️ Performance Optimization

### For Intel CPUs

```bash
# Install Intel optimizations
pip install intel_extension_for_pytorch

# Verify in code (already implemented)
import intel_extension_for_pytorch as ipex
```

**Expected Speed Improvements:**
- Inference: 2-3x faster
- CPU usage: More efficient

### For Limited RAM (<16GB)

Edit `serial_client.py`:
```python
# Use smaller model
model = AutoModelForCausalLM.from_pretrained(
    "microsoft/phi-1_5",  # ← Smaller version
    torch_dtype=torch.float16
)
```

### For Low-End Systems

Edit `jarvis_core.py`:
```python
# Disable vision
jarvis = JARVISCore(camera_id=-1)

# Reduce sensor polling
time.sleep(10)  # ← In _sensor_loop

# Disable LLM
esp = ESP32Client(use_llm=False)
```

---

## 🐛 Troubleshooting Guide

### Issue 1: "Model not found" or download fails

**Solution:**
```bash
# Manually download model
python -c "from transformers import AutoModelForCausalLM; AutoModelForCausalLM.from_pretrained('microsoft/phi-2', trust_remote_code=True)"
```

### Issue 2: "Out of memory"

**Solutions:**
1. Close other applications
2. Use smaller model (phi-1_5)
3. Add swap space (Windows: Virtual Memory)
4. Reduce max_length in generation

### Issue 3: "Camera not working"

**Solutions:**
1. Try different camera_id: 0, 1, 2...
2. Check Windows Camera permissions
3. Close other camera apps (Zoom, Teams, etc.)
4. Disable camera if not needed:
   ```python
   jarvis = JARVISCore(camera_id=-1)
   ```

### Issue 4: "Serial port busy"

**Solutions:**
1. Close Arduino IDE
2. Close PuTTY, Tera Term, etc.
3. Unplug/replug ESP32
4. Check Device Manager for port conflicts

### Issue 5: "Slow LLM inference"

**Expected times:**
- First run: 10-20s (normal)
- Subsequent: 5-10s (normal)

**If slower:**
1. Install Intel extension
2. Check CPU usage (should be 30-40%)
3. Verify no other heavy processes
4. Try bfloat16 if not already using

### Issue 6: "Voice recognition fails"

**Solutions:**
1. Speak clearly and directly
2. Reduce background noise
3. Check microphone levels
4. Adjust ambient noise calibration
5. Test with Google Assistant first

---

## 📊 System Health Monitoring

### Metrics to Watch

```python
# Add to jarvis_unified.py main loop
while True:
    state = jarvis.core.get_world_state()
    print(f"""
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    Activity: {state.activity_mode.name}
    Belief: {state.belief}/100
    Freshness: {state.freshness}/100
    Temperature: {state.temperature}°C
    Humidity: {state.humidity}%
    ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    """)
    time.sleep(10)
```

### Performance Benchmarks

| Metric | Expected | Action if Outside Range |
|--------|----------|-------------------------|
| LLM inference | 5-10s | Install Intel extension |
| Vision FPS | 4-6 FPS | Reduce inference_interval |
| Memory usage | 6-8GB | Close apps or use smaller model |
| CPU usage | 40-60% | Check for other processes |
| Event queue size | <10 | Check for bottlenecks |

---

## 🔐 Security & Privacy

### ✅ Privacy Checklist

- [x] All processing local (no cloud)
- [x] No data transmission by default
- [x] Phi-2 runs on device
- [x] Camera/audio stays local
- [x] No telemetry

### Optional: Disable Components

```python
# Disable specific inputs
jarvis = JARVISCore(
    esp_port="COM3",
    camera_id=-1  # ← No camera
)

# Or disable LLM
esp = ESP32Client(use_llm=False)
```

---

## 📝 Production Checklist

### Before Deployment

- [ ] All tests pass
- [ ] Hardware verified
- [ ] Configuration tuned
- [ ] Dry run successful
- [ ] Performance acceptable
- [ ] Error handling tested

### First 24 Hours

- [ ] Monitor console output
- [ ] Check for memory leaks
- [ ] Verify action cooldowns work
- [ ] Test all voice commands
- [ ] Verify graceful shutdown

### First Week

- [ ] Tune thresholds based on usage
- [ ] Adjust action cooldowns
- [ ] Optimize LLM prompts
- [ ] Add custom actions
- [ ] Review logs for patterns

---

## 🎯 Success Criteria

✅ **System runs continuously for 1+ hours**  
✅ **Voice commands respond within 10 seconds**  
✅ **Vision monitoring active @ 4-6 FPS**  
✅ **Sensors update every 5 seconds**  
✅ **No crashes or exceptions**  
✅ **Actions execute appropriately**  
✅ **LLM responses are coherent**  
✅ **Resource usage within limits**

---

## 📞 Support Resources

1. **Documentation**
   - QUICKSTART.md - Quick setup guide
   - README_UNIFIED.md - Full architecture
   - SYSTEM_SUMMARY.md - Implementation details
   - ARCHITECTURE_DIAGRAM.txt - Visual reference

2. **Test Suite**
   ```bash
   python test_jarvis.py
   ```

3. **Component Testing**
   - `python serial_client.py` - Test LLM only
   - `python jarvis_core.py` - Test core only
   - `python jarvis_unified.py` - Test full system

4. **Debug Mode**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

---

## 🎉 Post-Deployment

### Next Steps

1. **Customize for Your Workflow**
   - Add custom action callbacks
   - Tune thresholds
   - Adjust prompts

2. **Extend Functionality**
   - Add calendar integration
   - Connect to smart home
   - Add habit tracking

3. **Optimize Performance**
   - Profile bottlenecks
   - Fine-tune LLM
   - Optimize vision

4. **Share Your Setup**
   - Document your configuration
   - Share threshold settings
   - Contribute improvements

---

## 📅 Maintenance Schedule

### Daily
- Check console for errors
- Verify system responsiveness

### Weekly
- Review action logs
- Adjust thresholds if needed
- Update dependencies

### Monthly
- Check for model updates
- Review performance metrics
- Optimize prompts

---

**Deployment Status Tracker:**

```
[ ] Environment setup complete
[ ] Hardware verified
[ ] Component tests passed
[ ] Configuration tuned
[ ] Dry run successful
[ ] Production deployment
[ ] 24-hour stability test
[ ] Week 1 optimization
[ ] Customization complete
```

---

**READY TO DEPLOY? Let's go! 🚀**

```bash
cd testing/laptop
python jarvis_unified.py
```

---

*Built for reliability, optimized for performance, designed for privacy.*
