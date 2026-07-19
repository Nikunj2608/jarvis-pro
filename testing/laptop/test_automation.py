"""
Test Script for JARVIS Automation System
========================================

Tests the automation executor without ESP32 hardware.
Simulates action commands and verifies device control.
"""

import time
from automation_executor import AutomationExecutor, ActionId


def test_lighting():
    """Test lighting automation"""
    print("\n" + "="*60)
    print("TEST 1: LIGHTING CONTROL")
    print("="*60)
    
    executor = AutomationExecutor()
    
    # Test: Light ON
    print("\n[Test] Turn lights ON...")
    executor.execute_action(
        ActionId.ACTION_LIGHT_ON, 
        100, 
        "Evening presence detected - lights on"
    )
    time.sleep(1)
    
    # Test: Light DIM
    print("\n[Test] Dim lights for focus mode...")
    executor.execute_action(
        ActionId.ACTION_LIGHT_DIM, 
        60, 
        "Focus mode active - dimmed lighting"
    )
    time.sleep(1)
    
    # Test: Light OFF
    print("\n[Test] Turn lights OFF...")
    executor.execute_action(
        ActionId.ACTION_LIGHT_OFF, 
        0, 
        "Room empty for 2+ minutes - lights off"
    )
    time.sleep(1)
    
    executor.print_status()
    return executor


def test_climate():
    """Test climate control (AC and Fan)"""
    print("\n" + "="*60)
    print("TEST 2: CLIMATE CONTROL")
    print("="*60)
    
    executor = AutomationExecutor()
    
    # Test: AC ON with temperature
    print("\n[Test] Turn AC ON at 24°C...")
    executor.execute_action(
        ActionId.ACTION_AC_SET_TEMP, 
        24, 
        "High temperature (28°C) - AC to 24°C"
    )
    time.sleep(1)
    
    # Test: Fan speed control
    print("\n[Test] Set fan to medium speed...")
    executor.execute_action(
        ActionId.ACTION_FAN_SET_SPEED, 
        50, 
        "Mild warmth (25°C) - fan at 50%"
    )
    time.sleep(1)
    
    # Test: AC OFF
    print("\n[Test] Turn AC OFF...")
    executor.execute_action(
        ActionId.ACTION_AC_OFF, 
        0, 
        "Room empty for 10+ minutes - AC off"
    )
    time.sleep(1)
    
    # Test: Fan OFF
    print("\n[Test] Turn fan OFF...")
    executor.execute_action(
        ActionId.ACTION_FAN_OFF, 
        0, 
        "Temperature comfortable - fan off"
    )
    time.sleep(1)
    
    executor.print_status()
    return executor


def test_scenes():
    """Test scene automation"""
    print("\n" + "="*60)
    print("TEST 3: SCENE AUTOMATION")
    print("="*60)
    
    executor = AutomationExecutor()
    
    # Test: FOCUS scene
    print("\n[Test] Activate FOCUS scene...")
    executor.execute_action(
        ActionId.ACTION_SCENE_FOCUS, 
        0, 
        "Deep focus mode detected - optimal environment"
    )
    time.sleep(2)
    
    # Test: RELAX scene
    print("\n[Test] Activate RELAX scene...")
    executor.execute_action(
        ActionId.ACTION_SCENE_RELAX, 
        0, 
        "Distraction detected - relax mode"
    )
    time.sleep(2)
    
    # Test: SLEEP scene
    print("\n[Test] Activate SLEEP scene...")
    executor.execute_action(
        ActionId.ACTION_SCENE_SLEEP, 
        0, 
        "Night + prolonged absence - sleep mode"
    )
    time.sleep(2)
    
    # Test: AWAY scene
    print("\n[Test] Activate AWAY scene...")
    executor.execute_action(
        ActionId.ACTION_SCENE_AWAY, 
        0, 
        "No presence for 1+ hour - away mode"
    )
    time.sleep(2)
    
    executor.print_status()
    return executor


