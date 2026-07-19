import speech_recognition as sr
import pyttsx3
import threading
import numpy as np
from pyrnnoise import RNNoise
from serial_client import ESP32Client
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

# ============ INIT ============
recognizer = sr.Recognizer()
esp = ESP32Client(port="COM3", use_llm=True)  # Enable Phi-2 LLM integration

# Initialize RNNoise with 48kHz
try:
    denoiser = RNNoise(sample_rate=48000)
    print("[RNNoise] Initialized successfully")
except Exception as e:
    print(f"[RNNoise] Init Failed: {e}. Running without noise reduction.")
    denoiser = None

def denoise_audio(raw_data):
    """
    Enhanced version with proper None-checking and error handling.
    Returns cleaned audio and average speech probability.
    """
    if denoiser is None:
        return raw_data, 0.0

    try:
        # Convert to 16-bit numpy array and ensure contiguous memory
        audio_np = np.frombuffer(raw_data, dtype=np.int16).copy()
        
        # RNNoise requires frames of exactly 480 samples
        frame_size = 480
        num_samples = len(audio_np)
        
        # Pad to multiple of 480 if needed
        remainder = num_samples % frame_size
        if remainder > 0:
            padding_size = frame_size - remainder
            audio_np = np.pad(audio_np, (0, padding_size), mode='constant', constant_values=0)

        cleaned_chunks = []
        total_speech_prob = 0.0
        num_frames = 0

        # Process each 480-sample frame
        for i in range(0, len(audio_np), frame_size):
            frame = audio_np[i : i + frame_size]
            
            # Skip if frame is wrong size (shouldn't happen after padding)
            if len(frame) != frame_size:
                continue

            try:
                # Try standard API first
                result = denoiser.denoise_frame(frame)
                
                # CRITICAL FIX: Check if result is None before unpacking
                if result is None:
                    # If denoising fails, use original frame
                    cleaned_chunks.append(frame)
                    continue
                
                # Unpack only if we got a valid result
                speech_prob, denoised_frame = result
                
            except AttributeError:
                # Try byte-based API
                try:
                    result = denoiser.process_frame(frame.tobytes())
                    
                    # CRITICAL FIX: Check for None here too
                    if result is None:
                        cleaned_chunks.append(frame)
                        continue
                    
                    speech_prob, denoised_frame = result
                    
                except Exception as e:
                    # If both APIs fail, use original frame
                    cleaned_chunks.append(frame)
                    continue
                    
            except Exception as e:
                # Any other error - use original frame
                cleaned_chunks.append(frame)
                continue

            # Convert denoised frame to numpy array
            if denoised_frame is not None:
                if isinstance(denoised_frame, (bytes, bytearray)):
                    d_np = np.frombuffer(denoised_frame, dtype=np.int16)
                else:
                    d_np = np.asarray(denoised_frame, dtype=np.int16)
                
                cleaned_chunks.append(d_np)
                total_speech_prob += float(speech_prob)
                num_frames += 1
            else:
                # If denoised_frame is None, use original
                cleaned_chunks.append(frame)

        # Reconstruct audio
        if not cleaned_chunks:
            return raw_data, 0.0

        cleaned_audio = np.concatenate(cleaned_chunks).astype(np.int16).tobytes()
        avg_prob = total_speech_prob / num_frames if num_frames > 0 else 0.0
        
        # Only print if we have meaningful data
        if num_frames > 0:
            print(f"[DSP] Speech Probability: {avg_prob:.2%} ({num_frames} frames processed)")
        
        return cleaned_audio, avg_prob
        
    except Exception as e:
        print(f"[DSP] Error during denoising: {e}. Using original audio.")
        return raw_data, 0.0

# Load FLAN-T5 for AI responses
FLAN_MODEL_NAME = "google/flan-t5-small"
print("[AI] Loading FLAN-T5 model...")
tokenizer = AutoTokenizer.from_pretrained(FLAN_MODEL_NAME)
model = AutoModelForSeq2SeqLM.from_pretrained(FLAN_MODEL_NAME)
print("[AI] Model loaded successfully")

def flan_generate(user_input: str) -> str:
    """Generate AI response with JARVIS personality."""
    prompt = (
        "You are JARVIS, a polite and intelligent AI assistant. "
        "Respond in one brief, professional sentence.\n\n"
        f"User: {user_input}\n"
        "JARVIS:"
    )
    inputs = tokenizer(prompt, return_tensors="pt")
    outputs = model.generate(
        **inputs, 
        max_new_tokens=50, 
        do_sample=True, 
        temperature=0.7,
        repetition_penalty=1.2
    )
    response = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    return response.replace("JARVIS:", "").strip()

