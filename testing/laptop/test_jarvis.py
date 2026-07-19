"""
JARVIS System Test Suite
========================

Test individual components and full system integration.
"""

import time
import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))


def test_serial_client():
    """Test ESP32 serial client with LLM"""
    print("\n" + "="*60)
    print("TEST 1: Serial Client + Phi-2 LLM")
    print("="*60)
    
    try:
        from serial_client import ESP32Client
        
        print("[TEST] Initializing ESP32 client with Phi-2...")
        client = ESP32Client(port="COM3", use_llm=True)
        
        print("[TEST] Testing LLM with sample query...")
        response = client.query_jarvis("What is the purpose of JARVIS?")
        print(f"[TEST] LLM Response: {response}")
        
        print("\n✓ Serial Client Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n✗ Serial Client Test FAILED: {e}")
        return False


def test_vision_monitor():
    """Test vision monitoring system"""
    print("\n" + "="*60)
    print("TEST 2: Vision Monitor")
    print("="*60)
    
    try:
        from jarvis_core import VisionMonitor
        
        print("[TEST] Initializing vision monitor...")
        vision = VisionMonitor(camera_id=0)
        
        if not vision.start():
            print("[TEST] Camera not available - skipping")
            return True
        
        print("[TEST] Analyzing frame...")
        event = vision.analyze_frame()
        
        if event:
            print(f"[TEST] Event generated: {event.type.name}, confidence: {event.confidence}")
        
        vision.stop()
        print("\n✓ Vision Monitor Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n✗ Vision Monitor Test FAILED: {e}")
        return False


def test_world_state():
    """Test world state and event processing"""
    print("\n" + "="*60)
    print("TEST 3: World State & Event Processing")
    print("="*60)
    
    try:
        from jarvis_core import WorldState, EventReducer, Event, EventType, ActivityMode
        
        print("[TEST] Creating world state...")
        world = WorldState(
            day_segment=0,
            last_sync_ms=int(time.time() * 1000),
            room_occupied=False,
            last_motion_ms=0,
            activity_mode=ActivityMode.IDLE,
            mode_start_ms=int(time.time() * 1000)
        )
        
        print("[TEST] Creating event reducer...")
        reducer = EventReducer(world)
        
        print("[TEST] Processing presence event...")
        event = Event(
            type=EventType.PRESENCE,
            timestamp=time.time(),
            value=1,
            confidence=80
        )
        
        world = reducer.process_event(event)
        print(f"[TEST] Room occupied: {world.room_occupied}")
        print(f"[TEST] Belief: {world.belief}")
        
        print("\n✓ World State Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n✗ World State Test FAILED: {e}")
        return False


def test_decision_gate():
    """Test decision gate logic"""
    print("\n" + "="*60)
    print("TEST 4: Decision Gate")
    print("="*60)
    
    try:
        from jarvis_core import WorldState, DecisionGate, ActivityMode, DaySegment
        
        print("[TEST] Creating world state...")
        world = WorldState(
            day_segment=DaySegment.AFTERNOON,
            last_sync_ms=int(time.time() * 1000),
            room_occupied=True,
            last_motion_ms=int(time.time() * 1000),
            activity_mode=ActivityMode.FOCUS,
            mode_start_ms=int(time.time() * 1000),
            belief=80,
            freshness=90
        )
        
        print("[TEST] Creating decision gate...")
        gate = DecisionGate()
        
        print("[TEST] Evaluating decision...")
        decision = gate.evaluate(world)
        
        print(f"[TEST] Permitted: {decision.permitted}")
        print(f"[TEST] Reason: {decision.reason}")
        print(f"[TEST] Belief: {decision.belief}")
        print(f"[TEST] Freshness: {decision.freshness}")
        
        print("\n✓ Decision Gate Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n✗ Decision Gate Test FAILED: {e}")
        return False


def test_action_intent():
    """Test action intent engine"""
    print("\n" + "="*60)
    print("TEST 5: Action Intent Engine")
    print("="*60)
    
    try:
        from jarvis_core import (WorldState, DecisionGate, ActionIntentEngine, 
                                ActivityMode, DaySegment, DecisionExplanation)
        
        print("[TEST] Creating world state (distracted)...")
        world = WorldState(
            day_segment=DaySegment.AFTERNOON,
            last_sync_ms=int(time.time() * 1000),
            room_occupied=True,
            last_motion_ms=int(time.time() * 1000),
            activity_mode=ActivityMode.DISTRACTED,
            mode_start_ms=int(time.time() * 1000),
            distraction_confidence=80,
            belief=70,
            freshness=80
        )
        
        print("[TEST] Creating decision...")
        decision = DecisionExplanation(
            permitted=True,
            belief=70,
            freshness=80,
            reason="High distraction detected"
        )
        
        print("[TEST] Creating action engine...")
        engine = ActionIntentEngine()
        
        print("[TEST] Evaluating action intent...")
        intent = engine.evaluate(world, decision)
        
        print(f"[TEST] Action proposed: {intent.proposed}")
        print(f"[TEST] Action ID: {intent.action_id}")
        print(f"[TEST] Rationale: {intent.rationale}")
        print(f"[TEST] Priority: {intent.priority}")
        
        print("\n✓ Action Intent Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n✗ Action Intent Test FAILED: {e}")
        return False


def test_full_integration():
    """Test full JARVIS core integration"""
    print("\n" + "="*60)
    print("TEST 6: Full System Integration")
    print("="*60)
    
    try:
        from jarvis_core import JARVISCore, Event, EventType
        
        print("[TEST] Initializing JARVIS core...")
        jarvis = JARVISCore(esp_port="COM3", camera_id=0)
        
        print("[TEST] Starting systems...")
        jarvis.start()
        
        print("[TEST] Emitting test events...")
        
        # Emit presence event
        jarvis.emit_event(Event(
            type=EventType.PRESENCE,
            timestamp=time.time(),
            value=1,
            confidence=80
        ))
        
        # Wait for processing
        time.sleep(2)
        
        # Check world state
        state = jarvis.get_world_state()
        print(f"[TEST] Room occupied: {state.room_occupied}")
        print(f"[TEST] Activity mode: {state.activity_mode.name}")
        print(f"[TEST] Belief: {state.belief}")
        
        print("[TEST] Stopping systems...")
        jarvis.stop()
        
        print("\n✓ Full Integration Test PASSED")
        return True
        
    except Exception as e:
        print(f"\n✗ Full Integration Test FAILED: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("\n" + "="*60)
    print("JARVIS SYSTEM TEST SUITE")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("Serial Client + LLM", test_serial_client()))
    results.append(("Vision Monitor", test_vision_monitor()))
    results.append(("World State & Events", test_world_state()))
    results.append(("Decision Gate", test_decision_gate()))
    results.append(("Action Intent", test_action_intent()))
    results.append(("Full Integration", test_full_integration()))
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status:8} - {name}")
    
    print("\n" + "="*60)
    print(f"Results: {passed}/{total} tests passed")
    print("="*60 + "\n")
    
    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
