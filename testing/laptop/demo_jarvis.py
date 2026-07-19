"""
JARVIS Demo Script for Design Engineering Presentation
=======================================================

This demonstrates the complete JARVIS automation system:
- Smart lighting (context-aware)
- Climate control (temperature-based)
- Scene management (focus, relax, sleep, away)
- Sensor integration (DHT11 temperature, PIR motion)

Runs in SIMULATION mode (no hardware required).
"""

import time
import sys
from automation_executor import AutomationExecutor, ActionId

def print_banner():
    """Print demo banner"""
    print("\n" + "="*70)
    print(" "*15 + "JARVIS AUTOMATION SYSTEM DEMO")
    print("="*70)
    print("\n📋 ARCHITECTURE:")
    print("   ESP32 C++ Core (Decision Maker)")
    print("        ↓")
    print("   Python Executor (This Demo)")
    print("        ↓")
    print("   Smart Devices (Lights, AC, Fan)")
    print("\n🎯 DEMO MODE: Software simulation (no hardware required)")
    print("="*70 + "\n")


def demo_scenario_1_evening_arrival():
    """Scenario 1: User arrives home in evening"""
    print("\n" + "="*70)
    print("SCENARIO 1: Evening Arrival Home")
    print("="*70)
    
    executor = AutomationExecutor()
    
    print("\n📍 Context: 7:00 PM, user enters room")
    print("🔍 PIR Sensor: Motion detected")
    print("🌡️  DHT11 Sensor: 28°C (warm evening)\n")
    
    # Step 1: Lights on (evening presence)
    print("\n[Step 1] Lighting System")
    print("-" * 40)
    success = executor.execute_action(
        ActionId.ACTION_LIGHT_ON, 
        value=100,
        rationale="Evening presence detected - full lighting"
    )
    time.sleep(2)
    
    # Step 2: AC on (temperature control)
    print("\n[Step 2] Climate Control")
    print("-" * 40)
    success = executor.execute_action(
        ActionId.ACTION_AC_SET_TEMP,
        value=24,
        rationale="High temperature (28°C) - cooling to 24°C"
    )
    time.sleep(2)
    
    # Show device status
    print("\n[Status] Current Device State:")
    print("-" * 40)
    executor.print_status()
    
    input("\n⏸️  Press Enter to continue to next scenario...")


def demo_scenario_2_focus_mode():
    """Scenario 2: User starts working (focus mode)"""
    print("\n" + "="*70)
    print("SCENARIO 2: Focus Mode Activation")
    print("="*70)
    
    executor = AutomationExecutor()
    
    print("\n📍 Context: User sits down at desk, opens laptop")
    print("🔍 Vision System: Focused posture detected for 5+ minutes")
    print("🧠 Decision: Activate focus environment\n")
    
    # Activate focus scene
    print("\n[Action] Activating Focus Scene")
    print("-" * 40)
    success = executor.execute_action(
        ActionId.ACTION_SCENE_FOCUS,
        value=0,
        rationale="Deep focus detected - optimizing environment"
    )
    time.sleep(2)
    
    print("\n[Status] Focus Mode Active:")
    print("-" * 40)
    executor.print_status()
    
    input("\n⏸️  Press Enter to continue to next scenario...")


