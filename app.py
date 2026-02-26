# import base_ctrl library
from base_ctrl import BaseController
from conversation import add_conversation_routes, start_conversation_engine
import threading
import yaml, os

# raspberry pi version check.
def is_raspberry_pi5():
    with open('/proc/cpuinfo', 'r') as file:
        for line in file:
            if 'Model' in line:
                if 'Raspberry Pi 5' in line:
                    return True
                else:
                    return False

if is_raspberry_pi5():
    base = BaseController('/dev/ttyAMA0', 115200)
else:
    base = BaseController('/dev/serial0', 115200)

threading.Thread(target=lambda: base.breath_light(15), daemon=True).start()

# config file.
curpath = os.path.realpath(__file__)
thisPath = os.path.dirname(curpath)
with open(thisPath + '/config.yaml', 'r') as yaml_file:
    f = yaml.safe_load(yaml_file)

base.base_oled(0, f["base_config"]["robot_name"])
base.base_oled(1, f"sbc_version: {f['base_config']['sbc_version']}")
base.base_oled(2, f"{f['base_config']['main_type']}{f['base_config']['module_type']}")
base.base_oled(3, "Starting...")


# Import necessary modules
from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, send_from_directory, send_file
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from av import VideoFrame, AudioFrame
import json
import uuid
import asyncio
import time
import logging
import logging
import cv_ctrl
import cv2  # Add this line
import audio_ctrl
import os_info
import wifi_ctrl
import ssl

# Get system info
UPLOAD_FOLDER = thisPath + '/sounds/others'
si = os_info.SystemInfo()

# Create a Flask app instance
app = Flask(__name__)
# log = logging.getLogger('werkzeug')
# log.disabled = True
socketio = SocketIO(app)

# Keep peer connections alive
import threading
pc_keep_alive_lock = threading.Lock()

# WebRTC Configuration
import subprocess

def get_tailscale_ip():
    try:
        result = subprocess.run(['tailscale', 'ip', '-4'], capture_output=True, text=True)
        return result.stdout.strip()
    except:
        return "127.0.0.1"

rtc_configuration = RTCConfiguration(iceServers=[])

# Set to keep track of RTCPeerConnection instances
active_pcs = {}

# Maximum number of active connections allowed
MAX_CONNECTIONS = 1

# Set to keep track of RTCPeerConnection instances
pcs = set()

# Camera funcs
cvf = cv_ctrl.OpencvFuncs(thisPath, base)

class TestVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        import numpy as np, cv2
        small = np.random.randint(0, 256, (30, 40, 3), dtype=np.uint8)
        self.img = cv2.resize(small, (80, 60), interpolation=cv2.INTER_LINEAR)
        self.img = np.ascontiguousarray(self.img, dtype=np.uint8)
        print(f"Tiny blurry: {self.img.shape}")
        self.count = 0
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = VideoFrame.from_ndarray(self.img, format="rgb24")
        frame.pts = pts
        frame.time_base = time_base
        return frame

# Video track that wraps our OpenCV camera
class CameraVideoTrack(VideoStreamTrack):
    def __init__(self, cvf):
        super().__init__()
        import numpy as np
        import threading
        self.last_frame = np.zeros((720, 1280, 3), dtype=np.uint8)
        self._lock = threading.Lock()
        self.count = 0
        def capture():
            while True:
                try:
                    frame_bytes = cvf.frame_process()
                    nparr = np.frombuffer(frame_bytes, np.uint8)
                    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    if img is not None:
                        img = cv2.resize(img, (1280, 720))
                        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                        with self._lock:
                            self.last_frame = img_rgb
                except:
                    pass
        threading.Thread(target=capture, daemon=True).start()
        print("CameraVideoTrack initialized at 640x480")
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        with self._lock:
            img = self.last_frame.copy()
        frame = VideoFrame.from_ndarray(img, format="rgb24")
        frame.pts = pts
        frame.time_base = time_base
        self.count += 1
        if self.count % 30 == 0:
            print(f"CameraVideoTrack: sent {self.count} frames")
        return frame


# Audio track from microphone
#class MicrophoneAudioTrack(AudioStreamTrack):
#    """
#    Audio track from system microphone/Bluetooth speaker
#    """
#    def __init__(self):
#        super().__init__()
#        self.player = MediaPlayer(
#            'default',
#            format='alsa',
#            options={'sample_rate': '48000', 'channels': '1'}
#        )
#    
#    async def recv(self):
        return await self.player.audio.recv()  

