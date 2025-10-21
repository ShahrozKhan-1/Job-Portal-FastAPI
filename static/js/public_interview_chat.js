document.addEventListener("DOMContentLoaded", () => {
  const interviewId = document.getElementById("interview_id").textContent;
  const attemptId = document.getElementById("attempt_id").textContent;

  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/public-interview/${interviewId}?attempt_id=${attemptId}`;
  const ws = new WebSocket(wsUrl);

  // Elements
  const chatBox = document.getElementById("chat-box");
  const micBtn = document.getElementById("micBtn");
  const listeningIndicator = document.getElementById("listeningIndicator");
  const statusEl = document.getElementById("status");
  const statusDot = document.getElementById("statusDot");
  const cameraPreview = document.getElementById("cameraPreview");
  const cameraPlaceholder = document.getElementById("cameraPlaceholder");
  const recordingStatus = document.getElementById("recordingStatus");
  const recordingTimer = document.getElementById("recordingTimer");

  // State
  let recognition;
  let currentQuestion = null;
  let isListening = false;
  let interviewStarted = false;
  let interviewComplete = false;
  let speechSupported = false;
  let silenceTimer = null;
  let finalTranscript = "";
  let hasProcessedAnswer = false;
  let currentQuestionIndex = 0;
  let totalQuestions = "AI-driven";

  // Recording
  let mediaStream = null;
  let mediaRecorder = null;
  let recordedChunks = [];
  let mixedStream = null;
  let isRecording = false;
  let recordingStartTime = null;
  let recordingTimerInterval = null;

  // Audio mixing
  let audioContext = null;
  let microphoneSource = null;
  let destination = null;

  // Cached voice
  let cachedVoice = null;

  // --- INIT FUNCTIONS ---
  async function preloadVoices() {
    return new Promise((resolve) => {
      function load() {
        const voices = window.speechSynthesis.getVoices();
        if (voices.length > 0) {
          cachedVoice =
            voices.find(v => v.lang === "en-GB" && v.name.toLowerCase().includes("female")) ||
            voices.find(v => v.lang === "en-GB") ||
            voices[0];
          resolve();
        } else {
          window.speechSynthesis.onvoiceschanged = load;
        }
      }
      load();
    });
  }

  async function initMedia() {
    try {
      if (!mediaStream) {
        mediaStream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, frameRate: { ideal: 30 } },
          audio: { echoCancellation: true, noiseSuppression: true, sampleRate: 44100 },
        });
      }

      if (!audioContext) {
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        destination = audioContext.createMediaStreamDestination();
        microphoneSource = audioContext.createMediaStreamSource(mediaStream);
        microphoneSource.connect(destination);
      }

      mixedStream = new MediaStream([
        ...mediaStream.getVideoTracks(),
        ...destination.stream.getAudioTracks(),
      ]);

      cameraPreview.srcObject = mediaStream;
      cameraPreview.style.display = "block";
      cameraPlaceholder.style.display = "none";
      console.log("🎥 Camera + mic ready");
    } catch (error) {
      console.error("Camera error:", error);
      appendMessage("ai", "Unable to access camera or mic. Check permissions.");
    }
  }

  // --- RECORDING ---
  function initRecorder() {
    if (!mixedStream) return;
    recordedChunks = [];
    const mime = MediaRecorder.isTypeSupported("video/webm;codecs=vp9,opus")
      ? "video/webm;codecs=vp9,opus"
      : "video/webm";

    mediaRecorder = new MediaRecorder(mixedStream, { mimeType: mime, videoBitsPerSecond: 2500000 });

    mediaRecorder.ondataavailable = (e) => e.data.size > 0 && recordedChunks.push(e.data);
    mediaRecorder.onstop = handleRecordingStop;
    console.log("🎬 Recorder ready");
  }

  function startRecording() {
    if (mediaRecorder && mediaRecorder.state !== "recording") {
      mediaRecorder.start(1000);
      isRecording = true;
      recordingStatus.classList.remove("hidden");
      startRecordingTimer();
      console.log("📹 Recording started");
    }
  }

  function stopRecording() {
    if (mediaRecorder && mediaRecorder.state === "recording") {
      mediaRecorder.stop();
      isRecording = false;
      recordingStatus.classList.add("hidden");
      stopRecordingTimer();
      console.log("📹 Recording stopped");
    }
  }

  function handleRecordingStop() {
    const blob = new Blob(recordedChunks, { type: "video/webm" });
    if (blob.size > 0) {
      setTimeout(() => uploadRecording(blob), 1500); // slight delay for smooth UI
    } else {
      appendMessage("ai", "No recording data available.");
    }
  }

  async function uploadRecording(blob) {
    const formData = new FormData();
    formData.append("video", blob, `interview-${interviewId}-attempt-${attemptId}.webm`);
    formData.append("interview_id", interviewId);
    formData.append("attempt_id", attemptId);

    try {
      appendMessage("ai", "Uploading recording...");
      const response = await fetch("/upload-public-interview-video", { method: "POST", body: formData });
      if (!response.ok) throw new Error(`Upload failed: ${response.status}`);
      const result = await response.json();
      appendMessage("ai", "✅ Interview video uploaded!");
      console.log("Upload success:", result.video_url);
    } catch (err) {
      console.error("Upload error:", err);
      appendMessage("ai", "Upload failed. Please contact support.");
    }
  }

  function startRecordingTimer() {
    recordingStartTime = Date.now();
    recordingTimerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - recordingStartTime) / 1000);
      recordingTimer.textContent = `${String(Math.floor(elapsed / 60)).padStart(2, "0")}:${String(elapsed % 60).padStart(2, "0")}`;
    }, 1000);
  }

  function stopRecordingTimer() {
    clearInterval(recordingTimerInterval);
    recordingTimer.textContent = "00:00";
  }

  // --- SPEECH FUNCTIONS ---
  function appendMessage(sender, text) {
    const frag = document.createDocumentFragment();
    const div = document.createElement("div");
    div.className = sender === "ai" ? "ai-message" : "user-message";
    div.textContent = text;
    frag.appendChild(div);
    chatBox.appendChild(frag);
    chatBox.scrollTop = chatBox.scrollHeight;
  }

  function speakQuestion(text) {
    if (!speechSupported) return Promise.resolve();
    return new Promise((resolve) => {
      const utterance = new SpeechSynthesisUtterance(text);
      utterance.rate = 0.9;
      utterance.pitch = 1;
      utterance.voice = cachedVoice;
      utterance.lang = "en-GB";

      utterance.onend = () => setTimeout(() => { startListening(); resolve(); }, 100);
      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
    });
  }

  function startListening() {
    if (!recognition) {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) return alert("Speech recognition not supported.");
      recognition = new SR();
      recognition.lang = "en-US";
      recognition.interimResults = true;
      recognition.continuous = true;
    }

    if (isListening) return;
    recognition.abort();
    finalTranscript = "";
    hasProcessedAnswer = false;

    const hardTimeout = setTimeout(() => {
      if (!hasProcessedAnswer) {
        hasProcessedAnswer = true;
        stopListening();
        processAnswer("(no response detected)");
      }
    }, 8000);

    recognition.onstart = () => {
      isListening = true;
      listeningIndicator.classList.remove("hidden");
      micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Listening...';
      micBtn.classList.replace("btn-primary", "btn-warning");
    };

    recognition.onresult = (e) => {
      clearTimeout(silenceTimer);
      for (let i = e.resultIndex; i < e.results.length; ++i)
        if (e.results[i].isFinal) finalTranscript += e.results[i][0].transcript;
      silenceTimer = setTimeout(() => {
        if (!hasProcessedAnswer) {
          hasProcessedAnswer = true;
          stopListening();
          processAnswer(finalTranscript.trim() || "(no response detected)");
        }
      }, 1500);
    };

    recognition.onerror = () => {
      if (!hasProcessedAnswer) {
        hasProcessedAnswer = true;
        stopListening();
        processAnswer("(no response detected)");
      }
    };

    recognition.onend = () => {
      clearTimeout(hardTimeout);
      clearTimeout(silenceTimer);
      if (!hasProcessedAnswer) {
        hasProcessedAnswer = true;
        processAnswer(finalTranscript.trim() || "(no response detected)");
      }
      stopListening();
    };

    recognition.start();
  }

  function stopListening() {
    clearTimeout(silenceTimer);
    if (recognition && isListening) {
      try { recognition.stop(); } catch { }
    }
    isListening = false;
    listeningIndicator.classList.add("hidden");
    micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Processing...';
    micBtn.classList.replace("btn-warning", "btn-secondary");
    micBtn.disabled = true;
  }

  function processAnswer(transcript) {
    appendMessage("user", transcript);
    if (ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ answer: transcript }));
  }

  // --- WEBSOCKET HANDLERS ---
  ws.onopen = async () => {
    statusEl.textContent = "Connected - Interview Starting";
    statusDot.classList.add("active");
    speechSupported = "speechSynthesis" in window;

    // Parallel init (camera + voices)
    await Promise.all([initMedia(), preloadVoices()]);
    initRecorder();

    micBtn.disabled = true;
    micBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Starting...';
  };

  ws.onmessage = async (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === "welcome") {
      appendMessage("ai", data.message || "Welcome to your AI-powered interview!");
      if (data.instructions) {
        appendMessage("ai", data.instructions);
      }
      interviewStarted = true;
      setTimeout(startRecording, 1000);
      
    } else if (data.type === "question") {
      currentQuestion = data.question;
      currentQuestionIndex = data.index || currentQuestionIndex + 1;
      totalQuestions = data.total_questions || totalQuestions;
      
      // Format question display
      const questionPrefix = typeof data.index === 'number' ? 
        `Question ${data.index}:` : 
        `Question ${currentQuestionIndex}:`;
      
      appendMessage("ai", `${questionPrefix} ${currentQuestion}`);
      micBtn.disabled = true;
      
      // Speak the question
      await speakQuestion(currentQuestion);
      
    } else if (data.type === "ack") {
      appendMessage("ai", data.message);
      // Enable mic for next response
      micBtn.disabled = false;
      micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Start Speaking';
      micBtn.classList.replace("btn-secondary", "btn-primary");
      
    } else if (data.type === "timeout") {
      appendMessage("ai", data.message);
      // Re-enable mic for next question
      micBtn.disabled = false;
      micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Start Speaking';
      micBtn.classList.replace("btn-secondary", "btn-primary");
      
    } else if (data.type === "evaluation") {
      appendMessage("ai", "📊 Interview Evaluation Complete!");
      appendMessage("ai", `Score: ${data.score}/100`);
      appendMessage("ai", `Feedback: ${data.feedback}`);
      
    } else if (data.type === "complete") {
      interviewComplete = true;
      appendMessage("ai", data.message);
      
      if (data.total_questions) {
        appendMessage("ai", `Total questions asked: ${data.total_questions}`);
      }
      
      // Disable mic and update UI
      micBtn.disabled = true;
      micBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Interview Completed';
      micBtn.classList.remove("btn-primary", "btn-warning", "btn-secondary");
      micBtn.classList.add("btn-success");
      
      stopListening();
      stopRecording();
      
    } else if (data.type === "error") {
      appendMessage("ai", `Error: ${data.message}`);
      micBtn.disabled = true;
      micBtn.innerHTML = '<i class="bi bi-exclamation-triangle me-2"></i>Error';
      micBtn.classList.remove("btn-primary", "btn-warning", "btn-secondary");
      micBtn.classList.add("btn-danger");
    }
  };

  ws.onclose = () => {
    statusEl.textContent = "Disconnected";
    statusDot.classList.remove("active");
    stopListening();
    if (isRecording && !interviewComplete) stopRecording();
  };

  // --- EVENT LISTENERS ---
  micBtn.addEventListener("click", () => {
    if (!isListening && !interviewComplete) {
      startListening();
    }
  });

  // Add keyboard shortcut for mic (Space bar)
  document.addEventListener("keydown", (e) => {
    if (e.code === "Space" && !isListening && !interviewComplete && !e.target.matches("input, textarea")) {
      e.preventDefault();
      startListening();
    }
  });

  // --- CLEANUP ---
  window.addEventListener("beforeunload", () => {
    if (ws.readyState === WebSocket.OPEN) ws.close();
    if (recognition && isListening) recognition.stop();
    window.speechSynthesis.cancel();
    clearTimeout(silenceTimer);
    if (isRecording) stopRecording();
    if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
    if (audioContext) audioContext.close();
  });
});