def demo_scenario_3_climate_adaptation():
    """Scenario 3: Temperature changes throughout the day"""
    print("\n" + "="*70)
    print("SCENARIO 3: Adaptive Climate Control")
    print("="*70)
    
    executor = AutomationExecutor()
    
    print("\n📍 Context: Temperature fluctuates during the day")
    
    # Morning: Cool
    print("\n[Morning - 9:00 AM]")
    print("-" * 40)
    print("🌡️  DHT11: 22°C (comfortable)")
    print("🧠 Decision: No AC needed, fan off")
    time.sleep(1)
    
    # Afternoon: Getting warm
    print("\n[Afternoon - 2:00 PM]")
    print("-" * 40)
    print("🌡️  DHT11: 25°C (mild warmth)")
    print("🧠 Decision: Turn on fan for air circulation")
    executor.execute_action(
        ActionId.ACTION_FAN_SET_SPEED,
        value=40,
        rationale="Mild warmth (25°C) - gentle fan circulation"
    )
    time.sleep(2)
    
    # Evening: Hot
    print("\n[Evening - 6:00 PM]")
    print("-" * 40)
    print("🌡️  DHT11: 29°C (hot)")
    print("🧠 Decision: AC on, increase fan speed")
    executor.execute_action(
        ActionId.ACTION_AC_SET_TEMP,
        value=23,
        rationale="High temperature (29°C) - AC cooling to 23°C"
    )
    executor.execute_action(
        ActionId.ACTION_FAN_SET_SPEED,
        value=60,
        rationale="Enhanced air circulation with AC"
    )
    time.sleep(2)
    
    print("\n[Status] Climate System State:")
    print("-" * 40)
    executor.print_status()
    
    input("\n⏸️  Press Enter to continue to next scenario...")


def demo_scenario_4_scene_transitions():
    """Scenario 4: Scene management throughout the day"""
    print("\n" + "="*70)
    print("SCENARIO 4: Intelligent Scene Management")
    print("="*70)
    
    executor = AutomationExecutor()
    
    # Scene 1: Focus (work mode)
    print("\n[Scene 1] FOCUS MODE")
    print("-" * 40)
    print("📍 User working on important project")
    executor.execute_action(
        ActionId.ACTION_SCENE_FOCUS,
        rationale="Deep focus session - optimal productivity environment"
    )
    time.sleep(2)
    
    # Scene 2: Relax (break time)
    print("\n[Scene 2] RELAX MODE")
    print("-" * 40)
    print("📍 Taking a break, watching video")
    executor.execute_action(
        ActionId.ACTION_SCENE_RELAX,
        rationale="Break time - comfortable relaxation environment"
    )
    time.sleep(2)
    
    # Scene 3: Sleep (night time)
    print("\n[Scene 3] SLEEP MODE")
    print("-" * 40)
    print("📍 11:30 PM, preparing for sleep")
    executor.execute_action(
        ActionId.ACTION_SCENE_SLEEP,
        rationale="Night time - sleep-optimized environment"
    )
    time.sleep(2)
    
    # Scene 4: Away (leaving)
    print("\n[Scene 4] AWAY MODE")
    print("-" * 40)
    print("📍 No motion detected for 1+ hour")
    executor.execute_action(
        ActionId.ACTION_SCENE_AWAY,
        rationale="Prolonged absence - energy saving mode"
    )
    time.sleep(2)
    
    print("\n[Status] All Devices Secured:")
    print("-" * 40)
    executor.print_status()
    
    input("\n⏸️  Press Enter to continue...")


def demo_scenario_5_energy_efficiency():
    """Scenario 5: Energy efficiency and smart shutoff"""
    print("\n" + "="*70)
    print("SCENARIO 5: Energy Efficiency & Smart Shutoff")
    print("="*70)
    
    executor = AutomationExecutor()
    
    print("\n📍 Demonstrating intelligent energy management")
    
    # Setup: Devices on
    print("\n[Initial State] All devices active:")
    print("-" * 40)
    executor.execute_action(ActionId.ACTION_LIGHT_ON, value=100, rationale="Lights on")
    executor.execute_action(ActionId.ACTION_AC_ON, rationale="AC running")
    executor.execute_action(ActionId.ACTION_FAN_ON, rationale="Fan running")
    time.sleep(1)
    executor.print_status()
    
    # User leaves room
    print("\n[Event] PIR: No motion for 2 minutes")
    print("-" * 40)
    print("🧠 Decision: Turn off lights (room empty)")
    executor.execute_action(
        ActionId.ACTION_LIGHT_OFF,
        rationale="Room empty for 2+ minutes - lights off for energy savings"
    )
    time.sleep(2)
    
    # Extended absence
    print("\n[Event] PIR: No motion for 10 minutes")
    print("-" * 40)
    print("🧠 Decision: Turn off AC and fan (extended absence)")
    executor.execute_action(
        ActionId.ACTION_AC_OFF,
        rationale="Room empty for 10+ minutes - AC off for energy savings"
    )
    executor.execute_action(
        ActionId.ACTION_FAN_OFF,
        rationale="Room empty - fan off for energy savings"
    )
    time.sleep(2)
    
    print("\n[Status] Energy Saving Mode Active:")
    print("-" * 40)
    executor.print_status()
    print("\n💡 All devices safely powered off when not needed")
    
    input("\n⏸️  Press Enter to view demo summary...")


