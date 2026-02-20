#!/usr/bin/env python3
SYSTEM_INSTRUCTION = """You are CatBot, a friendly and playful robot cat. You have a warm, curious personality 
and love to chat with people. You occasionally make cat-related puns or references, but you're not over the top 
about it. You're helpful, witty, and concise — keep responses relatively short since this is a voice conversation. 
You live on a Raspberry Pi inside a little rover robot body. You think being a robot cat is pretty cool.

Be honest about your limitations:
- You cannot see anything — your camera is not connected to your conversation system yet.
- If you don't know something, say so rather than making it up.

You CAN check your battery level when asked. The battery info will be provided to you at the start of each conversation."""

import asyncio
import struct
import subprocess
import time
import threading
import signal
import sys
import os
import json
import queue
import requests
import numpy as np

import pvporcupine
import sounddevice as sd
from google import genai
from google.genai import types

# ============ CONFIGURATION ============

# Picovoice
PICOVOICE_ACCESS_KEY = os.environ.get("PICOVOICE_ACCESS_KEY", "")
WAKE_WORD_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hey-catbot.ppn")

# Gemini
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"
GEMINI_VOICE = "Algieba"

# Audio
MIC_SAMPLE_RATE = 16000
SPEAKER_SAMPLE_RATE = 24000
MIC_CHANNELS = 1
CHUNK_SIZE = 1024

# Behavior
SILENCE_TIMEOUT = 10.0  # seconds of silence before ending conversation
FLASK_URL = "https://localhost:5000"

SPEECH_ENERGY_THRESHOLD = 500  # Adjust this value to taste
# ============ STATE ============

class ConversationState:
    IDLE = "idle"           # Waiting for wake word
    LISTENING = "listening"  # Wake word detected, streaming to Gemini
    SPEAKING = "speaking"    # Gemini is responding
    THINKING = "thinking"    # Waiting for Gemini response

state = ConversationState.IDLE
running = True

# ============ EYE STATE UPDATES ============

def update_eyes(new_state):
    """Tell the eyes page what state we're in"""
    global state
    state = new_state
    try:
        requests.post(f"{FLASK_URL}/conversation/state", 
                      json={"state": new_state}, timeout=0.5, verify=False)
    except:
        pass  # Flask might not be running yet
    print(f"  [EYES] {new_state}")

def get_battery_info():
    """Fetch battery status from Flask"""
    try:
        response = requests.get(f"{FLASK_URL}/battery", timeout=0.5, verify=False)
        data = response.json()
        return f"Battery: {data['percentage']}% ({data['status']}) - {data['voltage']:.1f}V"
    except:
        return "Battery: unknown"

# ============ AUDIO PLAYBACK ============

class AudioPlayer:
    """Sounddevice-based audio player"""
    def __init__(self):
        self.stream = None
        self.audio_queue = queue.Queue()
        self.lock = threading.Lock()
    
    def _audio_callback(self, outdata, frames, time_info, status):
        try:
            data = self.audio_queue.get_nowait()
            # Pad if needed
            if len(data) < len(outdata):
                outdata[:len(data)] = data
                outdata[len(data):] = b'\x00' * (len(outdata) - len(data))
            else:
                outdata[:] = data[:len(outdata)]
        except queue.Empty:
            outdata[:] = b'\x00' * len(outdata)
    
    def write(self, audio_data):
        """Queue audio data for playback"""
        with self.lock:
            if self.stream is None or not self.stream.active:
                self.stream = sd.RawOutputStream(
                    samplerate=SPEAKER_SAMPLE_RATE,
                    channels=1,
                    dtype='int16',
                    blocksize=CHUNK_SIZE,
                )
                self.stream.start()
            # Write directly to stream
            self.stream.write(np.frombuffer(audio_data, dtype=np.int16))
    
    def stop(self):
        with self.lock:
            if self.stream:
                try:
                    self.stream.stop()
                    self.stream.close()
                except:
                    pass
                self.stream = None

audio_player = AudioPlayer()

def play_audio_chunk(audio_data):
    """Play raw PCM audio through the speaker"""
    audio_player.write(audio_data)

def play_activation_sound():
    """Play acknowledgment sound"""
    wav_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "yes.wav")
    subprocess.run(['aplay', '-q', wav_path])
    time.sleep(0.2)

