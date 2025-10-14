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

  // Camera recording variables
  let mediaStream = null;
  let mediaRecorder = null;
  let recordedChunks = [];
  let isRecording = false;
  let recordingStartTime = null;
  let recordingTimerInterval = null;

  // --- CAMERA ALWAYS ENABLED ---
  async function initializeCamera() {
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1280 },
          height: { ideal: 720 },
          frameRate: { ideal: 30 },
        },
        audio: true,
      });

      cameraPreview.srcObject = mediaStream;
      cameraPreview.style.display = "block";
      cameraPlaceholder.style.display = "none";

      initializeMediaRecorder();
      console.log("🎥 Camera enabled automatically");
    } catch (error) {
      console.error("Error accessing camera:", error);
      appendMessage("ai", "Unable to access camera. Please check permissions.");
    }
  }

  function disableCamera() {
    if (mediaStream) {
      mediaStream.getTracks().forEach((track) => track.stop());
      mediaStream = null;
    }

    if (mediaRecorder && isRecording) {
      mediaRecorder.stop();
      isRecording = false;
    }

    stopRecordingTimer();
    recordingStatus.classList.add("hidden");
  }

  function initializeMediaRecorder() {
    if (!mediaStream) return;

    try {
      recordedChunks = [];
      mediaRecorder = new MediaRecorder(mediaStream, {
        mimeType: "video/webm;codecs=vp9,opus",
        videoBitsPerSecond: 2500000,
      });

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) recordedChunks.push(event.data);
      };

      mediaRecorder.onstop = handleRecordingStop;
    } catch (error) {
      console.error("MediaRecorder error:", error);
      try {
        mediaRecorder = new MediaRecorder(mediaStream, { mimeType: "video/webm" });
        mediaRecorder.ondataavailable = (event) => {
          if (event.data.size > 0) recordedChunks.push(event.data);
        };
        mediaRecorder.onstop = handleRecordingStop;
      } catch (fallbackError) {
        console.error("Fallback MediaRecorder also failed:", fallbackError);
      }
    }
  }

  function startRecording() {
    if (!mediaRecorder || mediaRecorder.state === "recording") return;
    recordedChunks = [];
    mediaRecorder.start(1000);
    isRecording = true;
    recordingStatus.classList.remove("hidden");
    startRecordingTimer();
    console.log("📹 Recording started");
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      isRecording = false;
      console.log("🛑 Recording stopped");
    }
    recordingStatus.classList.add("hidden");
    stopRecordingTimer();
  }

  function handleRecordingStop() {
    if (recordedChunks.length === 0) return;
    const blob = new Blob(recordedChunks, { type: "video/webm" });
    uploadRecording(blob);
  }

  async function uploadRecording(blob) {
    const formData = new FormData();
    formData.append("video", blob, `interview-${interviewId}-attempt-${attemptId}.webm`);
    formData.append("interview_id", interviewId);
    formData.append("attempt_id", attemptId);

    try {
      const response = await fetch("/upload-public-interview-video", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("Upload failed");

      const result = await response.json();
      console.log("✅ Video uploaded successfully:", result.video_url);
      appendMessage("ai", "Interview recording uploaded successfully!");
    } catch (error) {
      console.error("Error uploading video:", error);
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

  // --- EXISTING FUNCTIONS (unchanged) ---
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
      return;
    }

    window.speechSynthesis.cancel();

    return new Promise((resolve) => {
      const speech = new SpeechSynthesisUtterance(text);
      speech.rate = 0.9;
      speech.pitch = 1;
      speech.volume = 1;

      const voices = window.speechSynthesis.getVoices();
      if (voices.length > 0) {
        const ukFemaleVoice = voices.find(
          (voice) =>
            voice.name.toLowerCase().includes("google uk english female") ||
            (voice.lang === "en-GB" && voice.name.toLowerCase().includes("female")) ||
            (voice.lang === "en-GB" && voice.name.toLowerCase().includes("google"))
        );

        speech.voice = ukFemaleVoice || voices.find((v) => v.lang === "en-GB") || voices[0];
        speech.lang = "en-GB";
      }

      window.speechSynthesis.speak(speech);

      speech.onend = () => {
        startListening();
        resolve();
      };
    });
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

      // Start recording when listening starts
      if (!isRecording) startRecording();
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
      } catch {}
    }

    isListening = false;
    listeningIndicator.classList.add("hidden");
    micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Processing...';
    micBtn.classList.remove("btn-warning");
    micBtn.classList.add("btn-secondary");
    micBtn.disabled = true;

    // Stop recording when listening ends
    if (isRecording) stopRecording();
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
      await initializeCamera(); // 🎥 enable camera automatically

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
      appendMessage("ai", data.message);
      if (data.summary) appendMessage("ai", data.summary);
      micBtn.disabled = true;
      micBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Interview Completed';
      micBtn.classList.remove("btn-primary", "btn-warning", "btn-secondary");
      micBtn.classList.add("btn-success");
      stopListening();

      if (isRecording) stopRecording();
      disableCamera();

      setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) ws.close();
      }, 3000);
    }
  };

  ws.onclose = () => {
    statusEl.textContent = "Disconnected";
    statusDot.classList.remove("active");
    stopListening();
    if (isRecording) stopRecording();
    disableCamera();
  };

  window.addEventListener("beforeunload", () => {
    if (ws.readyState === WebSocket.OPEN) ws.close();
    if (recognition && isListening) recognition.stop();
    window.speechSynthesis.cancel();
    clearTimeout(silenceTimer);
    disableCamera();
  });
});