cmd_actions = {
    f['code']['zoom_x1']: lambda: cvf.scale_ctrl(1),
    f['code']['zoom_x2']: lambda: cvf.scale_ctrl(2),
    f['code']['zoom_x4']: lambda: cvf.scale_ctrl(4),

    f['code']['pic_cap']: cvf.picture_capture,
    f['code']['vid_sta']: lambda: cvf.video_record(True),
    f['code']['vid_end']: lambda: cvf.video_record(False),

    f['code']['cv_none']: lambda: cvf.set_cv_mode(f['code']['cv_none']),
    f['code']['cv_moti']: lambda: cvf.set_cv_mode(f['code']['cv_moti']),
    f['code']['cv_face']: lambda: cvf.set_cv_mode(f['code']['cv_face']),
    f['code']['cv_objs']: lambda: cvf.set_cv_mode(f['code']['cv_objs']),
    f['code']['cv_clor']: lambda: cvf.set_cv_mode(f['code']['cv_clor']),
    f['code']['mp_hand']: lambda: cvf.set_cv_mode(f['code']['mp_hand']),
    f['code']['cv_auto']: lambda: cvf.set_cv_mode(f['code']['cv_auto']),
    f['code']['mp_face']: lambda: cvf.set_cv_mode(f['code']['mp_face']),
    f['code']['mp_pose']: lambda: cvf.set_cv_mode(f['code']['mp_pose']),

    f['code']['re_none']: lambda: cvf.set_detection_reaction(f['code']['re_none']),
    f['code']['re_capt']: lambda: cvf.set_detection_reaction(f['code']['re_capt']),
    f['code']['re_reco']: lambda: cvf.set_detection_reaction(f['code']['re_reco']),

    f['code']['mc_lock']: lambda: cvf.set_movtion_lock(True),
    f['code']['mc_unlo']: lambda: cvf.set_movtion_lock(False),

    f['code']['led_off']: lambda: cvf.head_light_ctrl(0),
    f['code']['led_aut']: lambda: cvf.head_light_ctrl(1),
    f['code']['led_ton']: lambda: cvf.head_light_ctrl(2),

    f['code']['release']: lambda: base.bus_servo_torque_lock(255, 0),
    f['code']['s_panid']: lambda: base.bus_servo_id_set(255, 2),
    f['code']['s_tilid']: lambda: base.bus_servo_id_set(255, 1),
    f['code']['set_mid']: lambda: base.bus_servo_mid_set(255),

    f['code']['base_of']: lambda: base.lights_ctrl(0, base.head_light_status),
    f['code']['base_on']: lambda: base.lights_ctrl(255, base.head_light_status),
    f['code']['head_ct']: lambda: cvf.head_light_ctrl(3),
    f['code']['base_ct']: base.base_lights_ctrl
}

cmd_feedback_actions = [f['code']['cv_none'], f['code']['cv_moti'],
                        f['code']['cv_face'], f['code']['cv_objs'],
                        f['code']['cv_clor'], f['code']['mp_hand'],
                        f['code']['cv_auto'], f['code']['mp_face'],
                        f['code']['mp_pose'], f['code']['re_none'],
                        f['code']['re_capt'], f['code']['re_reco'],
                        f['code']['mc_lock'], f['code']['mc_unlo'],
                        f['code']['led_off'], f['code']['led_aut'],
                        f['code']['led_ton'], f['code']['base_of'],
                        f['code']['base_on'], f['code']['head_ct'],
                        f['code']['base_ct']
                        ]

# cv info process
def process_cv_info(cmd):
    if cmd[f['fb']['detect_type']] != f['code']['cv_none']:
        print(cmd[f['fb']['detect_type']])
        pass

# Function to generate video frames from the camera
def generate_frames():
    while True:
        frame = cvf.frame_process()
        # print(cvf.cv_info())
        try:
            yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n') 
        except Exception as e:
            print("An [generate_frames] error occurred:", e)






# Route to render the HTML template
@app.route("/eyes")
def eyes():
    return render_template("eyes.html")

