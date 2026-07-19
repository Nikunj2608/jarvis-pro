"""
JARVIS Automation Executor
==========================

Executes automation actions commanded by ESP32 C++ core.
Does NOT make automation decisions - only executes them.

ARCHITECTURE:
    ESP32 C++ Core → Action Intent → Serial → This Executor → Smart Devices
"""

import time
import threading
from typing import Dict, Callable, Optional, Any
from enum import IntEnum


# ============ ACTION TYPES (MIRROR C++) ============

class ActionId(IntEnum):
    """Mirror of action_intent.h"""
    ACTION_NONE = 0
    ACTION_NOTIFY_USER = 1
    ACTION_SUGGEST_BREAK = 2
    ACTION_LOG_EVENT = 3
    
    # Smart home automation
    ACTION_LIGHT_ON = 10
    ACTION_LIGHT_OFF = 11
    ACTION_LIGHT_DIM = 12
    ACTION_AC_ON = 20
    ACTION_AC_OFF = 21
    ACTION_AC_SET_TEMP = 22
    ACTION_FAN_ON = 30
    ACTION_FAN_OFF = 31
    ACTION_FAN_SET_SPEED = 32
    ACTION_SCENE_FOCUS = 40
    ACTION_SCENE_RELAX = 41
    ACTION_SCENE_SLEEP = 42
    ACTION_SCENE_AWAY = 43


# ============ DEVICE CONTROLLERS ============

class LightController:
    """Controls smart lights (GPIO relays, WiFi bulbs, etc.)"""
    
    def __init__(self, pin: Optional[int] = None):
        self.pin = pin
        self.is_on = False
        self.brightness = 0
        
        # TODO: Initialize GPIO or WiFi connection
        # try:
        #     import RPi.GPIO as GPIO
        #     GPIO.setmode(GPIO.BCM)
        #     if self.pin:
        #         GPIO.setup(self.pin, GPIO.OUT)
        # except:
        #     pass
        
        print(f"[Light] Controller initialized (pin: {pin})")
    
    def turn_on(self, brightness: int = 100):
        """Turn light on at specified brightness (0-100)"""
        self.is_on = True
        self.brightness = brightness
        print(f"[Light] ON at {brightness}%")
        
        # TODO: Actual GPIO/WiFi control
        # if self.pin:
        #     GPIO.output(self.pin, GPIO.HIGH)
        return True
    
    def turn_off(self):
        """Turn light off"""
        self.is_on = False
        self.brightness = 0
        print(f"[Light] OFF")
        
        # TODO: Actual GPIO/WiFi control
        # if self.pin:
        #     GPIO.output(self.pin, GPIO.LOW)
        return True
    
    def set_brightness(self, brightness: int):
        """Set brightness (0-100)"""
        if brightness > 0:
            self.is_on = True
        else:
            self.is_on = False
        self.brightness = brightness
        print(f"[Light] Brightness set to {brightness}%")
        
        # TODO: PWM or WiFi dimming control
        # if self.pin:
        #     pwm = GPIO.PWM(self.pin, 1000)  # 1kHz frequency
        #     pwm.start(brightness)
        return True


class ACController:
    """Controls AC via IR blaster or smart plug"""
    
    def __init__(self):
        self.is_on = False
        self.target_temp = 24
        
        # TODO: Initialize IR blaster
        # try:
        #     import lirc
        #     lirc.init("myprogram")
        # except:
        #     pass
        
        print(f"[AC] Controller initialized")
    
    def turn_on(self, temp: int = 24):
        """Turn AC on and set temperature"""
        self.is_on = True
        self.target_temp = temp
        print(f"[AC] ON - Target: {temp}°C")
        
        # TODO: Send IR command or smart plug control
        # lirc.send_once("ac_remote", "power_on")
        # time.sleep(0.5)
        # lirc.send_once("ac_remote", f"temp_{temp}")
        return True
    
    def turn_off(self):
        """Turn AC off"""
        self.is_on = False
        print(f"[AC] OFF")
        
        # TODO: Send IR command
        # lirc.send_once("ac_remote", "power_off")
        return True
    
    def set_temperature(self, temp: int):
        """Set AC temperature"""
        self.target_temp = temp
        if self.is_on:
            print(f"[AC] Temperature set to {temp}°C")
            # TODO: Send IR command
            # lirc.send_once("ac_remote", f"temp_{temp}")
        else:
            # Turn on if setting temperature
            self.turn_on(temp)
        return True


