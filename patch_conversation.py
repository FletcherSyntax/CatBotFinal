#!/usr/bin/env python3
"""Patch app.py to integrate the conversation engine"""

with open('/home/ws/ugv_rpi/app.py', 'r') as f:
    content = f.read()

# 1. Add import for conversation engine near the top (after existing imports)
old_imports = "from base_ctrl import BaseController"
new_imports = """from base_ctrl import BaseController
from conversation import add_conversation_routes, start_conversation_engine"""

if "from conversation import" not in content:
    content = content.replace(old_imports, new_imports, 1)
    print("1. Added conversation imports")
else:
    print("1. Conversation imports already present")

# 2. Add conversation routes after Flask app setup
# Find where routes are added - after app config for telepresence
old_telepresence_config = 'app.config["telepresence_active"] = False\napp.config["telepresence_frame"] = None'
new_telepresence_config = '''app.config["telepresence_active"] = False
app.config["telepresence_frame"] = None

# Conversation AI routes
add_conversation_routes(app)'''

if "add_conversation_routes" not in content:
    if old_telepresence_config in content:
        content = content.replace(old_telepresence_config, new_telepresence_config, 1)
        print("2. Added conversation routes")
    else:
        # Try without telepresence_frame
        old_tc = 'app.config["telepresence_active"] = False'
        new_tc = 'app.config["telepresence_active"] = False\n\n# Conversation AI routes\nadd_conversation_routes(app)'
        content = content.replace(old_tc, new_tc, 1)
        print("2. Added conversation routes (alt)")
else:
    print("2. Conversation routes already present")

# 3. Start conversation engine before socketio.run
old_launch = "threading.Thread(target=launch_eyes, daemon=True).start()"
new_launch = """threading.Thread(target=launch_eyes, daemon=True).start()

# Start conversation AI engine
start_conversation_engine()"""

if "start_conversation_engine()" not in content:
    content = content.replace(old_launch, new_launch, 1)
    print("3. Added conversation engine startup")
else:
    print("3. Conversation engine startup already present")

with open('/home/ws/ugv_rpi/app.py', 'w') as f:
    f.write(content)

print("\nDone! app.py patched for conversation AI.")
print("\nRemember to:")
print("  1. Place conversation.py in ~/ugv_rpi/")
print("  2. Place hey-catbot.ppn in ~/ugv_rpi/")
print("  3. Set PICOVOICE_ACCESS_KEY in conversation.py")
print("  4. pip install pvporcupine google-genai pyaudio --break-system-packages")