@app.route('/')
def index():
    audio_ctrl.play_random_audio("connected", False)
    return render_template('index.html')

@app.route('/config')
def get_config():
    with open(thisPath + '/config.yaml', 'r') as file:
        yaml_content = file.read()
    return yaml_content

# Telepresence state
app.config["telepresence_active"] = False
app.config["telepresence_frame"] = None

# Conversation AI routes
add_conversation_routes(app)

@app.route("/telepresence/start", methods=["POST"])
def telepresence_start():
    app.config["telepresence_active"] = True
    print(">>> TELEPRESENCE STARTED - browser audio now playing through speaker")
    return jsonify({"status": "ok", "telepresence": True})

@app.route("/telepresence/stop", methods=["POST"])
def telepresence_stop():
    app.config["telepresence_active"] = False
    app.config["telepresence_frame"] = None
    print(">>> TELEPRESENCE STOPPED - browser audio muted")
    return jsonify({"status": "ok", "telepresence": False})

@app.route("/telepresence/status")
def telepresence_status():
    return jsonify({"active": app.config.get("telepresence_active", False)})

@app.route("/battery")
def battery_status():
    try:
        voltage = base.base_data.get('v', 0) if base.base_data else 0
        # 3S LiPo: 9.9V (empty) to 12.6V (full)
        min_voltage = 9.9
        max_voltage = 12.6
        percentage = max(0, min(100, (voltage - min_voltage) / (max_voltage - min_voltage) * 100))
        return jsonify({
            "voltage": voltage,
            "percentage": round(percentage),
            "status": "full" if percentage > 80 else "good" if percentage > 50 else "low" if percentage > 20 else "critical"
        })
    except Exception as e:
        return jsonify({"error": str(e), "voltage": 0, "percentage": 0, "status": "unknown"})

@app.route("/telepresence/video")
def telepresence_video():
    import time as time_mod
    from flask import Response
    def generate():
        while app.config.get('telepresence_active', False):
            frame = app.config.get('telepresence_frame')
            if frame:
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
            time_mod.sleep(0.033)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/ice-config')
def ice_config():
    return jsonify({
        'iceServers': [
            {'urls': 'stun:stun.l.google.com:19302'}
        ]
    })

# get pictures and videos.
@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('templates', filename)

@app.route('/get_photo_names')
def get_photo_names():
    photo_files = sorted(os.listdir(thisPath + '/templates/pictures'), key=lambda x: os.path.getmtime(os.path.join(thisPath + '/templates/pictures', x)), reverse=True)
    return jsonify(photo_files)

@app.route('/delete_photo', methods=['POST'])
def delete_photo():
    filename = request.form.get('filename')
    try:
        os.remove(os.path.join(thisPath + '/templates/pictures', filename))
        return jsonify(success=True)
    except Exception as e:
        print(e)
        return jsonify(success=False)

@app.route('/videos/<path:filename>')
def videos(filename):
    return send_from_directory(thisPath + '/templates/videos', filename)

@app.route('/get_video_names')
def get_video_names():
    video_files = sorted(
        [filename for filename in os.listdir(thisPath + '/templates/videos/') if filename.endswith('.mp4')],
        key=lambda filename: os.path.getctime(os.path.join(thisPath + '/templates/videos/', filename)),
        reverse=True
    )
    return jsonify(video_files)

@app.route('/delete_video', methods=['POST'])
def delete_video():
    filename = request.form.get('filename')
    try:
        os.remove(os.path.join(thisPath + '/templates/videos', filename))
        return jsonify(success=True)
    except Exception as e:
        print(e)
        return jsonify(success=False)

@app.route('/shutdown', methods=['POST'])
def shutdown():
    subprocess.Popen(['sudo', 'shutdown', '-h', 'now'])
    return jsonify({'status': 'shutting down'})

@app.route('/reboot', methods=['POST'])
def reboot():
    subprocess.Popen(['sudo', 'reboot'])
    return jsonify({'status': 'rebooting'})
@app.route('/camera/capture', methods=['GET'])
def camera_capture():
    """Capture a single frame from the camera for AI vision"""
    try:
        from cv_ctrl import capture_frame_base64
        image_data = capture_frame_base64()
        if image_data:
            return jsonify({'success': True, 'image': image_data})
        else:
            return jsonify({'success': False, 'error': 'Failed to capture frame'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})




