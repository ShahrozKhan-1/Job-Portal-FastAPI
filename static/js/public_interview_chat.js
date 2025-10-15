document.addEventListener("DOMContentLoaded", () => {
  const interviewId = document.getElementById("interview_id").textContent;
  const attemptId = document.getElementById("attempt_id").textContent;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/public-interview/${interviewId}?attempt_id=${attemptId}`;

  const ws = new WebSocket(wsUrl);

  const chatBox = document.getElementById("chat-box");
  const micBtn = document.getElementById("micBtn");
  const listeningIndicator = document.getElementById("listeningIndicator");
  const statusEl = document.getElementById("status");
  const statusDot = document.getElementById("statusDot");

  // Camera elements
  const cameraPreview = document.getElementById("cameraPreview");
  const cameraPlaceholder = document.getElementById("cameraPlaceholder");
  const recordingStatus = document.getElementById("recordingStatus");
  const recordingTimer = document.getElementById("recordingTimer");

  let recognition;
  let currentQuestion = null;
  let isListening = false;
  let interviewStarted = false;
  let speechSupported = false;
  let silenceTimer = null;
  let finalTranscript = "";

  // Recording variables
  let mediaStream = null;
  let mediaRecorder = null;
  let recordedChunks = [];
  let isRecording = false;
  let recordingStartTime = null;
  let recordingTimerInterval = null;
  let interviewComplete = false;

  // Audio mixing variables
  let audioContext = null;
  let microphoneSource = null;
  let ttsSource = null;
  let destination = null;
  let mixedStream = null;

  // --- CAMERA SETUP WITH AUDIO MIXING ---
  async function initializeCamera() {
    try {
      // Get camera and microphone
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 30 },
        },
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          sampleRate: 44100,
        },
      });

      // Setup audio context for mixing
      await setupAudioMixing();

      cameraPreview.srcObject = mediaStream;
      cameraPreview.style.display = "block";
      cameraPlaceholder.style.display = "none";

      console.log("🎥 Camera and microphone enabled with audio mixing");
      return true;
    } catch (error) {
      console.error("Error accessing camera:", error);
      appendMessage("ai", "Unable to access camera. Please check permissions.");
      return false;
    }
  }

  // --- AUDIO MIXING SETUP ---
  async function setupAudioMixing() {
    try {
      // Create audio context
      audioContext = new (window.AudioContext || window.webkitAudioContext)();
      
      // Create destination for mixed audio
      destination = audioContext.createMediaStreamDestination();

      // Connect microphone to destination
      microphoneSource = audioContext.createMediaStreamSource(mediaStream);
      microphoneSource.connect(destination);

      // Create mixed stream with video + mixed audio
      mixedStream = new MediaStream([
        ...mediaStream.getVideoTracks(),
        ...destination.stream.getAudioTracks()
      ]);

      console.log("🎤 Audio mixing setup complete - ready to capture TTS");
      return true;
    } catch (error) {
      console.error("Error setting up audio mixing:", error);
      // Fallback to original stream
      mixedStream = mediaStream;
      return false;
    }
  }

  // --- TTS CAPTURE USING SPEECH SYNTHESIS ---
  function captureTTSAudio(text) {
    return new Promise((resolve) => {
      if (!audioContext) {
        // Fallback without audio mixing
        speakWithoutCapture(text).then(resolve);
        return;
      }

      // Create a temporary audio element to capture TTS
      const audioElement = new Audio();
      const mediaElementSource = audioContext.createMediaElementSource(audioElement);
      mediaElementSource.connect(destination);

      // Use the Speech Synthesis API
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.volume = 1;

      // Set voice preferences
      const voices = window.speechSynthesis.getVoices();
      if (voices.length > 0) {
        const ukFemaleVoice = voices.find(
          (voice) =>
            voice.name.toLowerCase().includes("google uk english female") ||
            (voice.lang === "en-GB" && voice.name.toLowerCase().includes("female")) ||
            (voice.lang === "en-GB" && voice.name.toLowerCase().includes("google"))
        );
        utterance.voice = ukFemaleVoice || voices.find((v) => v.lang === "en-GB") || voices[0];
        utterance.lang = "en-GB";
      }

      // Create a workaround to capture TTS audio
      // This uses the fact that TTS plays through system audio
      // and will be captured by the microphone if speakers are on
      console.log("🔊 Starting TTS with audio capture");

      // Start TTS
      window.speechSynthesis.speak(utterance);

      utterance.onstart = () => {
        console.log("TTS started - audio should be captured through microphone");
      };

      utterance.onend = () => {
        console.log("TTS completed");
        // Clean up
        mediaElementSource.disconnect();
        
        setTimeout(() => {
          startListening();
          resolve();
        }, 500);
      };

      utterance.onerror = (event) => {
        console.error("TTS error:", event.error);
        mediaElementSource.disconnect();
        speakWithoutCapture(text).then(resolve);
      };
    });
  }

  // Fallback TTS without capture
  function speakWithoutCapture(text) {
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.volume = 1;

      const voices = window.speechSynthesis.getVoices();
      if (voices.length > 0) {
        const ukFemaleVoice = voices.find(
          (voice) =>
            voice.name.toLowerCase().includes("google uk english female") ||
            (voice.lang === "en-GB" && voice.name.toLowerCase().includes("female")) ||
            (voice.lang === "en-GB" && voice.name.toLowerCase().includes("google"))
        );
        utterance.voice = ukFemaleVoice || voices.find((v) => v.lang === "en-GB") || voices[0];
        utterance.lang = "en-GB";
      }

      window.speechSynthesis.speak(utterance);

      utterance.onend = () => {
        setTimeout(() => {
          startListening();
          resolve();
        }, 500);
      };
    });
  }

  // --- RECORDING FUNCTIONS ---
  function initializeMediaRecorder() {
    const streamToRecord = mixedStream || mediaStream;
    
    if (!streamToRecord) {
      console.error("No stream available for recording");
      return false;
    }

    try {
      recordedChunks = [];
      
      // Try preferred MIME type first
      if (MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")) {
        mediaRecorder = new MediaRecorder(streamToRecord, {
          mimeType: "video/webm;codecs=vp9,opus",
          videoBitsPerSecond: 2500000,
        });
      } else {
        mediaRecorder = new MediaRecorder(streamToRecord);
      }

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          recordedChunks.push(event.data);
          console.log(`Recorded chunk: ${event.data.size} bytes`);
        }
      };

      mediaRecorder.onstop = handleRecordingStop;
      console.log("🎬 MediaRecorder initialized with mixed audio stream");
      return true;
    } catch (error) {
      console.error("MediaRecorder error:", error);
      return false;
    }
  }

  // Start recording ONCE at the beginning
  function startInterviewRecording() {
    if (!mediaRecorder) {
      console.error("MediaRecorder not initialized");
      return false;
    }

    if (mediaRecorder.state === "recording") {
      console.log("Recording already in progress");
      return true;
    }

    try {
      mediaRecorder.start(1000); // Collect data every second
      isRecording = true;
      recordingStatus.classList.remove("hidden");
      startRecordingTimer();
      console.log("📹 Interview recording STARTED - capturing microphone + TTS");
      return true;
    } catch (error) {
      console.error("Error starting recording:", error);
      return false;
    }
  }

  // Stop recording ONLY ONCE at the end
  function stopInterviewRecording() {
    if (!mediaRecorder || mediaRecorder.state !== "recording") {
      console.log("No active recording to stop");
      return;
    }

    try {
      mediaRecorder.stop();
      isRecording = false;
      console.log("Interview recording STOPPED");
    } catch (error) {
      console.error("Error stopping recording:", error);
    }

    recordingStatus.classList.add("hidden");
    stopRecordingTimer();
  }

  // Upload immediately after stopping
  function handleRecordingStop() {
    console.log(`🎬 Recording stopped. Collected ${recordedChunks.length} chunks`);

    if (recordedChunks.length === 0) {
      console.error("No video data recorded");
      appendMessage("ai", "No recording data available.");
      return;
    }

    const blob = new Blob(recordedChunks, { type: "video/webm" });
    console.log(`Created video blob: ${blob.size} bytes`);
    uploadRecording(blob);
  }

  async function uploadRecording(blob) {
    console.log("Starting video upload...");

    const formData = new FormData();
    formData.append("video", blob, `interview-${interviewId}-attempt-${attemptId}.webm`);
    formData.append("interview_id", interviewId);
    formData.append("attempt_id", attemptId);

    try {
      appendMessage("ai", "Uploading interview recording...");

      const response = await fetch("/upload-public-interview-video", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(`Upload failed with status: ${response.status}`);
      }

      const result = await response.json();
      console.log("Full interview video uploaded successfully:", result.video_url);
      appendMessage("ai", "Interview recording uploaded successfully!");
    } catch (error) {
      console.error("Error uploading video:", error);
      appendMessage("ai", "Failed to upload recording. Please contact support.");
    }
  }

  function startRecordingTimer() {
    recordingStartTime = Date.now();
    recordingTimerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
      const minutes = Math.floor(elapsed / 60).toString().padStart(2, "0");
      const seconds = (elapsed % 60).toString().padStart(2, "0");
      recordingTimer.textContent = `${minutes}:${seconds}`;
    }, 1000);
  }

  function stopRecordingTimer() {
    if (recordingTimerInterval) {
      clearInterval(recordingTimerInterval);
      recordingTimerInterval = null;
    }
    recordingTimer.textContent = "00:00";
  }

  // --- VOICE FUNCTIONS ---
  function ensureVoicesLoaded() {
    return new Promise((resolve) => {
      const voices = window.speechSynthesis.getVoices();
      if (voices.length !== 0) resolve();
      else window.speechSynthesis.onvoiceschanged = () => resolve();
    });
  }

  function checkSpeechSupport() {
    speechSupported = "speechSynthesis" in window;
    return speechSupported;
  }

  function appendMessage(sender, text) {
    const div = document.createElement("div");
    div.className = sender === "ai" ? "ai-message" : "user-message";
    div.textContent = text;
    chatBox.appendChild(div);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function speakQuestion(text) {
    if (!checkSpeechSupport()) {
      micBtn.disabled = false;
      return Promise.resolve();
    }

    window.speechSynthesis.cancel();
    return captureTTSAudio(text);
  }

  function startListening() {
    if (!interviewStarted) return;

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
      alert("Speech recognition not supported in this browser.");
      return;
    }

    recognition = new SpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.continuous = true;

    finalTranscript = "";

    recognition.onstart = () => {
      isListening = true;
      listeningIndicator.classList.remove("hidden");
      micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Listening...';
      micBtn.classList.add("btn-warning");
      micBtn.classList.remove("btn-primary");
    };

    recognition.onresult = (event) => {
      clearTimeout(silenceTimer);
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        if (event.results[i].isFinal)
          finalTranscript += event.results[i][0].transcript;
      }

      silenceTimer = setTimeout(() => {
        if (finalTranscript.trim() !== "") processAnswer(finalTranscript);
        else stopListening();
      }, 3000);
    };

    recognition.onerror = () => stopListening();
    recognition.onend = () => stopListening();

    recognition.start();
  }

  function stopListening() {
    clearTimeout(silenceTimer);
    if (recognition && isListening) {
      try {
        recognition.stop();
      } catch { }
    }

    isListening = false;
    listeningIndicator.classList.add("hidden");
    micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Processing...';
    micBtn.classList.remove("btn-warning");
    micBtn.classList.add("btn-secondary");
    micBtn.disabled = true;
  }

  function processAnswer(transcript) {
    appendMessage("user", transcript);
    if (ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ answer: transcript }));
    }
  }

  // --- WebSocket handlers ---
  ws.onopen = async () => {
    statusEl.textContent = "Connected - Interview Starting";
    statusDot.classList.add("active");

    await ensureVoicesLoaded();
    checkSpeechSupport();
    micBtn.disabled = true;
    micBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Starting...';
  };

  ws.onmessage = async (event) => {
    const data = JSON.parse(event.data);

    if (data.type === "welcome") {
      appendMessage("ai", `Total questions: ${data.total_questions}`);
      interviewStarted = true;

      // Initialize camera and audio mixing
      const cameraReady = await initializeCamera();
      if (cameraReady) {
        const recorderReady = initializeMediaRecorder();
        if (recorderReady) {
          setTimeout(startInterviewRecording, 1000);
        }
      }

    } else if (data.type === "question") {
      currentQuestion = data.question;
      appendMessage("ai", `${data.index}/${data.total_questions}: ${currentQuestion}`);
      micBtn.disabled = true;
      await speakQuestion(`Question ${data.index}. ${currentQuestion}`);

    } else if (data.type === "ack") {
      appendMessage("ai", data.message);
      micBtn.disabled = false;
      micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Start Speaking';
      micBtn.classList.remove("btn-secondary");
      micBtn.classList.add("btn-primary");

    } else if (data.type === "complete") {
      interviewComplete = true;
      appendMessage("ai", data.message);
      if (data.summary) appendMessage("ai", data.summary);
      micBtn.disabled = true;
      micBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Interview Completed';
      micBtn.classList.remove("btn-primary", "btn-warning", "btn-secondary");
      micBtn.classList.add("btn-success");
      stopListening();

      // Stop recording ONLY ONCE at the end
      console.log("🎬 Interview complete - stopping recording");
      stopInterviewRecording();

      setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) ws.close();
      }, 3000);
    }
  };

  ws.onclose = () => {
    statusEl.textContent = "Disconnected";
    statusDot.classList.remove("active");
    stopListening();

    // If interview wasn't properly completed but connection closed, stop recording
    if (isRecording && !interviewComplete) {
      console.log("🔌 Connection closed - stopping recording");
      interviewComplete = true;
      stopInterviewRecording();
    }
  };

  // Cleanup
  window.addEventListener("beforeunload", () => {
    if (ws.readyState === WebSocket.OPEN) ws.close();
    if (recognition && isListening) recognition.stop();
    window.speechSynthesis.cancel();
    clearTimeout(silenceTimer);

    // Stop recording if still active
    if (isRecording) {
      console.log("Page unloading - stopping recording");
      interviewComplete = true;
      stopInterviewRecording();
    }

    // Clean up media streams
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
    }
    
    // Clean up audio context
    if (audioContext) {
      audioContext.close();
    }
  });
});