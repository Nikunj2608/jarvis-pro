# Validation Test Plan: Jarvis-Level Upgrades

**Status:** Ready for Hardware Testing  
**Estimated Time:** 2 hours

---

## Phase 1: Compilation & Upload (15 min)

### Test 1.1: ESP32 Compilation
```bash
# Arduino IDE
1. Open: src/main.cpp
2. Board: ESP32 Dev Module
3. Click: Verify (✓)
4. Expected: Compiles without errors
```

**Success Criteria:**
- ✅ No compilation errors
- ✅ Sketch uses ≤ 520KB SRAM
- ✅ Binary size reasonable (~200-300KB)

**Troubleshooting:**
- Missing FreeRTOS.h → Install ESP32 board support
- Syntax errors → Check world_state.h includes

---

### Test 1.2: Firmware Upload
```bash
# Arduino IDE
1. Connect ESP32 via USB
2. Port: Select COM port
3. Click: Upload (→)
4. Expected: Upload success, ESP32 boots
```

**Success Criteria:**
- ✅ Upload completes
- ✅ Serial monitor shows: "[Init] JARVIS Core System"
- ✅ All tasks start: "Event Reducer", "Decision Gate", etc.

**Expected Serial Output:**
```
[Init] JARVIS Core System v2.0
[Init] Event queue...
[Init] Starting tasks...
  [✓] Event Reducer
  [✓] Decision Gate
  [✓] Action Intent
  [✓] Snapshot Service
  [✓] Sensor Reader
  [✓] Time Tick
  [✓] Serial Input
[System] Waiting for events...
```

---

## Phase 2: Evidence Weighting (30 min)

### Test 2.1: Default Source Weight
```bash
# Send vision event (should be weighted to 70%)
echo "EVENT 2 1 100 1" > COM3

# Expected snapshot:
# belief = 100 × 70% = 70
```

**Success Criteria:**
- ✅ Belief = 70 (not 100)
- ✅ Serial shows: "[Event] Received: type=2 value=1 confidence=100"

---

### Test 2.2: PIR Override Vision
```bash
# First: Vision event (70% weight)
echo "EVENT 2 1 80 1" > COM3
# belief = 80 × 70% = 56

# Then: PIR event (90% weight)
echo "EVENT 1 1 70 0" > COM3
# belief = 70 × 90% = 63 (should WIN)

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ Final belief = 63 (PIR wins despite lower raw confidence)
- ✅ Decision explanation includes: "belief 63"

---

### Test 2.3: Manual Override Wins All
```bash
# Send manual override (100% weight)
echo "EVENT 3 1 50 3" > COM3
# belief = 50 × 100% = 50 (always accepted)

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ Belief = 50 (accepted despite other higher values)
- ✅ Activity mode changes to OVERRIDE

---

## Phase 3: Uncertainty Diagnosis (20 min)

### Test 3.1: Stale Data Detection
```bash
# Send event, then wait 6 minutes
echo "EVENT 2 1 80 1" > COM3
sleep 360  # 6 minutes

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ Decision reason contains: "(stale data)"
- ✅ Freshness decayed to low value

---

### Test 3.2: Low Signal Detection
```bash
# Send very low confidence event
echo "EVENT 2 1 35 1" > COM3
# belief = 35 × 70% = 24.5 → 24

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ Decision reason contains: "(low signal)"
- ✅ Belief < 40

---

### Test 3.3: High Confidence → No Uncertainty
```bash
# Send high confidence PIR event
echo "EVENT 1 1 95 0" > COM3
# belief = 95 × 90% = 85.5 → 85

# Request snapshot immediately
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ Decision permitted = true
- ✅ Uncertainty cause = UNCERTAINTY_NONE
- ✅ No uncertainty string in reason

---

## Phase 4: Session Tracking (15 min)

### Test 4.1: Session Start
```bash
# Send session start event
echo "EVENT 6 0 100 0" > COM3

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ active_session_id incremented
- ✅ session_count_today incremented
- ✅ session_start_ms set to current time

---