# Video WebRTC
# Function to manage connections
async def manage_connections(pc_id, pc):
    if len(active_pcs) >= MAX_CONNECTIONS:
        # If maximum connections reached, terminate the oldest connection
        oldest_pc_id = next(iter(active_pcs))
        old_pc = active_pcs.pop(oldest_pc_id)
        await old_pc.close()
    # Add new connection to active connections
    active_pcs[pc_id] = pc

async def offer_async():
    params = request.json
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    pc = RTCPeerConnection(configuration=rtc_configuration)
    @pc.on("iceconnectionstatechange")
    async def on_ice_state_change():
        print(f">>> SERVER ICE STATE: {pc.iceConnectionState}")
    @pc.on("connectionstatechange")
    async def on_connection_state_change():
        print(f">>> SERVER CONNECTION STATE: {pc.connectionState}")
    # Handle incoming audio and video from browser
    @pc.on("track")
    async def on_track(track):
        print(f"Received {track.kind} track from browser")
        if track.kind == "video":
            async def receive_video():
                count = 0
                try:
                    while True:
                        frame = await track.recv()
                        count += 1
                        if app.config.get('telepresence_active', False):
                            img = frame.to_ndarray(format="bgr24")
                            ret, jpeg = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 70])
                            if ret:
                                app.config['telepresence_frame'] = jpeg.tobytes()
                        if count <= 3:
                            print(f"Browser video frame {count}: {frame.width}x{frame.height}")
                except Exception as e:
                    print(f"Browser video ended after {count} frames: {e}")
            import asyncio as aio_v
            aio_v.ensure_future(receive_video())
            print("Browser video track ready")
        if track.kind == "audio":
            # Store track reference for telepresence toggle
            app.config['browser_audio_track'] = track
            
            async def play_audio():
                import subprocess
                paplay_proc = None
                count = 0
                try:
                    while True:
                        frame = await track.recv()
                        count += 1
                        # Only play audio when telepresence is active
                        if not app.config.get('telepresence_active', False):
                            continue
                        # Start paplay on first real frame
                        if paplay_proc is None:
                            paplay_proc = subprocess.Popen(
                                ['paplay', '--format=s16le', '--rate=48000', '--channels=2', '--raw'],
                                stdin=subprocess.PIPE
                            )
                            print("Started paplay for telepresence audio")
                        arr = frame.to_ndarray()
                        try:
                            paplay_proc.stdin.write(arr.tobytes())
                            paplay_proc.stdin.flush()
                        except BrokenPipeError:
                            print("paplay pipe broken, restarting...")
                            paplay_proc = subprocess.Popen(
                                ['paplay', '--format=s16le', '--rate=48000', '--channels=2', '--raw'],
                                stdin=subprocess.PIPE
                            )
                except Exception as e:
                    print(f"Audio track ended after {count} frames: {e}")
                    if paplay_proc:
                        paplay_proc.stdin.close()
                        paplay_proc.wait()
            import asyncio as aio
            aio.ensure_future(play_audio())
            print("Audio track ready (waiting for telepresence)")
    await pc.setRemoteDescription(offer)
    video_track = CameraVideoTrack(cvf)
    pc.addTrack(video_track)
    print("Added video track")
    # Add Pi microphone audio
    try:
        audio_player = MediaPlayer(
            'default',
            format='pulse',
            options={'sample_rate': '48000', 'channels': '1'}
        )
        if audio_player.audio:
            pc.addTrack(audio_player.audio)
            print("USB mic audio track added")
        else:
            print("WARNING: No audio track from MediaPlayer")
    except Exception as e:
        print(f"Could not add audio: {e}")
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    print("Waiting for ICE candidates...")
    await asyncio.sleep(2)
    print(f"ICE gathering state: {pc.iceGatheringState}")
    print(f"Local description SDP length: {len(pc.localDescription.sdp)}")
    # Filter out IPv6 candidates
    sdp_lines = pc.localDescription.sdp.split("\r\n")
    sdp_lines = [l for l in sdp_lines if not (l.startswith("a=candidate:") and (" " + ":" in l.split(" ")[4] if len(l.split(" ")) > 4 else False))]
    filtered_sdp = "\r\n".join(sdp_lines)
    return jsonify({"sdp": filtered_sdp, "type": pc.localDescription.type})

    # Prepare the response data with local SDP and type
    response_data = {
        "sdp": pc.localDescription.sdp, 
        "type": pc.localDescription.type
    }

    return jsonify(response_data)

