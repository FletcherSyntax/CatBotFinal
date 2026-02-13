#!/usr/bin/env python3
"""Patch app.py to add two-way video telepresence support"""

with open('/home/ws/ugv_rpi/app.py', 'r') as f:
    content = f.read()

# 1. Add video handler to on_track
old_on_track = '''    # Handle incoming audio and video from browser
    @pc.on("track")
    async def on_track(track):
        print(f"Received {track.kind} track from browser")
        if track.kind == "audio":'''

# If the old format doesn't exist, try the other format
if old_on_track not in content:
    old_on_track = '''    # Handle incoming audio from browser
    @pc.on("track")
    async def on_track(track):
        print(f"Received {track.kind} track from browser")
        if track.kind == "audio":'''

new_on_track = '''    # Handle incoming audio and video from browser
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
        if track.kind == "audio":'''

if old_on_track in content:
    content = content.replace(old_on_track, new_on_track, 1)
    print("1. Added video handler to on_track")
else:
    print("WARNING: Could not find on_track handler to patch")

# 2. Add telepresence status and MJPEG endpoints
old_telepresence_stop = '''@app.route("/telepresence/stop", methods=["POST"])
def telepresence_stop():
    app.config["telepresence_active"] = False
    print(">>> TELEPRESENCE STOPPED - browser audio muted")
    return jsonify({"status": "ok", "telepresence": False})'''

new_telepresence_stop = '''@app.route("/telepresence/stop", methods=["POST"])
def telepresence_stop():
    app.config["telepresence_active"] = False
    app.config["telepresence_frame"] = None
    print(">>> TELEPRESENCE STOPPED - browser audio muted")
    return jsonify({"status": "ok", "telepresence": False})

@app.route("/telepresence/status")
def telepresence_status():
    return jsonify({"active": app.config.get("telepresence_active", False)})

@app.route("/telepresence/video")
def telepresence_video():
    import time as time_mod
    from flask import Response
    def generate():
        while app.config.get('telepresence_active', False):
            frame = app.config.get('telepresence_frame')
            if frame:
                yield (b'--frame\\r\\n'
                       b'Content-Type: image/jpeg\\r\\n\\r\\n' + frame + b'\\r\\n')
            time_mod.sleep(0.033)
    return Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')'''

if old_telepresence_stop in content:
    content = content.replace(old_telepresence_stop, new_telepresence_stop, 1)
    print("2. Added telepresence status and MJPEG endpoints")
else:
    print("WARNING: Could not find telepresence_stop to patch")

# 3. Initialize telepresence_frame in config
old_config = 'app.config["telepresence_active"] = False'
new_config = 'app.config["telepresence_active"] = False\napp.config["telepresence_frame"] = None'

if new_config not in content:  # Don't double-add
    content = content.replace(old_config, new_config, 1)
    print("3. Added telepresence_frame config")

with open('/home/ws/ugv_rpi/app.py', 'w') as f:
    f.write(content)

print("\nDone! app.py patched for two-way video telepresence.")