### Test 4.2: Multiple Sessions
```bash
# Session 1
echo "EVENT 6 0 100 0" > COM3
# Session 2
echo "EVENT 6 0 100 0" > COM3
# Session 3
echo "EVENT 6 0 100 0" > COM3

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ active_session_id = 3
- ✅ session_count_today = 3

---

## Phase 5: Habit Tracking (15 min)

### Test 5.1: Distraction Count
```bash
# Send distraction events
echo "EVENT 2 2 80 1" > COM3  # DISTRACTED mode (value=2)
echo "EVENT 2 2 80 1" > COM3
echo "EVENT 2 2 80 1" > COM3

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ distraction_count_today = 3
- ✅ Activity mode = DISTRACTED

---

### Test 5.2: Habit Stats Persistence
```bash
# Check initial values
echo -e '\x01' > COM3
# Expected: typical_focus_hour = 10, typical_distraction_hour = 15

# (Future: these should update based on actual patterns)
```

**Success Criteria:**
- ✅ Defaults present (10am focus, 3pm distraction)
- ✅ Stats included in snapshot

---

## Phase 6: Python Integration (30 min)

### Test 6.1: Python Connects
```bash
cd testing/laptop
python jarvis_laptop_interface.py
```

**Success Criteria:**
- ✅ Connects to ESP32
- ✅ Receives snapshots
- ✅ Vision provider starts
- ✅ LLM loads (or gracefully degrades)

---

### Test 6.2: Vision Evidence with Source
```python
# In jarvis_laptop_interface.py, check logs
# Expected: "[Vision] Evidence: No face detected (confidence: 70)"
# Serial should show: "EVENT 2 1 70 1"
```

**Success Criteria:**
- ✅ Events include source field
- ✅ ESP32 receives 4th parameter
- ✅ Evidence weighted correctly

---

### Test 6.3: LLM Refusal Logic
```bash
# Create low-confidence scenario
echo "EVENT 2 1 30 1" > COM3  # belief = 30 × 70% = 21

# Python should refuse to narrate
```

**Success Criteria:**
- ✅ LLM output contains: "confidence is too low" or "sensor data is too old"
- ✅ No hallucinated narration
- ✅ Refusal message explains cause

---

### Test 6.4: LLM Normal Narration
```bash
# Create high-confidence scenario
echo "EVENT 1 1 95 0" > COM3  # belief = 95 × 90% = 85

# Python should narrate normally
```

**Success Criteria:**
- ✅ LLM generates natural language summary
- ✅ No refusal message
- ✅ Narration reflects ESP32 state

---

## Phase 7: Backward Compatibility (10 min)

### Test 7.1: Old 3-Arg Protocol
```bash
# Send old-style event (no source)
echo "EVENT 2 1 80" > COM3

# Should default to SOURCE_VISION_LAPTOP (1)
```

**Success Criteria:**
- ✅ Event accepted
- ✅ Source defaults to VISION_LAPTOP
- ✅ Weighted as 70%

---

### Test 7.2: Mixed Protocols
```bash
# Send mix of old and new
echo "EVENT 2 1 80" > COM3      # Old (3 args)
echo "EVENT 1 1 90 0" > COM3    # New (4 args)
echo "EVENT 2 1 70" > COM3      # Old again
```

**Success Criteria:**
- ✅ All events accepted
- ✅ No parsing errors
- ✅ Belief fusion works correctly

---

## Phase 8: Stress Testing (15 min)

### Test 8.1: Event Queue Saturation
```bash
# Send 50 events rapidly
for i in {1..50}; do
    echo "EVENT 2 1 80 1" > COM3
done
```

**Success Criteria:**
- ✅ Queue doesn't overflow
- ✅ Some events may be dropped (logged)
- ✅ System remains responsive

---

### Test 8.2: Long-Running Stability
```bash
# Let system run for 30 minutes with periodic events
# Monitor serial output for errors
```

**Success Criteria:**
- ✅ No crashes
- ✅ No memory leaks (SRAM stable)
- ✅ Freshness decay works
- ✅ Periodic snapshots sent

---

## Phase 9: Edge Cases (10 min)

### Test 9.1: Conflicting Evidence
```bash
# Vision: Face detected (focus)
echo "EVENT 2 0 80 1" > COM3  # belief = 56

# PIR: No motion (distracted)
echo "EVENT 1 0 90 0" > COM3  # belief = 81 (should WIN)

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ PIR wins (higher weighted confidence)
- ✅ Uncertainty cause may be CONFLICTING_EVIDENCE (future)

---

### Test 9.2: Zero Confidence
```bash
# Send zero confidence event
echo "EVENT 2 1 0 1" > COM3  # belief = 0

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ Event accepted (valid edge case)
- ✅ Belief = 0
- ✅ Uncertainty cause = LOW_SIGNAL