# Wrapper function for running the asynchronous offer function
    return future.result()

# set product version
def set_version(input_main, input_module):
    base.base_json_ctrl({"T":900,"main":input_main,"module":input_module})
    if input_main == 1:
        cvf.info_update("RaspRover", (0,255,255), 0.36)
    elif input_main == 2:
        cvf.info_update("UGV Rover", (0,255,255), 0.36)
    elif input_main == 3:
        cvf.info_update("UGV Beast", (0,255,255), 0.36)
    if input_module == 0:
        cvf.info_update("No Module", (0,255,255), 0.36)
    elif input_module == 1:
        cvf.info_update("ARM", (0,255,255), 0.36)
    elif input_module == 2:
        cvf.info_update("PT", (0,255,255), 0.36)

# main cmdline for robot ctrl
def cmdline_ctrl(args_string):
    if not args_string:
        return
    args = args_string.split()
    # base -c {"T":1,"L":0.5,"R":0.5}
    if args[0] == 'base':
        if args[1] == '-c' or args[1] == '--cmd':
            base.base_json_ctrl(json.loads(args[2]))
        elif args[1] == '-r' or args[1] == '--recv':
            if args[2] == 'on':
                cvf.show_recv_info(True)
            else:
                cvf.show_recv_info(False)

    elif args[0] == 'audio':
        if args[1] == '-s' or args[1] == '--say':
            audio_ctrl.play_speech_thread(' '.join(args[2:]))
        elif args[1] == '-v' or args[1] == '--volume':
            audio_ctrl.set_audio_volume(args[2])
        elif args[1] == '-p' or args[1] == '--play_file':
            audio_ctrl.play_file(args[2])

    elif args[0] == 'send':
        if args[1] == '-a' or args[1] == '--add':
            if args[2] == '-b' or args[2] == '--broadcast':
                base.base_json_ctrl({"T":303,"mac":"FF:FF:FF:FF:FF:FF"})
            else:
                base.base_json_ctrl({"T":303,"mac":args[2]})
        elif args[1] == '-rm' or args[1] == '--remove':
            if args[2] == '-b' or args[2] == '--broadcast':
                base.base_json_ctrl({"T":304,"mac":"FF:FF:FF:FF:FF:FF"})
            else:
                base.base_json_ctrl({"T":304,"mac":args[2]})
        elif args[1] == '-b' or args[1] == '--broadcast':
            base.base_json_ctrl({"T":306,"mac":"FF:FF:FF:FF:FF:FF","dev":0,"b":0,"s":0,"e":0,"h":0,"cmd":3,"megs":' '.join(args[2:])})
        elif args[1] == '-g' or args[1] == '--group':
            base.base_json_ctrl({"T":305,"dev":0,"b":0,"s":0,"e":0,"h":0,"cmd":3,"megs":' '.join(args[2:])})
        else:
            base.base_json_ctrl({"T":306,"mac":args[1],"dev":0,"b":0,"s":0,"e":0,"h":0,"cmd":3,"megs":' '.join(args[2:])})

    elif args[0] == 'cv':
        if args[1] == '-r' or args[1] == '--range':
            try:
                lower_trimmed = args[2].strip("[]")
                lower_nums = [int(lower_num) for lower_num in lower_trimmed.split(",")]
                if all(0 <= num <= 255 for num in lower_nums):
                    pass
                else:
                    return
            except:
                return
            try:
                upper_trimmed = args[3].strip("[]")
                upper_nums = [int(upper_num) for upper_num in upper_trimmed.split(",")]
                if all(0 <= num <= 255 for num in upper_nums):
                    pass
                else:
                    return
            except:
                return
            cvf.change_target_color(lower_nums, upper_nums)
        elif args[1] == '-s' or args[1] == '--select':
            cvf.selet_target_color(args[2])

    elif args[0] == 'video' or args[0] == 'v':
        if args[1] == '-q' or args[1] == '--quality':
            try:
                int(args[2])
            except:
                return
            cvf.set_video_quality(int(args[2]))

    elif args[0] == 'line':
        if args[1] == '-r' or args[1] == '--range':
            try:
                lower_trimmed = args[2].strip("[]")
                lower_nums = [int(lower_num) for lower_num in lower_trimmed.split(",")]
                if all(0 <= num <= 255 for num in lower_nums):
                    pass
                else:
                    return
            except:
                return
            try:
                upper_trimmed = args[3].strip("[]")
                upper_nums = [int(upper_num) for upper_num in upper_trimmed.split(",")]
                if all(0 <= num <= 255 for num in upper_nums):
                    pass
                else:
                    return
            except:
                return
            cvf.change_line_color(lower_nums, upper_nums)
        elif args[1] == '-s' or args[1] == '--set':
            if len(args) != 9:
                return
            try:
                for i in range(2,9):
                    float(args[i])
            except:
                return
            # line -s 0.7 0.8 1.6 0.0006 0.6 0.4 0.2
            cvf.set_line_track_args(float(args[2]), float(args[3]), float(args[4]), float(args[5]), float(args[6]), float(args[7]), float(args[8]))

    elif args[0] == 'track':
        cvf.set_pt_track_args(args[1], args[2])

    elif args[0] == 'timelapse':
        if args[1] == '-s' or args[1] == '--start':
            if len(args) != 6:
                return
            try:
                move_speed = float(args[2])
                move_time  = float(args[3])
                t_interval = float(args[4])
                loop_times = int(args[5])
            except:
                return
            cvf.timelapse(move_speed, move_time, t_interval, loop_times)
        elif args[1] == '-e' or args[1] == '--end' or args[1] == '--stop':
            cvf.mission_stop()

    elif args[0] == 'p':
        main_type = int(args[1][0])
        module_type = int(args[1][1])
        set_version(main_type, module_type)

    # s 20
    elif args[0] == 's':
        main_type = int(args[1][0])
        module_type = int(args[1][1])
        if main_type == 1:
            f['base_config']['robot_name'] = "RaspRover"
            f['args_config']['max_speed'] = 0.65
            f['args_config']['slow_speed'] = 0.3
        elif main_type == 2:
            f['base_config']['robot_name'] = "UGV Rover"
            f['args_config']['max_speed'] = 1.3
            f['args_config']['slow_speed'] = 0.2
        elif main_type == 3:
            f['base_config']['robot_name'] = "UGV Beast"
            f['args_config']['max_speed'] = 1.0
            f['args_config']['slow_speed'] = 0.2
        f['base_config']['main_type'] = main_type
        f['base_config']['module_type'] = module_type
        with open(thisPath + '/config.yaml', "w") as yaml_file:
            yaml.dump(f, yaml_file)
        set_version(main_type, module_type)

    elif args[0] == 'test':
        cvf.update_base_data({"T":1003,"mac":1111,"megs":"helllo aaaaaaaa"})