def speak(text):
    """Thread-safe text-to-speech function."""
    print(f"JARVIS: {text}")
    
    def _speak():
        try:
            engine = pyttsx3.init(driverName="sapi5")
            engine.setProperty("rate", 170)
            engine.setProperty("volume", 1.0)
            engine.say(text)
            engine.runAndWait()
            engine.stop()
        except Exception as e:
            print(f"[TTS] Error: {e}")
    
    thread = threading.Thread(target=_speak, daemon=True)
    thread.start()
    thread.join(timeout=10)

# ============ MAIN LOOP ============
print("="*50)
print("JARVIS VOICE ASSISTANT")
print("- Noise Reduction: ENABLED" if denoiser else "- Noise Reduction: DISABLED")
print("- AI Model: Phi-2 (Local LLM) + FLAN-T5")
print("- ESP32 Integration: Active with AI Analysis")
print("="*50)

speak("JARVIS systems online. Local AI powered by Phi-2. All systems ready.")

try:
    with sr.Microphone(sample_rate=48000) as source:
        recognizer.adjust_for_ambient_noise(source, duration=1)
        print("[System] Calibration complete. Ready for commands.\n")
        
        while True:
            try:
                print("[Listening...]")
                
                # Capture audio with timeout
                audio_captured = recognizer.listen(source, phrase_time_limit=5, timeout=10)
                raw_bytes = audio_captured.get_raw_data()

                # Apply noise reduction if available
                clean_bytes, speech_prob = denoise_audio(raw_bytes)
                
                # Create cleaned audio object for recognition
                clean_audio = sr.AudioData(clean_bytes, 48000, 2)

                # Recognize speech
                text = recognizer.recognize_google(clean_audio)
                print(f"You: {text}")
                
                text_lower = text.lower()

                # Command routing
                if "temperature" in text_lower or "humidity" in text_lower or "sensor" in text_lower or "environment" in text_lower:
                    print("[ESP32] Fetching environmental data with AI analysis...")
                    data = esp.get_env(analyze=True)  # Get sensor data + Phi-2 analysis
                    
                    if isinstance(data, dict) and "analysis" in data:
                        # We have AI analysis from Phi-2
                        response = data["analysis"]
                        print(f"[Phi-2 Analysis]: {response}")
                    elif isinstance(data, str) and "TEMP:" in data and "HUM:" in data:
                        # Fallback: parse raw sensor data
                        try:
                            temp = data.split("TEMP:")[1].split(",")[0].strip()
                            hum = data.split("HUM:")[1].strip()
                            response = f"Current temperature is {temp} degrees Celsius, humidity at {hum} percent."
                        except Exception as e:
                            print(f"[ESP32] Parse error: {e}")
                            response = "I received sensor data but could not parse it properly."
                    else:
                        response = "I'm unable to access the environmental sensors at the moment."
                
                elif any(word in text_lower for word in ["exit", "quit", "stop", "shutdown"]):
                    response = "Understood. Shutting down all systems. Goodbye."
                    speak(response)
                    break
                    
                else:
                    # Use Phi-2 (JARVIS) for general queries
                    print("[AI] JARVIS analyzing request...")
                    response = esp.query_jarvis(text)
                    
                    if response:
                        print(f"[JARVIS]: {response}")
                    else:
                        # Fallback to FLAN-T5 if Phi-2 fails
                        print("[AI] Falling back to FLAN-T5...")
                        response = flan_generate(text)

                speak(response)

            except sr.WaitTimeoutError:
                # Timeout - just continue listening
                continue
                
            except sr.UnknownValueError:
                # Speech not understood - continue silently
                print("[Recognition] Could not understand audio")
                continue
                
            except KeyboardInterrupt:
                print("\n[System] Interrupted by user")
                speak("Shutting down.")
                break
                
            except Exception as e:
                print(f"[Error] {type(e).__name__}: {e}")
                # Continue running despite errors
                continue

except Exception as e:
    print(f"[Fatal Error] {e}")
finally:
    print("\n[System] JARVIS terminated.")
    if denoiser:
        try:
            denoiser.close()
        except:
            pass