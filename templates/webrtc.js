// WebRTC with telepresence toggle (audio + video)
let webrtcPC = null;
let telepresenceActive = false;
let localMicStream = null;
let localCamStream = null;
let micSender = null;
let videoSender = null;

async function startWebRTC() {
    console.log("=== Starting WebRTC ===");

    const iceResponse = await fetch('/ice-config');
    const iceConfig = await iceResponse.json();

    webrtcPC = new RTCPeerConnection(iceConfig);

    webrtcPC.onicecandidate = (event) => {
        if (event.candidate) {
            console.log("ICE candidate:", event.candidate.candidate);
        } else {
            console.log("ICE gathering complete");
        }
    };

    webrtcPC.ontrack = (event) => {
        console.log("*** RECEIVED TRACK:", event.track.kind);
        if (event.track.kind === 'video') {
            const videoElement = document.getElementById('webrtc-video');
            if (videoElement) {
                videoElement.srcObject = event.streams[0];
                console.log("*** VIDEO ELEMENT SET");
            }
        }
        if (event.track.kind === 'audio') {
            const audioElement = document.getElementById('webrtc-audio');
            if (audioElement) {
                audioElement.srcObject = new MediaStream([event.track]);
                audioElement.play().then(() => {
                    console.log("*** AUDIO PLAYING");
                }).catch(e => {
                    console.log("Audio autoplay blocked, waiting for user click...");
                    const resumeAudio = () => {
                        audioElement.play();
                        console.log("*** AUDIO RESUMED after user click");
                        document.removeEventListener('click', resumeAudio);
                    };
                    document.addEventListener('click', resumeAudio);
                });
                console.log("*** AUDIO ELEMENT SET");
            }
        }
    };

    webrtcPC.oniceconnectionstatechange = () => {
        console.log(">>> ICE CONNECTION STATE:", webrtcPC.iceConnectionState);
    };

    webrtcPC.onconnectionstatechange = () => {
        console.log(">>> CONNECTION STATE:", webrtcPC.connectionState);
    };

    try {
        // Silent audio placeholder
        const silentCtx = new AudioContext();
        const silentOsc = silentCtx.createOscillator();
        const silentDest = silentCtx.createMediaStreamDestination();
        silentOsc.connect(silentDest);
        silentOsc.start();
        const silentTrack = silentDest.stream.getAudioTracks()[0];
        silentTrack.enabled = false;
        micSender = webrtcPC.addTrack(silentTrack, silentDest.stream);
        console.log("Added silent placeholder audio track");

        // Black video placeholder
        const blackCanvas = document.createElement('canvas');
        blackCanvas.width = 640;
        blackCanvas.height = 480;
        const bctx = blackCanvas.getContext('2d');
        bctx.fillStyle = 'black';
        bctx.fillRect(0, 0, 640, 480);
        const blackStream = blackCanvas.captureStream(1);
        const blackTrack = blackStream.getVideoTracks()[0];
        videoSender = webrtcPC.addTrack(blackTrack, blackStream);
        console.log("Added black placeholder video track");

        // Force H264 codec for Pi->Browser video
        const videoTransceiver = webrtcPC.addTransceiver('video', { direction: 'recvonly' });
        const codecs = RTCRtpReceiver.getCapabilities('video').codecs;
        const h264Codecs = codecs.filter(c => c.mimeType === 'video/H264');
        if (h264Codecs.length > 0) {
            videoTransceiver.setCodecPreferences(h264Codecs);
            console.log("Forced H264 codec preference");
        }

        console.log("Creating offer...");
        const offer = await webrtcPC.createOffer({
            offerToReceiveVideo: true,
            offerToReceiveAudio: true
        });

        console.log("Setting local description...");
        await webrtcPC.setLocalDescription(offer);

        console.log("Waiting for ICE gathering...");
        await new Promise((resolve) => {
            if (webrtcPC.iceGatheringState === 'complete') {
                resolve();
            } else {
                const checkState = () => {
                    console.log("ICE gathering state:", webrtcPC.iceGatheringState);
                    if (webrtcPC.iceGatheringState === 'complete') {
                        resolve();
                    }
                };
                webrtcPC.addEventListener('icegatheringstatechange', checkState);
                setTimeout(() => {
                    console.log("ICE gathering timeout, proceeding anyway");
                    resolve();
                }, 3000);
            }
        });

        console.log("Sending offer to server...");
        const response = await fetch('/offer', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                sdp: webrtcPC.localDescription.sdp,
                type: webrtcPC.localDescription.type
            })
        });

        if (!response.ok) {
            throw new Error("Server returned " + response.status);
        }

        const answer = await response.json();
        console.log("Received answer from server");
        await webrtcPC.setRemoteDescription(answer);
        console.log("Remote description set!");

    } catch (error) {
        console.error("!!! WebRTC ERROR:", error);
    }
}