# Route to handle the offer request
@app.route('/offer', methods=['POST'])
def offer():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Run in a background thread to keep loop alive
    def run_loop():
        asyncio.set_event_loop(loop)
        loop.run_forever()
    
    thread = threading.Thread(target=run_loop, daemon=True)
    thread.start()
    
    # Run the offer_async coroutine
    future = asyncio.run_coroutine_threadsafe(offer_async(), loop)
    result = future.result(timeout=10)
    
    return result

# Route to stream video frames
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/send_command', methods=['POST'])
def handle_command():
    command = request.form['command']
    print("Received command:", command)
    cvf.info_update("CMD:" + command, (0,255,255), 0.36)
    try:
        cmdline_ctrl(command)
    except Exception as e:
        print(f"[app.handle_command] error: {e}")
    return jsonify({"status": "success", "message": "Command received"})

@app.route('/getAudioFiles', methods=['GET'])
def get_audio_files():
    files = [f for f in os.listdir(UPLOAD_FOLDER) if os.path.isfile(os.path.join(UPLOAD_FOLDER, f)) and (f.endswith('.mp3') or f.endswith('.wav'))]
    return jsonify(files)

@app.route('/uploadAudio', methods=['POST'])
def upload_audio():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'})
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'})
    if file:
        filename = secure_filename(file.filename)
        file.save(os.path.join(UPLOAD_FOLDER, filename))
        return jsonify({'success': 'File uploaded successfully'})

