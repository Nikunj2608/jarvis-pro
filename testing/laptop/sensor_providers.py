"""
Physical Sensor Evidence Providers
==================================

Provides evidence from DHT11 (temp/humidity) and PIR (motion) sensors.
"""

import time
import threading
from typing import Optional

# Mock imports (replace with actual libraries)
# import Adafruit_DHT  # For DHT11
# import RPi.GPIO as GPIO  # For PIR


class DHT11Provider:
    """Provides temperature and humidity evidence from DHT11"""
    
    def __init__(self, esp_interface, pin: int = 4):
        self.esp = esp_interface
        self.pin = pin
        self.running = False
        
        # TODO: Initialize DHT11 sensor
        print(f"[DHT11] Initialized on pin {pin}")
    
    def read_sensor(self) -> Optional[tuple]:
        """
        Read DHT11 sensor.
        
        Returns:
            (temperature_C, humidity_%) or None if error
        """
        # TODO: Actual sensor read
        # humidity, temperature = Adafruit_DHT.read_retry(Adafruit_DHT.DHT11, self.pin)
        
        # Mock data for now
        import random
        temperature = 23.0 + random.uniform(-2, 3)
        humidity = 55 + random.randint(-10, 10)
        
        return (temperature, humidity)
    
    def evidence_loop(self):
        """Continuously read DHT11 and send evidence to ESP32"""
        from jarvis_laptop_interface import EventType, EvidenceSource
        
        while self.running:
            data = self.read_sensor()
            
            if data:
                temp, humidity = data
                
                # Send as EV_ENV_UPDATE event
                # Encode as: value = (temp * 10) + (humidity << 16)
                value = int(temp * 10) | (humidity << 16)
                
                self.esp.send_event(
                    EventType.EV_ENV_UPDATE,
                    value=value,
                    confidence=90,
                    source=EvidenceSource.SOURCE_ENV_SENSOR
                )
                
                print(f"[DHT11] Evidence: {temp:.1f}°C, {humidity}% humidity")
            
            time.sleep(60)  # Read every minute


class PIRProvider:
    """Provides motion detection evidence from PIR sensor"""
    
    def __init__(self, esp_interface, pin: int = 17):
        self.esp = esp_interface
        self.pin = pin
        self.running = False
        self.last_motion_time = 0
        
        # TODO: Initialize GPIO for PIR
        # GPIO.setmode(GPIO.BCM)
        # GPIO.setup(self.pin, GPIO.IN)
        
        print(f"[PIR] Initialized on pin {pin}")
    
    def read_sensor(self) -> bool:
        """
        Read PIR sensor state.
        
        Returns:
            True if motion detected
        """
        # TODO: Actual GPIO read
        # return GPIO.input(self.pin) == GPIO.HIGH
        
        # Mock data for testing
        import random
        return random.random() > 0.7  # 30% chance of motion
    
    def evidence_loop(self):
        """Continuously monitor PIR and send evidence to ESP32"""
        from jarvis_laptop_interface import EventType, EvidenceSource
        
        while self.running:
            motion_detected = self.read_sensor()
            current_time = time.time()
            
            if motion_detected:
                # Only send if motion is new (>5 seconds since last)
                if (current_time - self.last_motion_time) > 5:
                    self.last_motion_time = current_time
                    
                    # Send EV_PRESENCE event with high confidence (PIR is reliable)
                    self.esp.send_event(
                        EventType.EV_PRESENCE,
                        value=1,  # Present
                        confidence=90,
                        source=EvidenceSource.SOURCE_MOTION_PIR
                    )
                    
                    print(f"[PIR] Evidence: Motion detected (confidence: 90%)")
            
            time.sleep(0.5)  # Check every 500ms