// ====== TELEPRESENCE TOGGLE ======
async function startTelepresence() {
    if (telepresenceActive) return;

    try {
        // Get real microphone AND webcam
        localCamStream = await navigator.mediaDevices.getUserMedia({
            audio: true,
            video: { width: 1280, height: 720 }
        });

        const micTrack = localCamStream.getAudioTracks()[0];
        const camTrack = localCamStream.getVideoTracks()[0];
        console.log("Got mic:", micTrack.label);
        console.log("Got camera:", camTrack.label);

        // Replace placeholders with real tracks
        if (micSender) {
            await micSender.replaceTrack(micTrack);
            console.log("Replaced silent track with real mic");
        }
        if (videoSender) {
            await videoSender.replaceTrack(camTrack);
            console.log("Replaced black video with webcam");
        }

        // Show local preview
        const preview = document.getElementById('local-preview');
        if (preview) {
            preview.srcObject = new MediaStream([camTrack]);
            preview.style.display = 'block';
        }

        // Tell server to start telepresence
        await fetch('/telepresence/start', { method: 'POST' });

        telepresenceActive = true;
        updateTelepresenceButton();
        console.log("=== TELEPRESENCE ACTIVE ===");

    } catch (error) {
        console.error("Telepresence error:", error);
    }
}

async function stopTelepresence() {
    if (!telepresenceActive) return;

    try {
        // Replace with placeholders
        if (micSender) {
            const silentCtx = new AudioContext();
            const silentOsc = silentCtx.createOscillator();
            const silentDest = silentCtx.createMediaStreamDestination();
            silentOsc.connect(silentDest);
            silentOsc.start();
            const silentTrack = silentDest.stream.getAudioTracks()[0];
            silentTrack.enabled = false;
            await micSender.replaceTrack(silentTrack);
            console.log("Replaced mic with silent track");
        }
        if (videoSender) {
            const blackCanvas = document.createElement('canvas');
            blackCanvas.width = 640;
            blackCanvas.height = 480;
            const bctx = blackCanvas.getContext('2d');
            bctx.fillStyle = 'black';
            bctx.fillRect(0, 0, 640, 480);
            const blackStream = blackCanvas.captureStream(1);
            const blackTrack = blackStream.getVideoTracks()[0];
            await videoSender.replaceTrack(blackTrack);
            console.log("Replaced webcam with black video");
        }

        // Stop local streams
        if (localCamStream) {
            localCamStream.getTracks().forEach(t => t.stop());
            localCamStream = null;
        }

        // Hide local preview
        const preview = document.getElementById('local-preview');
        if (preview) {
            preview.srcObject = null;
            preview.style.display = 'none';
        }

        // Tell server to stop telepresence
        await fetch('/telepresence/stop', { method: 'POST' });

        telepresenceActive = false;
        updateTelepresenceButton();
        console.log("=== TELEPRESENCE STOPPED ===");

    } catch (error) {
        console.error("Stop telepresence error:", error);
    }
}

function toggleTelepresence() {
    if (telepresenceActive) {
        stopTelepresence();
    } else {
        startTelepresence();
    }
}

function updateTelepresenceButton() {
    const btn = document.getElementById('telepresence-btn');
    if (!btn) return;
    if (telepresenceActive) {
        btn.textContent = '📹 End Telepresence';
        btn.classList.add('active');
    } else {
        btn.textContent = '📹 Start Telepresence';
        btn.classList.remove('active');
    }
}

window.addEventListener('load', () => {
    setTimeout(startWebRTC, 1000);
});