class FanController:
    """Controls ceiling/table fan"""
    
    def __init__(self, pin: Optional[int] = None):
        self.pin = pin
        self.is_on = False
        self.speed = 0
        
        # TODO: Initialize GPIO for fan control
        # try:
        #     import RPi.GPIO as GPIO
        #     GPIO.setmode(GPIO.BCM)
        #     if self.pin:
        #         GPIO.setup(self.pin, GPIO.OUT)
        # except:
        #     pass
        
        print(f"[Fan] Controller initialized (pin: {pin})")
    
    def turn_on(self, speed: int = 50):
        """Turn fan on at specified speed (0-100)"""
        self.is_on = True
        self.speed = speed
        print(f"[Fan] ON at {speed}%")
        
        # TODO: PWM control for variable speed
        # if self.pin:
        #     pwm = GPIO.PWM(self.pin, 50)  # 50Hz for motors
        #     duty_cycle = (speed / 100.0) * 100
        #     pwm.start(duty_cycle)
        return True
    
    def turn_off(self):
        """Turn fan off"""
        self.is_on = False
        self.speed = 0
        print(f"[Fan] OFF")
        
        # TODO: GPIO control
        # if self.pin:
        #     GPIO.output(self.pin, GPIO.LOW)
        return True
    
    def set_speed(self, speed: int):
        """Set fan speed (0-100)"""
        if speed > 0:
            self.is_on = True
        else:
            self.is_on = False
        self.speed = speed
        print(f"[Fan] Speed set to {speed}%")
        
        # TODO: Adjust PWM duty cycle
        # if self.pin and speed > 0:
        #     pwm = GPIO.PWM(self.pin, 50)
        #     duty_cycle = (speed / 100.0) * 100
        #     pwm.ChangeDutyCycle(duty_cycle)
        return True


# ============ SCENE MANAGER ============

class SceneManager:
    """Executes multi-device scenes"""
    
    def __init__(self, light: LightController, ac: ACController, fan: FanController):
        self.light = light
        self.ac = ac
        self.fan = fan
    
    def execute_focus_scene(self):
        """Focus mode: Dimmed lights, comfortable temperature"""
        print("\n[Scene] ═══════════════════════════════")
        print("[Scene] Activating FOCUS MODE")
        print("[Scene] ───────────────────────────────")
        self.light.set_brightness(60)  # Dimmed for concentration
        self.ac.set_temperature(23)    # Cool for alertness
        self.fan.turn_off()            # Quiet environment
        print("[Scene] Focus mode activated")
        print("[Scene] ═══════════════════════════════\n")
    
    def execute_relax_scene(self):
        """Relax mode: Warm lighting, moderate temperature"""
        print("\n[Scene] ═══════════════════════════════")
        print("[Scene] Activating RELAX MODE")
        print("[Scene] ───────────────────────────────")
        self.light.set_brightness(80)  # Warm brightness
        self.ac.set_temperature(25)    # Warmer, comfortable
        self.fan.set_speed(30)         # Low speed, gentle breeze
        print("[Scene] Relax mode activated")
        print("[Scene] ═══════════════════════════════\n")
    
    def execute_sleep_scene(self):
        """Sleep mode: All off or night light only"""
        print("\n[Scene] ═══════════════════════════════")
        print("[Scene] Activating SLEEP MODE")
        print("[Scene] ───────────────────────────────")
        self.light.set_brightness(5)   # Night light only
        self.ac.set_temperature(26)    # Energy saving
        self.fan.turn_off()
        print("[Scene] Sleep mode activated")
        print("[Scene] ═══════════════════════════════\n")
    
    def execute_away_scene(self):
        """Away mode: Everything off for energy saving"""
        print("\n[Scene] ═══════════════════════════════")
        print("[Scene] Activating AWAY MODE")
        print("[Scene] ───────────────────────────────")
        self.light.turn_off()
        self.ac.turn_off()
        self.fan.turn_off()
        print("[Scene] Away mode activated - All devices off")
        print("[Scene] ═══════════════════════════════\n")


# ============ AUTOMATION EXECUTOR ============

