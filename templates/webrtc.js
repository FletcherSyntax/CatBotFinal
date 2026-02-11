// WebRTC with telepresence toggle
let webrtcPC = null;
let telepresenceActive = false;
let localMicStream = null;
let micSender = null;

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
        // Add a silent audio track as placeholder (so the server knows to expect audio later)
        // This reserves the audio transceiver for telepresence
        const silentCtx = new AudioContext();
        const silentOsc = silentCtx.createOscillator();
        const silentDest = silentCtx.createMediaStreamDestination();
        silentOsc.connect(silentDest);
        silentOsc.start();
        const silentTrack = silentDest.stream.getAudioTracks()[0];
        silentTrack.enabled = false; // muted
        micSender = webrtcPC.addTrack(silentTrack, silentDest.stream);
        console.log("Added silent placeholder audio track");

        // Force H264 codec
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
        // Get real microphone
        localMicStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const micTrack = localMicStream.getAudioTracks()[0];
        console.log("Got mic:", micTrack.label);

        // Replace silent track with real mic
        if (micSender) {
            await micSender.replaceTrack(micTrack);
            console.log("Replaced silent track with real mic");
        }

        // Tell server to start playing incoming audio
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
        // Replace mic with silent track
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

        // Stop local mic
        if (localMicStream) {
            localMicStream.getTracks().forEach(t => t.stop());
            localMicStream = null;
        }

        // Tell server to stop playing audio
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
        btn.textContent = '🎙️ End Telepresence';
        btn.classList.add('active');
    } else {
        btn.textContent = '🎙️ Start Telepresence';
        btn.classList.remove('active');
    }
}

window.addEventListener('load', () => {
    setTimeout(startWebRTC, 1000);
});
