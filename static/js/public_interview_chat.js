class PublicInterviewChat {
  constructor() {
    this.ws = null;
    this.mediaRecorder = null;
    this.audioChunks = [];
    this.isRecording = false;
    this.stream = null;
    this.cameraStream = null;
    this.startTime = null;
    this.timerInterval = null;
    this.silenceTimer = null;
    this.silenceThreshold = 0.3;
    this.silenceDuration = 1500;
    this.currentUserMsg = null; // 🆕 track current user message

    // Elements
    this.interviewId = document.getElementById("interview_id")?.textContent?.trim();
    this.attemptId = document.getElementById("attempt_id")?.textContent?.trim();
    this.statusEl = document.getElementById("status");
    this.statusDot = document.getElementById("statusDot");
    this.chatBox = document.getElementById("chat-box");
    this.voiceStatus = document.getElementById("voiceStatus");
    this.waveformBars = document.getElementById("waveformBars");
    this.recordingTimer = document.getElementById("recordingTimer");
    this.recordingStatus = document.getElementById("recordingStatus");
    this.cameraPreview = document.getElementById("cameraPreview");
    this.cameraPlaceholder = document.getElementById("cameraPlaceholder");

    this.init();
  }

  async init() {
    await this.setupCamera();
    await this.setupMicrophone();
    this.connectWebSocket();
  }

  // 🎥 Camera setup
  async setupCamera() {
    try {
      this.cameraStream = await navigator.mediaDevices.getUserMedia({ video: true });
      this.cameraPreview.srcObject = this.cameraStream;
      this.cameraPlaceholder.style.display = "none";
    } catch (error) {
      console.warn("Camera unavailable:", error);
      this.cameraPlaceholder.style.display = "flex";
    }
  }

  // 🎤 Microphone + waveform setup
  async setupMicrophone() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      this.audioContext = new AudioContext();
      this.source = this.audioContext.createMediaStreamSource(this.stream);
      this.analyser = this.audioContext.createAnalyser();
      this.source.connect(this.analyser);
      this.dataArray = new Float32Array(this.analyser.fftSize);

      const updateWaveform = () => {
        this.analyser.getFloatTimeDomainData(this.dataArray);
        const rms = Math.sqrt(this.dataArray.reduce((s, a) => s + a * a, 0) / this.dataArray.length);
        const scale = Math.min(1.5, rms * 10);
        this.waveformBars.querySelectorAll(".bar").forEach(bar => {
          bar.style.height = `${10 + Math.random() * 80 * scale}px`;
        });
        requestAnimationFrame(updateWaveform);
      };
      updateWaveform();
    } catch (err) {
      console.error("Mic setup error:", err);
    }
  }

  // 🌐 WebSocket connection
  connectWebSocket() {
    const wsUrl = `${location.origin.replace("http", "ws")}/ws/public-interview/${this.interviewId}?attempt_id=${this.attemptId}`;
    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      this.updateStatus("Connected", "green");
      this.addMessage("system", "Interview session connected. Please wait for the first question...");
    };

    this.ws.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      console.log("📩 WS Message:", data);

      switch (data.type) {
        case "question":
          await this.handleQuestion(data);
          break;

        case "user_transcript":
          this.updateUserMessage(data.text);
          break;

        case "evaluation_start":
          this.addMessage("system", "Evaluating your performance...");
          break;

        case "evaluation":
          this.addMessage("ai", `Score: ${data.score}\nFeedback: ${data.feedback}`);
          break;

        case "complete":
          this.addMessage("system", data.message);
          this.stopTimer();
          break;

        case "error":
          this.addMessage("error", data.message);
          this.updateStatus("Error", "red");
          break;
      }
    };

    this.ws.onclose = () => {
      this.updateStatus("Disconnected", "gray");
      this.stopTimer();
    };
  }

  // 🎧 Handle AI question
  async handleQuestion(data) {
    const { text, audio } = data;
    this.addMessage("ai", text);

    if (audio) {
      const audioBlob = await this.base64ToBlob(audio);
      const audioUrl = URL.createObjectURL(audioBlob);
      const audioPlayer = new Audio(audioUrl);
      audioPlayer.play();

      audioPlayer.onended = () => this.startRecording();
    } else {
      this.startRecording();
    }
  }

  // 🎙️ Start recording
  startRecording() {
    if (this.isRecording || !this.stream) return;

    this.audioChunks = [];
    this.mediaRecorder = new MediaRecorder(this.stream);
    this.mediaRecorder.ondataavailable = (e) => this.audioChunks.push(e.data);
    this.mediaRecorder.onstop = async () => {
      const audioBlob = new Blob(this.audioChunks, { type: "audio/webm" });
      const base64Audio = await this.blobToBase64(audioBlob);

      // 🧠 Show “Processing…” placeholder for user
      this.currentUserMsg = this.addMessage("user", "Processing your response...");
      this.ws.send(JSON.stringify({ audio: base64Audio }));
      this.voiceStatus.querySelector(".status-label").textContent = "Processing...";
    };

    this.isRecording = true;
    this.startTimer();
    this.voiceStatus.querySelector(".status-label").textContent = "Listening...";
    this.recordingStatus.classList.remove("hidden");
    this.mediaRecorder.start();

    this.monitorSilence();
  }

  // 🕵️ Silence detection logic
  monitorSilence() {
    let userHasSpoken = false;
    let noSpeechTimer = setTimeout(() => {
      if (!userHasSpoken) {
        console.log("⏱️ No speech detected for 8s, stopping recording...");
        this.stopRecording();
      }
    }, 8000);

    const checkSilence = () => {
      this.analyser.getFloatTimeDomainData(this.dataArray);
      const rms = Math.sqrt(this.dataArray.reduce((s, a) => s + a * a, 0) / this.dataArray.length);

      if (rms > this.silenceThreshold) {
        userHasSpoken = true;
        clearTimeout(noSpeechTimer);
        clearTimeout(this.silenceTimer);
        this.silenceTimer = null;
      } else if (userHasSpoken) {
        if (!this.silenceTimer) {
          this.silenceTimer = setTimeout(() => {
            console.log("🔇 Silence detected after speech, stopping recording...");
            this.stopRecording();
          }, this.silenceDuration);
        }
      }

      if (this.isRecording) requestAnimationFrame(checkSilence);
    };

    checkSilence();
  }

  stopRecording() {
    if (this.isRecording && this.mediaRecorder.state !== "inactive") {
      this.mediaRecorder.stop();
      this.isRecording = false;
      this.stopTimer();
      this.recordingStatus.classList.add("hidden");
      clearTimeout(this.silenceTimer);
      this.silenceTimer = null;
    }
  }

  // 🧮 Timer logic
  startTimer() {
    this.startTime = Date.now();
    this.timerInterval = setInterval(() => {
      const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
      const mins = String(Math.floor(elapsed / 60)).padStart(2, "0");
      const secs = String(elapsed % 60).padStart(2, "0");
      this.recordingTimer.textContent = `${mins}:${secs}`;
    }, 1000);
  }

  stopTimer() {
    clearInterval(this.timerInterval);
    this.recordingTimer.textContent = "00:00";
  }

  // 💬 Add message to chat
  addMessage(sender, text) {
    const msg = document.createElement("div");
    msg.classList.add("message");
    if (sender === "ai") msg.classList.add("ai-message");
    else if (sender === "system") msg.classList.add("system-message");
    else if (sender === "error") msg.classList.add("error-message");
    else msg.classList.add("user-message");

    const label = document.createElement("span");
    label.classList.add("message-label");
    label.textContent = sender === "ai" ? "AI" : sender === "system" ? "System" : sender === "error" ? "Error" : "You";

    const textEl = document.createElement("p");
    textEl.textContent = text;

    msg.appendChild(label);
    msg.appendChild(textEl);
    this.chatBox.appendChild(msg);
    this.chatBox.scrollTop = this.chatBox.scrollHeight;

    return textEl; // 🆕 return the text element for updating later
  }

  // 🆕 Update user message with final STT text
  updateUserMessage(finalText) {
    if (this.currentUserMsg) {
      this.currentUserMsg.textContent = finalText;
      this.currentUserMsg = null;
    } else {
      this.addMessage("user", finalText);
    }
  }

  updateStatus(text, color) {
    this.statusEl.textContent = text;
    this.statusDot.style.background = color;
  }

  // 🧩 Utils
  async blobToBase64(blob) {
    return new Promise((resolve) => {
      const reader = new FileReader();
      reader.onloadend = () => resolve(reader.result.split(",")[1]);
      reader.readAsDataURL(blob);
    });
  }

  async base64ToBlob(base64) {
    const binary = atob(base64);
    const array = Uint8Array.from(binary, (c) => c.charCodeAt(0));
    return new Blob([array], { type: "audio/mp3" });
  }
}

document.addEventListener("DOMContentLoaded", () => new PublicInterviewChat());
