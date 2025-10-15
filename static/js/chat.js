// ======================= CONFIG =======================
const applicantId = Number(document.getElementById("applicant_id").textContent);

let socket = null;
const chatBox = document.getElementById("chat-box");
const statusDiv = document.getElementById("status");
const statusDot = document.getElementById("statusDot");
const listeningIndicator = document.getElementById("listeningIndicator");
const micBtn = document.getElementById("micBtn");

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;
let isListening = false;
let currentAiMessage = "";
let silenceTimer = null;
let finalTranscript = "";
let speechRecognition = null;
let interviewStarted = false;

const cameraFeed = document.getElementById("cameraPreview");
const cameraStatus = document.getElementById("cameraPlaceholder");
let cameraStream = null;

// ======================= CAMERA =======================
async function startCamera() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    cameraFeed.srcObject = cameraStream;
    cameraFeed.style.display = "block";
    cameraStatus.style.display = "none";
    console.log("Camera started successfully!");
  } catch (error) {
    console.error("Camera error:", error);
    cameraStatus.innerHTML = "<p>Camera access denied or unavailable.</p>";
  }
}

function stopCamera() {
  if (cameraStream) {
    cameraStream.getTracks().forEach(track => track.stop());
    cameraStream = null;
  }
  cameraStatus.innerHTML = "<p>Camera stopped.</p>";
}

startCamera();

// ======================= VIDEO RECORDING =======================
let videoRecorder = null;
let recordedChunks = [];
let videoBlob = null;

function startVideoRecording() {
  if (!cameraStream) {
    console.warn("Camera not started yet.");
    return;
  }

  recordedChunks = [];
  videoRecorder = new MediaRecorder(cameraStream, { mimeType: "video/webm" });

  videoRecorder.ondataavailable = (event) => {
    if (event.data.size > 0) recordedChunks.push(event.data);
  };

  videoRecorder.onstop = () => {
    videoBlob = new Blob(recordedChunks, { type: "video/webm" });
    uploadVideoToCloudinary(videoBlob);
  };

  videoRecorder.start();
  console.log("🎥 Video recording started...");
}

function stopVideoRecording() {
  if (videoRecorder && videoRecorder.state !== "inactive") {
    videoRecorder.stop();
    console.log("🛑 Video recording stopped.");
  }
}

async function uploadVideoToCloudinary(blob) {
  const formData = new FormData();
  formData.append("applicant_id", applicantId);
  formData.append("video", blob, `interview_${applicantId}.webm`);

  try {
    console.log("📤 Uploading video to Cloudinary...");
    const response = await fetch("/upload-job-interview-video", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    if (response.ok && data.success) {
      console.log("✅ Video uploaded successfully:", data.video_url);
    } else {
      console.error("❌ Upload failed:", data.detail || data);
    }
  } catch (error) {
    console.error("🚨 Video upload error:", error);
  }
}

// ======================= TTS (British Female Voice) =======================
let ttsVoice = null;

function loadVoices() {
  const voices = window.speechSynthesis.getVoices();
  console.log("Available voices:", voices.map(v => v.name));

  ttsVoice =
    voices.find(v =>
      v.lang === "en-GB" &&
      /(female|Google UK English Female|Libby|Hazel)/i.test(v.name)
    ) ||
    voices.find(v => v.lang === "en-GB") ||
    voices.find(v => v.lang.startsWith("en"));
}

window.speechSynthesis.onvoiceschanged = loadVoices;
loadVoices();

async function speakText(text) {
  if (!text?.trim() || !("speechSynthesis" in window)) return;

  window.speechSynthesis.cancel();
  return new Promise((resolve) => {
    const utterance = new SpeechSynthesisUtterance(text.trim());
    utterance.rate = 0.9;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;
    if (ttsVoice) utterance.voice = ttsVoice;

    utterance.onend = () => resolve();
    utterance.onerror = () => resolve();
    window.speechSynthesis.speak(utterance);
  });
}

// ======================= HELPERS =======================
function sanitizeClassName(name) {
  return name.toLowerCase().replace(/[^a-z0-9_-]/g, "-");
}

function buildWebSocketUrl(applicantId) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const host =
    location.hostname === "localhost" || location.hostname === "127.0.0.1"
      ? "localhost:8000"
      : location.host;
  return `${proto}://${host}/ws/chat/${applicantId}`;
}