---

### Test 9.3: Maximum Values
```bash
# Send max values
echo "EVENT 2 1 100 3" > COM3  # Manual override, max confidence

# Request snapshot
echo -e '\x01' > COM3
```

**Success Criteria:**
- ✅ Belief = 100
- ✅ Freshness = 100
- ✅ Decision permitted = true

---

## Expected Issues & Fixes

### Issue 1: Event Parsing Fails
**Symptom:** "[Error] Unknown command: EVENT..."  
**Fix:** Check sscanf format string, ensure 4 args

### Issue 2: Source Weight Incorrect
**Symptom:** Belief not weighted correctly  
**Fix:** Check get_source_weight() switch cases

### Issue 3: LLM Always Refuses
**Symptom:** Every narration is a refusal  
**Fix:** Check REFUSAL_BELIEF_THRESHOLD (should be 40, not 60)

### Issue 4: Python Can't Parse Snapshot
**Symptom:** Struct size mismatch  
**Fix:** Update SystemSnapshot dataclass to match C struct

---

## Success Metrics

### Minimum Viable
- [ ] ESP32 compiles and uploads
- [ ] Events weighted correctly
- [ ] Uncertainty diagnosis works
- [ ] Python connects and receives snapshots

### Full Success
- [ ] All Phase 1-6 tests pass
- [ ] LLM refusal logic works
- [ ] Session tracking increments
- [ ] Habit stats accumulate
- [ ] No crashes in stress test

### Excellence
- [ ] All Phase 1-9 tests pass
- [ ] Backward compatibility confirmed
- [ ] Edge cases handled gracefully
- [ ] 30-minute stability test passes

---

## Test Log Template

```
Date: ___________
Tester: ___________

Phase 1: Compilation
├─ 1.1 Compile: [ ] PASS [ ] FAIL
└─ 1.2 Upload:  [ ] PASS [ ] FAIL

Phase 2: Evidence Weighting
├─ 2.1 Default:  [ ] PASS [ ] FAIL
├─ 2.2 PIR wins: [ ] PASS [ ] FAIL
└─ 2.3 Override: [ ] PASS [ ] FAIL

Phase 3: Uncertainty
├─ 3.1 Stale:    [ ] PASS [ ] FAIL
├─ 3.2 Low sig:  [ ] PASS [ ] FAIL
└─ 3.3 High:     [ ] PASS [ ] FAIL

Phase 4: Sessions
├─ 4.1 Start:    [ ] PASS [ ] FAIL
└─ 4.2 Multiple: [ ] PASS [ ] FAIL

Phase 5: Habits
├─ 5.1 Count:    [ ] PASS [ ] FAIL
└─ 5.2 Stats:    [ ] PASS [ ] FAIL

Phase 6: Python
├─ 6.1 Connect:  [ ] PASS [ ] FAIL
├─ 6.2 Vision:   [ ] PASS [ ] FAIL
├─ 6.3 Refusal:  [ ] PASS [ ] FAIL
└─ 6.4 Narrate:  [ ] PASS [ ] FAIL

Phase 7: Compat
├─ 7.1 Old:      [ ] PASS [ ] FAIL
└─ 7.2 Mixed:    [ ] PASS [ ] FAIL

Phase 8: Stress
├─ 8.1 Queue:    [ ] PASS [ ] FAIL
└─ 8.2 Stable:   [ ] PASS [ ] FAIL

Phase 9: Edge
├─ 9.1 Conflict: [ ] PASS [ ] FAIL
├─ 9.2 Zero:     [ ] PASS [ ] FAIL
└─ 9.3 Max:      [ ] PASS [ ] FAIL

OVERALL: [ ] PASS [ ] FAIL
Notes:
_________________________________
_________________________________
```

---

## Post-Testing Next Steps

### If All Tests Pass ✅
1. Tune evidence weights based on observations
2. Adjust refusal thresholds if needed
3. Implement focus timer (habit accumulation)
4. Add midnight reset for daily stats

### If Tests Fail ❌
1. Document failure mode
2. Check serial output for errors
3. Verify struct alignment (C vs Python)
4. Review get_errors() output
5. Debug with verbose logging

---

**Ready to validate the Jarvis-level architecture!** 🚀
