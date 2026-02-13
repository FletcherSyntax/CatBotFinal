#!/usr/bin/env python3
"""Patch eyes.html to react to conversation states (listening, speaking, thinking)"""

with open('/home/ws/ugv_rpi/templates/eyes.html', 'r') as f:
    content = f.read()

# Add conversation state polling and eye reactions
# Insert before the telepresence overlay script

old_telepresence_script = """<script>
let telepresenceShowing = false;
async function checkTelepresence() {"""

new_conversation_and_telepresence = """<script>
// ====== CONVERSATION STATE REACTIONS ======
let currentConvState = 'idle';
let convPulseInterval = null;

async function checkConversationState() {
  try {
    const resp = await fetch('/conversation/state');
    const data = await resp.json();
    
    if (data.state !== currentConvState) {
      currentConvState = data.state;
      applyConversationState(currentConvState);
    }
  } catch(e) {}
  setTimeout(checkConversationState, 300);
}

function applyConversationState(state) {
  const eyes = document.querySelectorAll('.eye');
  const irises = document.querySelectorAll('.iris');
  const pupils = document.querySelectorAll('.pupil');
  
  // Clear any existing pulse animation
  if (convPulseInterval) {
    clearInterval(convPulseInterval);
    convPulseInterval = null;
  }
  
  // Reset eye styles
  eyes.forEach(eye => {
    eye.style.transition = 'all 0.3s ease';
    eye.style.boxShadow = '';
  });
  irises.forEach(iris => {
    iris.style.transition = 'all 0.3s ease';
    iris.style.background = '';
    iris.style.transform = '';
  });
  
  switch(state) {
    case 'listening':
      // Bright green glow, pupils dilated (attentive)
      irises.forEach(iris => {
        iris.style.background = 'radial-gradient(circle at 40% 40%, #90ff90, #40c040 50%, #208020)';
        iris.style.transform = 'scale(1.15)';
      });
      eyes.forEach(eye => {
        eye.style.boxShadow = '0 0 30px rgba(100, 255, 100, 0.5), inset 0 0 20px rgba(0,0,0,0.3)';
      });
      // Subtle pulse while listening
      let pulseUp = true;
      convPulseInterval = setInterval(() => {
        irises.forEach(iris => {
          iris.style.transform = pulseUp ? 'scale(1.2)' : 'scale(1.1)';
        });
        pulseUp = !pulseUp;
      }, 800);
      break;
      
    case 'thinking':
      // Yellow/amber, eyes slightly narrowed
      irises.forEach(iris => {
        iris.style.background = 'radial-gradient(circle at 40% 40%, #ffffaa, #e0c040 50%, #a08020)';
      });
      eyes.forEach(eye => {
        eye.style.boxShadow = '0 0 20px rgba(255, 200, 50, 0.4), inset 0 0 20px rgba(0,0,0,0.3)';
        eye.style.transform = 'scaleY(0.85)';
      });
      break;
      
    case 'speaking':
      // Bright blue/cyan, lively
      irises.forEach(iris => {
        iris.style.background = 'radial-gradient(circle at 40% 40%, #aaffff, #40a0e0 50%, #2060a0)';
        iris.style.transform = 'scale(1.1)';
      });
      eyes.forEach(eye => {
        eye.style.boxShadow = '0 0 25px rgba(80, 180, 255, 0.5), inset 0 0 20px rgba(0,0,0,0.3)';
      });
      // Animated pulse while speaking
      let speakBright = true;
      convPulseInterval = setInterval(() => {
        irises.forEach(iris => {
          iris.style.transform = speakBright ? 'scale(1.15)' : 'scale(1.05)';
        });
        eyes.forEach(eye => {
          const glow = speakBright ? '0 0 35px rgba(80, 180, 255, 0.6)' : '0 0 20px rgba(80, 180, 255, 0.3)';
          eye.style.boxShadow = glow + ', inset 0 0 20px rgba(0,0,0,0.3)';
        });
        speakBright = !speakBright;
      }, 400);
      break;
      
    case 'idle':
    default:
      // Return to normal green
      eyes.forEach(eye => {
        eye.style.boxShadow = '';
        eye.style.transform = '';
      });
      irises.forEach(iris => {
        iris.style.background = '';
        iris.style.transform = '';
      });
      break;
  }
}

setTimeout(checkConversationState, 1000);

// ====== TELEPRESENCE STATE ======
let telepresenceShowing = false;
async function checkTelepresence() {"""

if 'checkConversationState' not in content:
    content = content.replace(old_telepresence_script, new_conversation_and_telepresence, 1)
    print("Updated eyes.html with conversation state reactions")
else:
    print("Conversation state reactions already present in eyes.html")

with open('/home/ws/ugv_rpi/templates/eyes.html', 'w') as f:
    f.write(content)
