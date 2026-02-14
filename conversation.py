#!/usr/bin/env python3
"""
CatBot Conversation Engine
- Porcupine wake word detection ("Hey CatBot")
- Gemini Live API for real-time voice conversation
- Eye state updates via Flask endpoint
- Silence timeout returns to idle
"""

import asyncio
import struct
import subprocess
import time
import threading
import signal
import sys
import os
import json
import requests

import pvporcupine
import pyaudio
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
SILENCE_TIMEOUT = 5.0  # seconds of silence before ending conversation
FLASK_URL = "http://localhost:5000"

# CatBot personality
SYSTEM_INSTRUCTION = """You are CatBot, a friendly and playful robot cat. You have a warm, curious personality 
and love to chat with people. You occasionally make cat-related puns or references, but you're not over the top 
about it. You're helpful, witty, and concise — keep responses relatively short since this is a voice conversation. 
You can see through your camera and hear through your microphone. You live on a Raspberry Pi inside a little 
rover robot body. You think being a robot cat is pretty cool."""

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
                      json={"state": new_state}, timeout=0.5)
    except:
        pass  # Flask might not be running yet
    print(f"  [EYES] {new_state}")

# ============ AUDIO PLAYBACK ============

class AudioPlayer:
    """Persistent paplay process for smooth audio streaming"""
    def __init__(self):
        self.proc = None
    
    def ensure_running(self):
        if self.proc is None or self.proc.poll() is not None:
            self.proc = subprocess.Popen(
                ['paplay', '--format=s16le', f'--rate={SPEAKER_SAMPLE_RATE}',
                 '--channels=1', '--raw'],
                stdin=subprocess.PIPE
            )
    
    def write(self, audio_data):
        try:
            self.ensure_running()
            self.proc.stdin.write(audio_data)
            self.proc.stdin.flush()
        except BrokenPipeError:
            self.proc = None
            self.ensure_running()
            self.proc.stdin.write(audio_data)
            self.proc.stdin.flush()
    
    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                self.proc.stdin.close()
                self.proc.wait(timeout=1)
            except:
                self.proc.kill()
            self.proc = None

audio_player = AudioPlayer()

def play_audio_chunk(audio_data):
    """Play raw PCM audio through the Bluetooth speaker"""
    audio_player.write(audio_data)

def play_activation_sound():
    """Play a short beep to indicate wake word detected"""
    # Generate a short 440Hz beep
    duration = 0.15
    samples = int(SPEAKER_SAMPLE_RATE * duration)
    import math
    audio = bytes()
    for i in range(samples):
        value = int(16000 * math.sin(2 * math.pi * 880 * i / SPEAKER_SAMPLE_RATE))
        audio += struct.pack('<h', value)
    play_audio_chunk(audio)

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

    pa = pyaudio.PyAudio()
    
    mic_stream = pa.open(
        format=pyaudio.paInt16,
        channels=1,
        rate=porcupine.sample_rate,
        input=True,
        frames_per_buffer=porcupine.frame_length
    )
    
    print(f"Listening for wake word... (rate={porcupine.sample_rate}, frame={porcupine.frame_length})")
    update_eyes(ConversationState.IDLE)
    
    try:
        while running:
            if state != ConversationState.IDLE:
                # Don't listen for wake word during active conversation
                time.sleep(0.1)
                continue
                
            pcm = mic_stream.read(porcupine.frame_length, exception_on_overflow=False)
            pcm_unpacked = struct.unpack_from("h" * porcupine.frame_length, pcm)
            
            keyword_index = porcupine.process(pcm_unpacked)
            
            if keyword_index >= 0:
                print("\n*** WAKE WORD DETECTED! ***")
                # Close wake word mic before starting conversation
                mic_stream.close()
                pa.terminate()
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
                # Re-open mic for wake word detection
                pa = pyaudio.PyAudio()
                mic_stream = pa.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=porcupine.sample_rate,
                    input=True,
                    frames_per_buffer=porcupine.frame_length
                )
                print("Wake word listener resumed")
    
    except KeyboardInterrupt:
        print("\nStopping wake word listener...")
    finally:
        mic_stream.close()
        pa.terminate()
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
        system_instruction=SYSTEM_INSTRUCTION,
    )
    
    pa = pyaudio.PyAudio()
    mic_stream = pa.open(
        format=pyaudio.paInt16,
        channels=MIC_CHANNELS,
        rate=MIC_SAMPLE_RATE,
        input=True,
        frames_per_buffer=CHUNK_SIZE
    )
    
    last_activity = time.time()
    conversation_active = True
    
    try:
        print("Connecting to Gemini Live...")
        async with client.aio.live.connect(model=GEMINI_MODEL, config=config) as session:
            print("Connected to Gemini Live!")
            
            # Task 1: Stream mic audio to Gemini
            async def send_audio():
                nonlocal last_activity, conversation_active
                while conversation_active:
                    try:
                        data = await asyncio.to_thread(
                            mic_stream.read, CHUNK_SIZE,
                        )
                        # Don't send mic audio while speaking (prevents echo/barge-in)
                        if state == ConversationState.SPEAKING:
                            continue
                        await session.send_realtime_input(
                            audio=types.Blob(data=data, mime_type="audio/pcm;rate=16000")
                        )
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
        mic_stream.close()
        pa.terminate()
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