def demo_summary():
    """Show demo summary"""
    print("\n" + "="*70)
    print(" "*20 + "DEMO SUMMARY")
    print("="*70)
    
    print("\n✅ DEMONSTRATED FEATURES:")
    print("   [1] Context-Aware Lighting")
    print("       • Automatic on/off based on presence and time")
    print("       • Brightness adjustment for different activities")
    print()
    print("   [2] Intelligent Climate Control")
    print("       • Temperature-based AC automation")
    print("       • Smart fan speed adjustment")
    print("       • Energy-efficient operation")
    print()
    print("   [3] Scene Management")
    print("       • Focus: Optimized for productivity")
    print("       • Relax: Comfortable break environment")
    print("       • Sleep: Night-time optimization")
    print("       • Away: Energy-saving security mode")
    print()
    print("   [4] Sensor Integration")
    print("       • DHT11: Temperature/humidity monitoring")
    print("       • PIR: Motion detection")
    print("       • Vision: Activity analysis")
    print()
    print("   [5] Energy Efficiency")
    print("       • Smart shutoff when room empty")
    print("       • Adaptive control based on conditions")
    print()
    
    print("="*70)
    print("\n🏗️  ARCHITECTURE HIGHLIGHTS:")
    print("   • ESP32 C++ Core: Authoritative decision maker")
    print("   • Python Executor: Device control & coordination")
    print("   • Modular Design: Easy to extend with new devices")
    print("   • Simulation Mode: Test without hardware")
    print()
    
    print("="*70)
    print("\n📊 SYSTEM CAPABILITIES:")
    print(f"   • {len([a for a in ActionId])} automation actions")
    print("   • 4 intelligent scenes")
    print("   • 3 device types (lights, AC, fan)")
    print("   • Multi-sensor integration")
    print("   • Real-time decision making")
    print()
    
    print("="*70)
    print("\n🚀 READY FOR:")
    print("   ✓ Hardware integration (ESP32, DHT11, PIR, relays)")
    print("   ✓ Production deployment")
    print("   ✓ Extended device support (more lights, appliances)")
    print("   ✓ Additional sensors (LDR, sound, etc.)")
    print()
    
    print("="*70)
    print("\n💡 This is a JARVIS-CLASS intelligent automation system!")
    print("="*70 + "\n")


def main():
    """Run complete demo"""
    try:
        print_banner()
        
        print("This demo will walk you through 5 scenarios:")
        print("  1. Evening arrival home")
        print("  2. Focus mode activation")
        print("  3. Adaptive climate control")
        print("  4. Intelligent scene management")
        print("  5. Energy efficiency & smart shutoff")
        print("\n" + "="*70)
        
        input("\n▶️  Press Enter to start demo...")
        
        # Run all scenarios
        demo_scenario_1_evening_arrival()
        demo_scenario_2_focus_mode()
        demo_scenario_3_climate_adaptation()
        demo_scenario_4_scene_transitions()
        demo_scenario_5_energy_efficiency()
        
        # Show summary
        demo_summary()
        
        print("✨ Demo completed successfully!")
        print("\n📝 To run individual tests: python test_automation.py")
        print("🚀 To run with real hardware: python jarvis_laptop_interface.py")
        print()
        
    except KeyboardInterrupt:
        print("\n\n⏹️  Demo interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Demo error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
