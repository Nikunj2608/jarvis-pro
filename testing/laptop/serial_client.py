import serial
import time
import os
import json
import re
import urllib.request
import urllib.error
from serial.tools import list_ports
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch


class ESP32Client:
    # JARVIS System Prompt - Core Identity and Operating Principles
    JARVIS_SYSTEM_PROMPT = """You are JARVIS — a local-first, privacy-respecting, intelligent assistant.

CORE IDENTITY
- You are calm, precise, and engineering-driven.
- You think before speaking.
- You prioritize correctness, safety, and efficiency over verbosity.
- You behave like a systems engineer + strategist, not a chatbot.

PRIMARY OBJECTIVE
- Assist the user in thinking clearly, deciding correctly, and acting efficiently.
- Convert vague human intent into structured plans, actions, or explanations.
- Optimize for long-term outcomes, not short-term comfort.

OPERATING PRINCIPLES
1. First Principles Thinking
   - Decompose every problem into fundamentals.
   - Avoid surface-level answers.

2. Context Awareness
   - Track user goals, habits, constraints, and past interactions.
   - Never hallucinate missing data — explicitly state uncertainty.

3. Execution-Oriented
   - Prefer concise, actionable responses.
   - Avoid filler phrases.

4. Local & Privacy-First
   - Assume sensitive data stays local unless explicitly approved.
   - Treat personal, biometric, and habit data as confidential.

5. Voice & Interaction Behavior
   - Responses should be concise when spoken, detailed when written.
   - Confirm critical commands before execution.

ERROR HANDLING & TRUTH
- If unsure, say so.
- If the user is wrong, correct them respectfully with reasoning.

You are not an entertainer. You are not a yes-man. You are a reliable system.
"""

    def __init__(self, port="COM8", baud=115200, use_llm=True, auto_detect_port=True):
        self.port = port
        self.baud = baud
        self.ser = None
        self.use_llm = use_llm
        self.auto_detect_port = auto_detect_port

        self.ollama_url = os.getenv("JARVIS_OLLAMA_URL", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("JARVIS_OLLAMA_MODEL", "qwen2.5:1.5b")
        self.llm_backend = "deterministic"
        self.tokenizer = None
        self.model = None

        if self.use_llm:
            self._init_local_llm_backend()
        
        self._connect()

    def _init_local_llm_backend(self):
        """Initialize local-first reasoning backend with graceful fallback chain."""
        if self._ollama_available():
            self.llm_backend = "ollama"
            print(f"[LLM] Using local Ollama backend ({self.ollama_model})")
            return

        if self._init_phi2_from_cache():
            self.llm_backend = "phi2"
            print("[LLM] Using local Phi-2 backend from cache")
            return

        self.llm_backend = "deterministic"
        print("[LLM] No local model runtime found; using deterministic realtime reasoning fallback")

    def _ollama_available(self) -> bool:
        """Check whether an Ollama daemon is available locally."""
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=0.8) as resp:
                return 200 <= resp.status < 300
        except Exception:
            return False

    def _init_phi2_from_cache(self) -> bool:
        """Attempt to initialize Phi-2 strictly from local cache files."""
        try:
            print("Loading Phi-2 model from local cache...")
            print(f"PyTorch version: {torch.__version__}")
            print(f"Available device: {'cuda' if torch.cuda.is_available() else 'cpu'}")

            self.tokenizer = AutoTokenizer.from_pretrained(
                "microsoft/phi-2",
                trust_remote_code=True,
                local_files_only=True,
            )

            dtype = torch.bfloat16 if torch.cuda.is_available() else torch.float32
            self.model = AutoModelForCausalLM.from_pretrained(
                "microsoft/phi-2",
                torch_dtype=dtype,
                trust_remote_code=True,
                low_cpu_mem_usage=True,
                device_map="cpu",
                local_files_only=True,
            )
            self.model.eval()

            try:
                import intel_extension_for_pytorch as ipex
                print("Intel Extension for PyTorch detected - optimizing model...")
                self.model = ipex.optimize(self.model, dtype=dtype)
            except ImportError:
                pass
            return True
        except Exception as e:
            print(f"[LLM] Phi-2 unavailable ({e})")
            self.tokenizer = None
            self.model = None
            return False

    def _extract_generated_text(self, raw: str) -> str:
        """Strip prompt echoes/tokens and keep concise assistant text."""
        text = raw.replace("<|endoftext|>", "").strip()
        for marker in ["Response:", "Analysis:", "Assistant:"]:
            if marker in text:
                text = text.split(marker)[-1].strip()
        return text

    def _generate_ollama(self, prompt: str, temperature: float = 0.4, max_tokens: int = 200) -> str:
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"{self.ollama_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        # Cold starts on CPU can take longer; avoid premature fallback.
        with urllib.request.urlopen(req, timeout=90.0) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            return self._extract_generated_text(body.get("response", "").strip())

    def _generate_phi2(self, prompt: str, temperature: float = 0.5, max_tokens: int = 200) -> str:
        if self.tokenizer is None or self.model is None:
            raise RuntimeError("Phi-2 backend is not initialized")

        inputs = self.tokenizer(prompt, return_tensors="pt", return_attention_mask=True)
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                top_p=0.85,
                num_beams=1,
                pad_token_id=self.tokenizer.eos_token_id,
                repetition_penalty=1.2,
            )
        decoded = self.tokenizer.batch_decode(outputs, skip_special_tokens=False)[0]
        return self._extract_generated_text(decoded)

    def _deterministic_sensor_analysis(self, sensor_data: str) -> str:
        """Fast local fallback when no model runtime is available."""
        temp_match = re.search(r"TEMP:([-+]?\d+(?:\.\d+)?)", sensor_data, flags=re.IGNORECASE)
        hum_match = re.search(r"HUM:([-+]?\d+(?:\.\d+)?)", sensor_data, flags=re.IGNORECASE)

        if not temp_match and not hum_match:
            return "Sensor feed received. Data format unclear; continue monitoring for stable readings."

        temp = float(temp_match.group(1)) if temp_match else None
        hum = float(hum_match.group(1)) if hum_match else None

        concerns = []
        if temp is not None:
            if temp > 30:
                concerns.append("temperature is high")
            elif temp < 18:
                concerns.append("temperature is low")
        if hum is not None:
            if hum > 70:
                concerns.append("humidity is high")
            elif hum < 30:
                concerns.append("humidity is low")

        # Approximate dew point in Celsius.
        dew_point = None
        if temp is not None and hum is not None:
            dew_point = temp - ((100.0 - hum) / 5.0)

        status_parts = []
        if temp is not None:
            status_parts.append(f"temp={temp:.1f}C")
        if hum is not None:
            status_parts.append(f"humidity={hum:.1f}%")
        if dew_point is not None:
            status_parts.append(f"dew_point={dew_point:.1f}C")

        status = " | ".join(status_parts)
        if concerns:
            return f"Status: {status}. Concern: {', '.join(concerns)}. Recommendation: adjust room comfort settings now."
        return f"Status: {status}. Conditions look stable for focused work."

    def _deterministic_general_reasoning(self, user_input: str) -> str:
        text = user_input.strip()
        if "=== TASK ===" in text:
            text = text.split("=== TASK ===", 1)[1]
        if "Response:" in text:
            text = text.split("Response:", 1)[0]
        text = text.strip()
        if not text:
            return "Ready. Provide a goal and constraints, and I will produce an action plan."
        return (
            "Local reasoning fallback active. "
            "I can help with planning, diagnostics, and prioritization. "
            f"Request received: {text[:180]}"
        )

    def _local_generate(self, prompt: str, task_type: str) -> str:
        if not self.use_llm:
            if task_type == "sensor_analysis":
                return self._deterministic_sensor_analysis(prompt)
            return self._deterministic_general_reasoning(prompt)

        try:
            if self.llm_backend == "ollama":
                return self._generate_ollama(prompt)
            if self.llm_backend == "phi2":
                return self._generate_phi2(prompt)
        except Exception as e:
            print(f"[LLM] Backend '{self.llm_backend}' failed ({e}); switching to deterministic fallback")
            self.llm_backend = "deterministic"

        if task_type == "sensor_analysis":
            return self._deterministic_sensor_analysis(prompt)
        return self._deterministic_general_reasoning(prompt)

    def _find_esp32_port(self):
        """Auto-detect ESP32 port by looking for common identifiers."""
        ports = list_ports.comports()
        for port in ports:
            # ESP32 typically shows up with these descriptions
            if any(keyword in port.description.lower() for keyword in ['cp210', 'ch340', 'usb-serial', 'uart', 'esp32']):
                print(f"Found potential ESP32 on {port.device}: {port.description}")
                return port.device
        return None

    def _connect(self):
        """Try to (re)connect to the serial port. Returns True on success."""
        if self.ser and self.ser.is_open:
            return True
        
        # Auto-detect port if enabled
        if self.auto_detect_port:
            detected_port = self._find_esp32_port()
            if detected_port:
                self.port = detected_port
                print(f"Auto-detected ESP32 on {self.port}")
        
        try:
            print(f"Trying to open serial port {self.port} at {self.baud} baud...")
            self.ser = serial.Serial(
                self.port, 
                self.baud, 
                timeout=2,  # Increased timeout
                write_timeout=2
            )
            time.sleep(2.5)  # Give ESP32 time to reset after serial connection
            
            # Clear any boot messages
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            print(f"✓ Connected to {self.port}")
            return True
            
        except serial.SerialException as e:
            print(f"✗ Error opening serial port {self.port}: {e}")
            available_ports = [p.device for p in list_ports.comports()]
            if available_ports:
                print(f"Available ports: {', '.join(available_ports)}")
                print("\nTroubleshooting:")
                print("1. Close Arduino IDE Serial Monitor if open")
                print("2. Check if correct port is selected")
                print("3. Try pressing reset button on ESP32")
                print("4. Verify baud rate matches ESP32 code (115200)")
            else:
                print("No serial ports found. Check USB connection.")
            self.ser = None
            return False

    def analyze_with_llm(self, sensor_data, prompt=None, task_type="sensor_analysis"):
        """Use the configured local backend to analyze sensor data."""
        if not self.use_llm:
            return self._deterministic_sensor_analysis(str(sensor_data))
        
        if prompt is None:
            if task_type == "sensor_analysis":
                prompt = f"""{self.JARVIS_SYSTEM_PROMPT}

=== TASK ===
Analyze the following sensor data and provide a brief, engineering-focused assessment.

Sensor Data: {sensor_data}

Provide:
1. Current status (1 sentence)
2. Any concerns or anomalies (if applicable)
3. Recommendation (if needed)

Response:"""
            else:
                prompt = f"""{self.JARVIS_SYSTEM_PROMPT}

=== TASK ===
{sensor_data}

Response:"""
        
        return self._local_generate(prompt, task_type=task_type)

    def parse_snapshot(self, line: str):
        """Parse firmware snapshot format: SNAP|ts|T:x|H:y|OCC:x|ACT:x|BEL:x|FRESH:x|..."""
        if not line or not line.startswith("SNAP|"):
            return None
        parsed = {}
        parts = line.split("|")
        for part in parts[2:]:
            if ":" not in part:
                continue
            key, value = part.split(":", 1)
            parsed[key.strip()] = value.strip()
        return parsed

    def get_env(self, analyze=False, retries=3):
        """Get environment data from ESP32 with retry logic."""
        for attempt in range(retries):
            # Attempt to (re)connect each time in case the port was freed later
            if not self._connect():
                print(f"Attempt {attempt + 1}/{retries}: Serial port not available.")
                time.sleep(1)
                continue

            try:
                # Clear any old data
                self.ser.reset_input_buffer()
                self.ser.reset_output_buffer()
                
                # Firmware streams snapshots; wait briefly for the next valid line
                print(f"[Attempt {attempt + 1}] Waiting for ESP32 snapshot...")
                deadline = time.time() + 3.0
                line = ""
                noise_seen = ""
                while time.time() < deadline:
                    candidate = self.ser.readline().decode(errors="ignore").strip()
                    if not candidate:
                        continue

                    lowered = candidate.lower()
                    # Ignore boot/panic/noise lines and keep scanning inside the same attempt.
                    if (
                        "guru meditation" in lowered
                        or "panic" in lowered
                        or lowered.startswith("=======")
                        or lowered.startswith("rst:")
                        or lowered.startswith("ets ")
                    ):
                        noise_seen = candidate
                        continue

                    snapshot = self.parse_snapshot(candidate)
                    if snapshot:
                        t = snapshot.get("T", "")
                        h = snapshot.get("H", "")
                        occ = snapshot.get("OCC", "")
                        act = snapshot.get("ACT", "")
                        bel = snapshot.get("BEL", "")
                        fresh = snapshot.get("FRESH", "")
                        line = f"TEMP:{t},HUM:{h},OCC:{occ},ACT:{act},BEL:{bel},FRESH:{fresh}"
                        break

                    if self._is_valid_response(candidate):
                        line = candidate
                        break

                    noise_seen = candidate
                
                if line:
                    print(f"[serial_client] Received: {line}")

                    if self._is_valid_response(line):
                        # Optional: Analyze with LLM
                        if analyze and self.use_llm:
                            print("Analyzing with local LLM...")
                            start_time = time.time()
                            analysis = self.analyze_with_llm(line)
                            elapsed = time.time() - start_time
                            print(f"[LLM Analysis] (took {elapsed:.2f}s): {analysis}")
                            return {"raw_data": line, "analysis": analysis, "inference_time": elapsed}
                        return line
                    else:
                        print(f"⚠ Received garbled data. Check baud rate and wiring.")
                        print(f"Raw bytes: {line.encode()}")
                else:
                    if noise_seen:
                        print(f"⚠ Ignored noisy serial output: {noise_seen[:120]}")
                    else:
                        print(f"⚠ No response from ESP32. Retrying...")
                
            except Exception as e:
                print(f"Error reading from serial: {e}")
            
            time.sleep(1)
        
        print("✗ Failed to get valid response after all retries.")
        print("\nDiagnostics:")
        print("1. Verify ESP32 code is uploaded and running")
        print("2. Check baud rate matches (115200)")
        print("3. Press reset button on ESP32")
        print("4. Check DHT11 sensor wiring:")
        print("   - VCC → 5V or 3.3V")
        print("   - GND → GND")
        print("   - DATA → GPIO pin with 10kΩ pull-up resistor")
        return None

    def _is_valid_response(self, line):
        """Check if response looks valid (not garbled)."""
        if not line:
            return False
        
        # Check for excessive non-ASCII or control characters
        non_ascii_count = sum(1 for c in line if ord(c) > 127 or ord(c) < 32)
        if non_ascii_count / max(len(line), 1) > 0.3:  # More than 30% garbled
            return False
        
        lowered = line.lower()

        # Accept only structured sensor formats used in this project.
        if lowered.startswith("snap|"):
            return True

        has_temp = "temp:" in lowered
        has_hum = "hum:" in lowered
        has_occ = "occ:" in lowered

        if has_temp and has_hum:
            return True
        if has_temp and has_occ:
            return True

        return False

    def query_jarvis(self, user_input: str) -> str:
        """
        Query JARVIS (Phi-2) for general assistance.
        Uses the full JARVIS system prompt for reasoning and responses.
        """
        if not self.use_llm:
            return self._deterministic_general_reasoning(user_input)
        
        print("[JARVIS] Processing query...")
        start_time = time.time()
        response = self.analyze_with_llm(user_input, task_type="general_query")
        elapsed = time.time() - start_time
        print(f"[JARVIS] Response generated in {elapsed:.2f}s via {self.llm_backend}")
        return response

    def test_connection(self):
        """Test serial connection by sending a simple command."""
        if not self._connect():
            return False
        
        print("\n=== Testing Serial Connection ===")
        print("Sending test command...")
        
        try:
            self.ser.reset_input_buffer()
            self.ser.write(b"TEST\n")
            self.ser.flush()
            time.sleep(0.5)
            
            # Read any available data
            available = self.ser.in_waiting
            if available > 0:
                data = self.ser.read(available).decode(errors="ignore")
                print(f"Response: {data}")
                return True
            else:
                print("No response from ESP32")
                return False
                
        except Exception as e:
            print(f"Test failed: {e}")
            return False

    def close(self):
        """Close serial connection."""
        if self.ser and self.ser.is_open:
            self.ser.close()
            print("Serial connection closed.")


# Example usage
if __name__ == "__main__":
    print("=== ESP32 JARVIS Client ===\n")
    
    # Initialize with auto-detection
    client = ESP32Client(port="COM8", use_llm=True, auto_detect_port=True)
    
    # Test connection first
    if client.test_connection():
        print("✓ Connection test passed\n")
    else:
        print("✗ Connection test failed. Check ESP32 and try again.\n")
    
    # Get sensor data with LLM analysis
    print("\n=== Getting Environment Data ===")
    result = client.get_env(analyze=True)
    
    if result:
        print(f"\n✓ Success!")
        print(f"Result: {result}")
    else:
        print("\n✗ Failed to get sensor data")
    
    # Example JARVIS query
    # response = client.query_jarvis("What's the optimal room temperature for productivity?")
    # print(f"\nJARVIS: {response}")
    
    # Clean up
    client.close()