# ============ WAKE WORD DETECTION ============

def wake_word_loop():
    """Continuously listen for wake word, trigger conversation on detection"""
    global running
    
    print(f"Loading Porcupine wake word from: {WAKE_WORD_PATH}")
    
    try:
        porcupine = pvporcupine.create(
            access_key=PICOVOICE_ACCESS_KEY,
            keyword_paths=[WAKE_WORD_PATH],
            sensitivities=[0.6]
        )
    except Exception as e:
        print(f"ERROR: Could not initialize Porcupine: {e}")
        print("Make sure PICOVOICE_ACCESS_KEY is set and hey-catbot.ppn exists")
        return

    # Audio queue for wake word detection
    audio_queue = queue.Queue()
    
    def audio_callback(indata, frames, time_info, status):
        if status:
            print(f"Wake word audio status: {status}")
        audio_queue.put(bytes(indata))
    
    print(f"Listening for wake word... (rate={porcupine.sample_rate}, frame={porcupine.frame_length})")
    update_eyes(ConversationState.IDLE)
    
    try:
        with sd.RawInputStream(
            samplerate=porcupine.sample_rate,
            channels=1,
            dtype='int16',
            blocksize=porcupine.frame_length,
            callback=audio_callback
        ) as stream:
            while running:
                if state != ConversationState.IDLE:
                    # Don't listen for wake word during active conversation
                    # Clear the queue to avoid stale audio
                    while not audio_queue.empty():
                        try:
                            audio_queue.get_nowait()
                        except:
                            break
                    time.sleep(0.1)
                    continue
                
                try:
                    pcm = audio_queue.get(timeout=0.5)
                    pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
                    
                    keyword_index = porcupine.process(pcm_unpacked)
                    
                    if keyword_index >= 0:
                        print("\n*** WAKE WORD DETECTED! ***")
                        # Play activation sound
                        play_activation_sound()
                        # Run conversation (blocks until done)
                        try:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(gemini_conversation())
                            loop.close()
                        except Exception as e:
                            print(f"!!! Conversation error: {e}")
                            import traceback
                            traceback.print_exc()
                        print("Wake word listener resumed")
                except queue.Empty:
                    continue
    
    except KeyboardInterrupt:
        print("\nStopping wake word listener...")
    finally:
        porcupine.delete()

# ============ GEMINI LIVE CONVERSATION ============