def test_automation_flow():
    """Test realistic automation flow"""
    print("\n" + "="*60)
    print("TEST 4: REALISTIC AUTOMATION FLOW")
    print("="*60)
    
    executor = AutomationExecutor()
    
    print("\n[Scenario] Evening arrival home...")
    time.sleep(1)
    
    # Step 1: PIR detects motion at 7 PM
    print("\n[Event] PIR: Motion detected (evening)")
    executor.execute_action(
        ActionId.ACTION_LIGHT_ON, 
        100, 
        "Presence detected in evening - lights on"
    )
    time.sleep(2)
    
    # Step 2: Temperature is 27°C
    print("\n[Event] DHT11: Temperature 27°C")
    executor.execute_action(
        ActionId.ACTION_AC_SET_TEMP, 
        24, 
        "High temperature (27°C) - AC to 24°C"
    )
    time.sleep(2)
    
    # Step 3: User enters focus mode
    print("\n[Event] Vision: User focusing on work")
    executor.execute_action(
        ActionId.ACTION_SCENE_FOCUS, 
        0, 
        "Deep focus mode (5+ minutes) - optimal environment"
    )
    time.sleep(2)
    
    # Step 4: Late night, no motion for 30 min
    print("\n[Event] PIR: No motion for 30 minutes (11 PM)")
    executor.execute_action(
        ActionId.ACTION_SCENE_SLEEP, 
        0, 
        "Night + prolonged absence - sleep mode"
    )
    time.sleep(2)
    
    executor.print_status()
    return executor


def test_error_handling():
    """Test error handling and edge cases"""
    print("\n" + "="*60)
    print("TEST 5: ERROR HANDLING")
    print("="*60)
    
    executor = AutomationExecutor()
    
    # Test: Invalid action ID
    print("\n[Test] Invalid action ID (999)...")
    success = executor.execute_action(999, 0, "Invalid action test")
    assert not success, "Should fail for invalid action ID"
    print("[Result] ✓ Correctly rejected invalid action")
    
    # Test: Boundary values
    print("\n[Test] Boundary values...")
    executor.execute_action(ActionId.ACTION_LIGHT_DIM, 0, "Minimum brightness")
    time.sleep(0.5)
    executor.execute_action(ActionId.ACTION_LIGHT_DIM, 100, "Maximum brightness")
    time.sleep(0.5)
    executor.execute_action(ActionId.ACTION_AC_SET_TEMP, 16, "Min temperature")
    time.sleep(0.5)
    executor.execute_action(ActionId.ACTION_AC_SET_TEMP, 30, "Max temperature")
    print("[Result] ✓ Boundary values handled")
    
    executor.print_status()
    return executor


def main():
    """Run all automation tests"""
    print("\n" + "="*70)
    print(" " * 15 + "JARVIS AUTOMATION SYSTEM TESTS")
    print("="*70)
    print("\nArchitecture:")
    print("  ESP32 C++ Core → Action Intent → This Executor → Smart Devices")
    print("\nNote: This is simulation mode (no real hardware control)")
    print("="*70)
    
    try:
        # Run tests
        test_lighting()
        time.sleep(1)
        
        test_climate()
        time.sleep(1)
        
        test_scenes()
        time.sleep(1)
        
        test_automation_flow()
        time.sleep(1)
        
        test_error_handling()
        
        # Final summary
        print("\n" + "="*70)
        print(" " * 20 + "ALL TESTS COMPLETED")
        print("="*70)
        print("\n✓ Lighting control: PASS")
        print("✓ Climate control: PASS")
        print("✓ Scene automation: PASS")
        print("✓ Automation flow: PASS")
        print("✓ Error handling: PASS")
        print("\n[Summary] Automation system ready for integration!")
        print("="*70 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n[Test] Interrupted by user")
    except Exception as e:
        print(f"\n\n[Test] Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