@app.route('/playAudio', methods=['POST'])
def play_audio():
    audio_file = request.form['audio_file']
    print(thisPath + '/sounds/others/' + audio_file)
    audio_ctrl.play_audio_thread(thisPath + '/sounds/others/' + audio_file)
    return jsonify({'success': 'Audio is playing'})

@app.route('/stop_audio', methods=['POST'])
def audio_stop():
    audio_ctrl.stop()
    return jsonify({'success': 'Audio stop'})

@app.route('/settings/<path:filename>')
def serve_static_settings(filename):
    return send_from_directory('templates', filename)


# WiFi management endpoints
@app.route('/wifi/status')
def wifi_status():
    return jsonify(wifi_ctrl.get_wifi_status())

@app.route('/wifi/scan')
def wifi_scan():
    return jsonify(wifi_ctrl.scan_networks())

@app.route('/wifi/saved')
def wifi_saved():
    return jsonify(wifi_ctrl.get_saved_profiles())

@app.route('/wifi/connect', methods=['POST'])
def wifi_connect():
    ssid = request.form.get('ssid', '')
    password = request.form.get('password', '')
    if not ssid:
        return jsonify({"success": False, "message": "SSID is required"})
    success, message = wifi_ctrl.connect_to_network(ssid, password if password else None)
    return jsonify({"success": success, "message": message})

@app.route('/wifi/hotspot', methods=['POST'])
def wifi_hotspot():
    success, message = wifi_ctrl.switch_to_hotspot()
    return jsonify({"success": success, "message": message})

@app.route('/wifi/forget', methods=['POST'])
def wifi_forget():
    ssid = request.form.get('ssid', '')
    if not ssid:
        return jsonify({"success": False, "message": "SSID is required"})
    success, message = wifi_ctrl.forget_network(ssid)
    return jsonify({"success": success, "message": message})


# Web socket
@socketio.on('json', namespace='/json')
def handle_socket_json(json):
    try:
        base.base_json_ctrl(json)
    except Exception as e:
        print("Error handling JSON data:", e)
        return

# info update single
def update_data_websocket_single():
    # {'T':1001,'L':0,'R':0,'r':0,'p':0,'v': 11,'pan':0,'tilt':0}
    try:
        socket_data = {
            f['fb']['picture_size']:si.pictures_size,
            f['fb']['video_size']:  si.videos_size,
            f['fb']['cpu_load']:    si.cpu_load,
            f['fb']['cpu_temp']:    si.cpu_temp,
            f['fb']['ram_usage']:   si.ram,
            f['fb']['wifi_rssi']:   si.wifi_rssi,

            f['fb']['led_mode']:    cvf.cv_light_mode,
            f['fb']['detect_type']: cvf.cv_mode,
            f['fb']['detect_react']:cvf.detection_reaction_mode,
            f['fb']['pan_angle']:   cvf.pan_angle,
            f['fb']['tilt_angle']:  cvf.tilt_angle,
            f['fb']['base_voltage']:base.base_data['v'],
            f['fb']['video_fps']:   cvf.video_fps,
            f['fb']['cv_movtion_mode']: cvf.cv_movtion_lock,
            f['fb']['base_light']:  base.base_light_status
        }
        socketio.emit('update', socket_data, namespace='/ctrl')
    except Exception as e:
        print("An [app.update_data_websocket_single] error occurred:", e)