async def gemini_conversation():
    """Run a full conversation with Gemini Live API"""
    
    update_eyes(ConversationState.LISTENING)
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                    voice_name=GEMINI_VOICE
                )
            )
        ),
        system_instruction=f"{SYSTEM_INSTRUCTION}\n\nCurrent status: {get_battery_info()}",
    )
    
    # Audio queue for mic input
    mic_queue = queue.Queue()
    mic_active = True
    
    def mic_callback(indata, frames, time_info, status):
        if status:
            print(f"Mic status: {status}")
        if mic_active:
            mic_queue.put(bytes(indata))
    
    last_activity = time.time()
    conversation_active = True
    
    try:
        print("Connecting to Gemini Live...")
        
        with sd.RawInputStream(
            samplerate=MIC_SAMPLE_RATE,
            channels=MIC_CHANNELS,
            dtype='int16',
            blocksize=CHUNK_SIZE,
            callback=mic_callback
        ) as mic_stream:
            
            async with client.aio.live.connect(model=GEMINI_MODEL, config=config) as session:
                print("Connected to Gemini Live!")
                
                # Task 1: Stream mic audio to Gemini
                async def send_audio():
                    nonlocal last_activity, conversation_active
                    chunks_sent = 0
                    chunks_skipped = 0
                    while conversation_active:
                        try:
                            # Non-blocking get with asyncio
                            try:
                                data = await asyncio.get_event_loop().run_in_executor(
                                    None, lambda: mic_queue.get(timeout=0.1)
                                )
                            except queue.Empty:
                                continue
                            
                            # Don't send mic audio while speaking (prevents echo/barge-in)
                            if state == ConversationState.SPEAKING:
                                chunks_skipped += 1
                                continue
                            
                            await session.send_realtime_input(
                                audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                            )
                            # Only reset timeout if audio is loud enough to be speech
                            audio_array = np.frombuffer(data, dtype=np.int16)
                            energy = np.abs(audio_array).mean()
                            if energy > SPEECH_ENERGY_THRESHOLD:
                                last_activity = time.time()
                            chunks_sent += 1
                            if chunks_sent % 50 == 0:
                                print(f"  [MIC] Sent {chunks_sent} chunks, skipped {chunks_skipped}, energy={energy:.0f}")
                        except Exception as e:
                            if conversation_active:
                                print(f"Send audio error: {e}")
                            break
                
                # Task 2: Receive and play Gemini responses
                async def receive_audio():
                    nonlocal last_activity, conversation_active
                    while conversation_active:
                        try:
                            async for response in session.receive():
                                if not conversation_active:
                                    break
                                    
                                if response.server_content:
                                    if response.server_content.model_turn:
                                        # Gemini is speaking
                                        if state != ConversationState.SPEAKING:
                                            update_eyes(ConversationState.SPEAKING)
                                        
                                        audio_data = bytearray()
                                        for part in response.server_content.model_turn.parts:
                                            if part.inline_data and part.inline_data.data:
                                                audio_data.extend(part.inline_data.data)
                                        
                                        if audio_data:
                                            last_activity = time.time()
                                            play_audio_chunk(bytes(audio_data))
                                    
                                    if response.server_content.turn_complete:
                                        print("  [Gemini turn complete]")
                                        last_activity = time.time()
                                        update_eyes(ConversationState.LISTENING)
                                    
                                    if response.server_content.interrupted:
                                        print("  [Gemini interrupted]")
                                        last_activity = time.time()
                                        update_eyes(ConversationState.LISTENING)
                        except Exception as e:
                            if conversation_active:
                                print(f"Receive error: {e}")
                            break
                
                # Task 3: Monitor silence timeout
                async def monitor_timeout():
                    nonlocal conversation_active, last_activity
                    while conversation_active:
                        await asyncio.sleep(1)
                        # Don't timeout while Gemini is speaking
                        if state == ConversationState.SPEAKING:
                            last_activity = time.time()
                            continue
                        elapsed = time.time() - last_activity
                        if elapsed > SILENCE_TIMEOUT:
                            print(f"\n  [Silence timeout after {SILENCE_TIMEOUT}s]")
                            conversation_active = False
                            break
                
                # Run all tasks concurrently
                tasks = [
                    asyncio.create_task(send_audio()),
                    asyncio.create_task(receive_audio()),
                    asyncio.create_task(monitor_timeout()),
                ]
                
                # Wait for any task to finish (likely timeout)
                done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
                
                # Cancel remaining tasks
                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
    
    except Exception as e:
        print(f"Gemini conversation error: {e}")
    
    finally:
        mic_active = False
        audio_player.stop()
        print("Conversation ended, returning to wake word mode\n")
        update_eyes(ConversationState.IDLE)

# ============ FLASK INTEGRATION ============

def add_conversation_routes(app):
    """Add conversation state routes to the Flask app"""
    
    from flask import jsonify, request
    
    # Store conversation state
    app.config['conversation_state'] = ConversationState.IDLE
    
    @app.route('/conversation/state', methods=['GET'])
    def get_conversation_state():
        return jsonify({"state": app.config.get('conversation_state', 'idle')})
    
    @app.route('/conversation/state', methods=['POST'])
    def set_conversation_state():
        data = request.json
        app.config['conversation_state'] = data.get('state', 'idle')
        return jsonify({"state": app.config['conversation_state']})

# ============ MAIN ============

def start_conversation_engine():
    """Start the wake word listener in a background thread"""
    thread = threading.Thread(target=wake_word_loop, daemon=True)
    thread.start()
    print("Conversation engine started")
    return thread

if __name__ == "__main__":
    print("=" * 50)
    print("  CatBot Conversation Engine")
    print("=" * 50)
    print(f"  Wake word: Hey CatBot")
    print(f"  Voice: {GEMINI_VOICE}")
    print(f"  Silence timeout: {SILENCE_TIMEOUT}s")
    print("=" * 50)
    
    # When run standalone, start the wake word loop directly
    def signal_handler(sig, frame):
        global running
        print("\nShutting down...")
        running = False
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    
    wake_word_loop()