class AutomationExecutor:
    """
    Executes automation actions from ESP32 C++ core.
    Receives action intents via serial and controls devices.
    
    CRITICAL: This class does NOT make decisions.
    It only executes commands from the authoritative ESP32 C++ core.
    """
    
    def __init__(self, light_pin: Optional[int] = None, fan_pin: Optional[int] = None):
        # Initialize device controllers
        self.light = LightController(pin=light_pin)
        self.ac = ACController()
        self.fan = FanController(pin=fan_pin)
        self.scenes = SceneManager(self.light, self.ac, self.fan)
        
        # Action execution history
        self.last_action_time = 0
        self.action_count = 0
        
        # Action handler mapping
        self.handlers: Dict[ActionId, Callable[[int], bool]] = {
            ActionId.ACTION_LIGHT_ON: lambda value: self.light.turn_on(value if value > 0 else 100),
            ActionId.ACTION_LIGHT_OFF: lambda value: self.light.turn_off(),
            ActionId.ACTION_LIGHT_DIM: lambda value: self.light.set_brightness(value),
            ActionId.ACTION_AC_ON: lambda value: self.ac.turn_on(value if value > 0 else 24),
            ActionId.ACTION_AC_OFF: lambda value: self.ac.turn_off(),
            ActionId.ACTION_AC_SET_TEMP: lambda value: self.ac.set_temperature(value),
            ActionId.ACTION_FAN_ON: lambda value: self.fan.turn_on(value if value > 0 else 50),
            ActionId.ACTION_FAN_OFF: lambda value: self.fan.turn_off(),
            ActionId.ACTION_FAN_SET_SPEED: lambda value: self.fan.set_speed(value),
            ActionId.ACTION_SCENE_FOCUS: lambda value: (self.scenes.execute_focus_scene(), True)[1],
            ActionId.ACTION_SCENE_RELAX: lambda value: (self.scenes.execute_relax_scene(), True)[1],
            ActionId.ACTION_SCENE_SLEEP: lambda value: (self.scenes.execute_sleep_scene(), True)[1],
            ActionId.ACTION_SCENE_AWAY: lambda value: (self.scenes.execute_away_scene(), True)[1],
        }
        
        print("[Automation] ✓ Executor initialized")
        print("[Automation]   - Light controller ready")
        print("[Automation]   - AC controller ready")
        print("[Automation]   - Fan controller ready")
        print("[Automation]   - Scene manager ready")
    
    def execute_action(self, action_id: int, value: int = 0, rationale: str = "") -> bool:
        """
        Execute automation action commanded by ESP32 C++ core.
        
        Args:
            action_id: Action to execute (from ActionId enum)
            value: Action parameter (brightness %, temp °C, speed %, etc.)
            rationale: Explanation from C++ core (why this action?)
            
        Returns:
            True if execution succeeded, False otherwise
        """
        # Validate action ID
        try:
            action = ActionId(action_id)
        except ValueError:
            print(f"[Automation] ✗ Unknown action ID: {action_id}")
            return False
        
        # Skip if no action
        if action == ActionId.ACTION_NONE:
            return True
        
        # Check if handler exists
        if action not in self.handlers:
            print(f"[Automation] ✗ No handler for action: {action.name}")
            return False
        
        # Log execution
        print(f"\n[Automation] ═══════════════════════════════")
        print(f"[Automation] Executing: {action.name}")
        print(f"[Automation] Value: {value}")
        print(f"[Automation] Rationale: {rationale}")
        print(f"[Automation] ───────────────────────────────")
        
        # Execute action
        try:
            result = self.handlers[action](value)
            self.last_action_time = time.time()
            self.action_count += 1
            
            print(f"[Automation] ✓ {action.name} executed successfully")
            print(f"[Automation] ═══════════════════════════════\n")
            return True
        except Exception as e:
            print(f"[Automation] ✗ Execution failed: {e}")
            print(f"[Automation] ═══════════════════════════════\n")
            return False
    
    def get_device_status(self) -> Dict[str, Any]:
        """Get current status of all devices"""
        return {
            "light": {
                "is_on": self.light.is_on,
                "brightness": self.light.brightness
            },
            "ac": {
                "is_on": self.ac.is_on,
                "target_temp": self.ac.target_temp
            },
            "fan": {
                "is_on": self.fan.is_on,
                "speed": self.fan.speed
            },
            "stats": {
                "total_actions": self.action_count,
                "last_action_time": self.last_action_time
            }
        }
    
    def print_status(self):
        """Print current device status"""
        status = self.get_device_status()
        print("\n[Automation] Device Status:")
        print(f"  Light: {'ON' if status['light']['is_on'] else 'OFF'} ({status['light']['brightness']}%)")
        print(f"  AC: {'ON' if status['ac']['is_on'] else 'OFF'} ({status['ac']['target_temp']}°C)")
        print(f"  Fan: {'ON' if status['fan']['is_on'] else 'OFF'} ({status['fan']['speed']}%)")
        print(f"  Total actions: {status['stats']['total_actions']}\n")


# ============ EXAMPLE USAGE ============

if __name__ == "__main__":
    # Test automation executor
    print("Testing JARVIS Automation Executor")
    print("=" * 50)
    
    executor = AutomationExecutor()
    
    # Test lighting
    print("\n1. Testing lighting control...")
    executor.execute_action(ActionId.ACTION_LIGHT_ON, 100, "Testing light on")
    time.sleep(1)
    executor.execute_action(ActionId.ACTION_LIGHT_DIM, 50, "Testing light dim")
    time.sleep(1)
    executor.execute_action(ActionId.ACTION_LIGHT_OFF, 0, "Testing light off")
    
    # Test AC
    print("\n2. Testing AC control...")
    executor.execute_action(ActionId.ACTION_AC_SET_TEMP, 24, "Testing AC temperature")
    time.sleep(1)
    executor.execute_action(ActionId.ACTION_AC_OFF, 0, "Testing AC off")
    
    # Test fan
    print("\n3. Testing fan control...")
    executor.execute_action(ActionId.ACTION_FAN_SET_SPEED, 75, "Testing fan speed")
    time.sleep(1)
    executor.execute_action(ActionId.ACTION_FAN_OFF, 0, "Testing fan off")
    
    # Test scene
    print("\n4. Testing scene activation...")
    executor.execute_action(ActionId.ACTION_SCENE_FOCUS, 0, "Testing focus scene")
    time.sleep(2)
    executor.execute_action(ActionId.ACTION_SCENE_RELAX, 0, "Testing relax scene")
    time.sleep(2)
    executor.execute_action(ActionId.ACTION_SCENE_AWAY, 0, "Testing away scene")
    
    # Print final status
    executor.print_status()