function addMessage(sender, text) {
  const wrap = document.createElement("div");
  const className = sanitizeClassName(sender);
  wrap.classList.add("message", className);

  const avatar = document.createElement("div");
  avatar.classList.add("avatar");
  avatar.innerHTML = sender.toLowerCase().includes("ai")
    ? '<i class="bi bi-robot"></i>'
    : '<i class="bi bi-person-fill"></i>';

  const bubble = document.createElement("div");
  bubble.classList.add("bubble");
  bubble.innerHTML = "<strong>" + sender + ":</strong> " + escapeHtml(text);

  if (sender.toLowerCase().includes("ai")) {
    wrap.appendChild(avatar);
    wrap.appendChild(bubble);
  } else {
    wrap.appendChild(bubble);
    wrap.appendChild(avatar);
  }

  chatBox.appendChild(wrap);
  chatBox.scrollTop = chatBox.scrollHeight;

  return wrap;
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function updateListeningUI(listening) {
  if (listening) {
    micBtn.classList.add("listening");
    micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Listening...';
    listeningIndicator.classList.remove("hidden");
  } else {
    micBtn.classList.remove("listening");
    micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Processing...';
    listeningIndicator.classList.add("hidden");
    micBtn.disabled = true;
  }
}

// ======================= SPEECH RECOGNITION =======================
function startListening() {
  if (!interviewStarted) return;

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    alert("Speech recognition not supported. Use Chrome or Edge.");
    return;
  }

  speechRecognition = new SpeechRecognition();
  speechRecognition.lang = "en-US";
  speechRecognition.interimResults = true;
  speechRecognition.continuous = true;
  speechRecognition.maxAlternatives = 1;

  finalTranscript = "";

  speechRecognition.onstart = () => {
    isListening = true;
    updateListeningUI(true);
  };

  speechRecognition.onresult = (event) => {
    clearTimeout(silenceTimer);

    let interimTranscript = "";

    for (let i = event.resultIndex; i < event.results.length; ++i) {
      if (event.results[i].isFinal) {
        finalTranscript += event.results[i][0].transcript;
      } else {
        interimTranscript += event.results[i][0].transcript;
      }
    }

    silenceTimer = setTimeout(() => {
      if (finalTranscript.trim() !== "") {
        processAnswer(finalTranscript);
      } else {
        stopListening();
      }
    }, 3000);
  };

  speechRecognition.onerror = () => stopListening();
  speechRecognition.onend = () => stopListening();

  try {
    speechRecognition.start();
  } catch {
    stopListening();
  }
}

function stopListening() {
  clearTimeout(silenceTimer);
  if (speechRecognition && isListening) {
    try {
      speechRecognition.stop();
    } catch {}
  }
  isListening = false;
  updateListeningUI(false);
}

function processAnswer(transcript) {
  addMessage("You", transcript);
  if (socket && socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ answer: transcript }));
  }
}

// ======================= WEBSOCKET =======================
function connectWebSocket() {
  socket = new WebSocket(buildWebSocketUrl(applicantId));

  socket.onopen = () => {
    statusDiv.textContent = "Connected - Interview Starting";
    statusDot.classList.remove("disconnected");
    statusDot.classList.add("connected");

    micBtn.disabled = true;
    micBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Starting...';

    // 🎥 Start video recording
    startVideoRecording();
  };

  socket.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);

      if (data.type === "welcome") {
        interviewStarted = true;
      } else if (data.type === "question") {
        currentAiMessage = data.question || data.message;

        if (currentAiMessage) {
          addMessage("AI", `${data.index}/${data.total_questions}: ${currentAiMessage}`);
          await speakText(`Question ${data.index}. ${currentAiMessage}`);

          setTimeout(() => {
            if (!isListening && interviewStarted) startListening();
          }, 1000);
        }
      } else if (data.type === "ack") {
        micBtn.disabled = false;
        micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Start Speaking';
        micBtn.classList.remove("listening");
      } else if (data.type === "complete") {
        addMessage("AI", data.message);
        if (data.summary) addMessage("AI", data.summary);

        micBtn.disabled = true;
        micBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Interview Completed';
        micBtn.classList.remove("listening");

        stopListening();
        stopVideoRecording();

        setTimeout(() => {
          if (socket.readyState === WebSocket.OPEN) socket.close();
        }, 3000);
      } else if (data.type === "error") {
        addMessage("AI", data.message);
        micBtn.disabled = true;
      }

      chatBox.scrollTop = chatBox.scrollHeight;
    } catch (err) {
      console.error("Error processing WebSocket message:", err);
    }
  };

  socket.onclose = () => {
    statusDiv.textContent = "Interview ended";
    statusDot.classList.remove("connected");
    statusDot.classList.add("disconnected");
    addMessage("AI", "Interview completed. Thank you!");

    stopListening();
    stopVideoRecording();

    setTimeout(() => {
      window.location.href = "/dashboard";
    }, 5000);
  };

  socket.onerror = () => {
    statusDiv.textContent = "Connection error";
    statusDot.classList.remove("connected");
    statusDot.classList.add("disconnected");
  };
}

connectWebSocket();

// ======================= BUTTONS & CLEANUP =======================
micBtn.addEventListener("click", () => {
  if (isListening) stopListening();
  else startListening();
});

window.addEventListener("beforeunload", () => {
  if (socket) socket.close();
  if (speechRecognition && isListening) speechRecognition.stop();
  if (silenceTimer) clearTimeout(silenceTimer);
  window.speechSynthesis.cancel();
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden && isListening) stopListening();
});
