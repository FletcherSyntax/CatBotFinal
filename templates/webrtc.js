// WebRTC with full ICE debugging
let webrtcPC = null;

async function startWebRTC() {
    console.log("=== Starting WebRTC ===");

    // Fetch TURN config from server
    const iceResponse = await fetch('/ice-config');
    const iceConfig = await iceResponse.json();

    webrtcPC = new RTCPeerConnection(iceConfig);

    // Log ALL ICE candidates
    webrtcPC.onicecandidate = (event) => {
        if (event.candidate) {
            console.log("ICE candidate:", event.candidate.candidate);
        } else {
            console.log("ICE gathering complete");
        }
    };

    // Handle incoming tracks (video AND audio from Pi)
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
        // Get browser microphone
        try {
            const localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
            localStream.getAudioTracks().forEach(track => {
                webrtcPC.addTrack(track, localStream);
                console.log("Added browser mic track to peer connection");
            });
        } catch (micError) {
            console.warn("Could not access microphone:", micError);
        }

        console.log("Creating offer...");

// Force H264 codec
        const videoTransceiver = webrtcPC.addTransceiver('video', { direction: 'recvonly' });
        const codecs = RTCRtpReceiver.getCapabilities('video').codecs;
        const h264Codecs = codecs.filter(c => c.mimeType === 'video/H264');
        if (h264Codecs.length > 0) {
            videoTransceiver.setCodecPreferences(h264Codecs);
            console.log("Forced H264 codec preference");
        }

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
        console.log("Answer SDP:", answer.sdp.substring(0, 200) + "...");

        await webrtcPC.setRemoteDescription(answer);
        console.log("Remote description set!");

    } catch (error) {
        console.error("!!! WebRTC ERROR:", error);
    }
}

window.addEventListener('load', () => {
    setTimeout(startWebRTC, 1000);
});