# info feedback
def update_data_loop():
    base.base_oled(2, "F/J:5000/8888")
    start_time = time.time()
    time.sleep(1)
    while 1:
        update_data_websocket_single()
        eth0 = si.eth0_ip
        wlan = si.wlan_ip
        if eth0:
            base.base_oled(0, f"E:{eth0}")
        else:
            base.base_oled(0, f"E: No Ethernet")
        if wlan:
            base.base_oled(1, f"W:{wlan}")
        else:
            base.base_oled(1, f"W: NO {si.net_interface}")
        elapsed_time = time.time() - start_time
        hours = int(elapsed_time // 3600)
        minutes = int((elapsed_time % 3600) // 60)
        seconds = int(elapsed_time % 60)
        base.base_oled(3, f"{si.wifi_mode} {hours:02d}:{minutes:02d}:{seconds:02d} {si.wifi_rssi}dBm")
        time.sleep(5)

def base_data_loop():
    sensor_interval = 1
    sensor_read_time = time.time()
    while True:
        cvf.update_base_data(base.feedback_data())

        # get sensor data
        if base.extra_sensor:
            if time.time() - sensor_read_time > sensor_interval:
                base.rl.read_sensor_data()
                sensor_read_time = time.time()
        
        # get lidar data
        if base.use_lidar:
            base.rl.lidar_data_recv()
        
        time.sleep(0.025)

@socketio.on('message', namespace='/ctrl')
def handle_socket_cmd(message):
    try:
        json_data = json.loads(message)
    except json.JSONDecodeError:
        print("Error decoding JSON.[app.handle_socket_cmd]")
        return
    cmd_a = float(json_data.get("A", 0))
    if cmd_a in cmd_actions:
        cmd_actions[cmd_a]()
    else:
        pass
    if cmd_a in cmd_feedback_actions:
        threading.Thread(target=update_data_websocket_single, daemon=True).start()



# commandline on boot
def cmd_on_boot():
    cmd_list = [
        'base -c {"T":142,"cmd":50}',   # set feedback interval
        'base -c {"T":131,"cmd":1}',    # serial feedback flow on
        'base -c {"T":143,"cmd":0}',    # serial echo off
        'base -c {{"T":4,"cmd":{}}}'.format(f['base_config']['module_type']),      # select the module - 0:None 1:RoArm-M2-S 2:Gimbal
        'base -c {"T":300,"mode":0,"mac":"EF:EF:EF:EF:EF:EF"}',  # the base won't be ctrl by esp-now broadcast cmd, but it can still recv broadcast megs.
        'send -a -b'    # add broadcast mac addr to peer
    ]
    print('base -c {{"T":4,"cmd":{}}}'.format(f['base_config']['module_type']))
    for i in range(0, len(cmd_list)):
        cmdline_ctrl(cmd_list[i])
        cvf.info_update(cmd_list[i], (0,255,255), 0.36)
    set_version(f['base_config']['main_type'], f['base_config']['module_type'])


# Run the Flask app
if __name__ == "__main__":

    
    # lights off
    base.lights_ctrl(255, 255)
    
    # play a audio file in /sounds/robot_started/
    audio_ctrl.play_random_audio("robot_started", False)

    # update the size of videos and pictures
    si.update_folder(thisPath)

    # pt/arm looks forward
    if f['base_config']['module_type'] == 1:
        base.base_json_ctrl({"T":f['cmd_config']['cmd_arm_ctrl_ui'],"E":f['args_config']['arm_default_e'],"Z":f['args_config']['arm_default_z'],"R":f['args_config']['arm_default_r']})
    else:
        base.gimbal_ctrl(0, 0, 200, 10)

    # feedback loop starts
    si.start()
    si.resume()
    data_update_thread = threading.Thread(target=update_data_loop, daemon=True)
    data_update_thread.start()

    # base data update
    base_update_thread = threading.Thread(target=base_data_loop, daemon=True)
    base_update_thread.start()

    # lights off
    base.lights_ctrl(0, 0)
    cmd_on_boot()

    # run the main web app
    # Launch eyes on Pi screen
    import subprocess
    import os
    def launch_eyes():
        import time
        time.sleep(3)  # Wait for Flask to be ready
        env = os.environ.copy()
        env["DISPLAY"] = ":0"
        try:
            subprocess.Popen([
                "chromium-browser",
                "--start-fullscreen", "--noerrdialogs", "--disable-infobars",
                "--no-first-run", "--ignore-certificate-errors", "--disable-infobars", "--test-type", "--app=https://localhost:5000/eyes"
            ], env=env)
            print(">>> Eyes launched on Pi screen")
        except Exception as e:
            print(f"Could not launch eyes: {e}")
    threading.Thread(target=launch_eyes, daemon=True).start()
    
    # Start conversation AI engine
    start_conversation_engine()

    # Create SSL context for HTTPS
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(
        '/home/ws/ugv_rpi/catbot.tailaa6986.ts.net.crt',
        '/home/ws/ugv_rpi/catbot.tailaa6986.ts.net.key'
    )

    socketio.run(app, host='0.0.0.0', port=5000, allow_unsafe_werkzeug=True, ssl_context=ssl_context)
