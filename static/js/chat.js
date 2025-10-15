// ======================= CONFIG =======================
const applicantId = Number(document.getElementById("applicant_id").textContent);

const chatBox = document.getElementById("chat-box");
const statusDiv = document.getElementById("status");
const statusDot = document.getElementById("statusDot");
const listeningIndicator = document.getElementById("listeningIndicator");
const micBtn = document.getElementById("micBtn");
const cameraFeed = document.getElementById("cameraPreview");
const cameraStatus = document.getElementById("cameraPlaceholder");

let socket = null;
let mediaRecorder = null;
let speechRecognition = null;
let cameraStream = null;
let videoRecorder = null;
let videoBlob = null;
let recordedChunks = [];
let isListening = false;
let interviewStarted = false;
let silenceTimer = null;
let finalTranscript = "";

// ======================= CAMERA =======================
async function startCamera() {
  try {
    cameraStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
    cameraFeed.srcObject = cameraStream;
    cameraFeed.style.display = "block";
    cameraStatus.style.display = "none";
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
function startVideoRecording() {
  if (!cameraStream) return;
  recordedChunks = [];
  videoRecorder = new MediaRecorder(cameraStream, { mimeType: "video/webm" });

  videoRecorder.ondataavailable = e => e.data.size > 0 && recordedChunks.push(e.data);
  videoRecorder.onstop = () => {
    videoBlob = new Blob(recordedChunks, { type: "video/webm" });
    uploadVideoToCloudinary(videoBlob);
  };

  videoRecorder.start();
}

function stopVideoRecording() {
  if (videoRecorder && videoRecorder.state !== "inactive") videoRecorder.stop();
}

async function uploadVideoToCloudinary(blob) {
  const formData = new FormData();
  formData.append("applicant_id", applicantId);
  formData.append("video", blob, `interview_${applicantId}.webm`);

  try {
    const res = await fetch("/upload-job-interview-video", { method: "POST", body: formData });
    const data = await res.json();
    console.log(res.ok ? "✅ Video uploaded:" : "❌ Upload failed:", data);
  } catch (err) {
    console.error("🚨 Upload error:", err);
  }
}

// ======================= TTS (FAST BRITISH VOICE) =======================
let ttsVoice = null;

function loadVoices() {
  const voices = window.speechSynthesis.getVoices();
  ttsVoice =
    voices.find(v => v.lang === "en-GB" && /(female|Google UK English Female|Libby|Hazel)/i.test(v.name)) ||
    voices.find(v => v.lang === "en-GB") ||
    voices.find(v => v.lang.startsWith("en"));
}
window.speechSynthesis.onvoiceschanged = loadVoices;
loadVoices();

function speakText(text) {
  if (!text?.trim() || !("speechSynthesis" in window)) return Promise.resolve();
  window.speechSynthesis.cancel();

  return new Promise(resolve => {
    const utter = new SpeechSynthesisUtterance(text.trim());
    utter.rate = 0.93; // Slightly faster for smoother pacing
    utter.pitch = 1.0;
    utter.volume = 1;
    if (ttsVoice) utter.voice = ttsVoice;
    utter.onend = resolve;
    utter.onerror = resolve;
    window.speechSynthesis.speak(utter);
  });
}

// ======================= HELPERS =======================
function addMessage(sender, text) {
  const msg = document.createElement("div");
  msg.className = `message ${sender === "AI" ? "ai" : "user"}`;
  msg.innerHTML = `<strong>${sender}:</strong> ${escapeHtml(text)}`;
  chatBox.appendChild(msg);
  chatBox.scrollTop = chatBox.scrollHeight;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, m => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"
  }[m]));
}

function updateListeningUI(listening, processing = false) {
  if (processing) {
    micBtn.innerHTML = '<i class="bi bi-hourglass-split me-2"></i>Processing...';
    micBtn.disabled = true;
  } else if (listening) {
    micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Listening...';
    micBtn.disabled = false;
  } else {
    micBtn.innerHTML = '<i class="bi bi-mic-fill me-2"></i>Start Speaking';
    micBtn.disabled = false;
  }
}

// ======================= SPEECH RECOGNITION =======================
function startListening() {
  if (!interviewStarted || isListening) return;
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return alert("Speech recognition not supported. Use Chrome or Edge.");

  speechRecognition = new SpeechRecognition();
  speechRecognition.lang = "en-US";
  speechRecognition.interimResults = true;
  speechRecognition.continuous = true;
  finalTranscript = "";
  isListening = true;
  updateListeningUI(true);

  speechRecognition.onresult = (e) => {
    clearTimeout(silenceTimer);
    for (let i = e.resultIndex; i < e.results.length; ++i)
      if (e.results[i].isFinal) finalTranscript += e.results[i][0].transcript;
    silenceTimer = setTimeout(() => {
      stopListening();
      if (finalTranscript.trim()) processAnswer(finalTranscript);
    }, 2000);
  };

  speechRecognition.onerror = () => stopListening();
  speechRecognition.onend = () => stopListening();
  speechRecognition.start();
}

function stopListening() {
  clearTimeout(silenceTimer);
  if (speechRecognition && isListening) {
    try { speechRecognition.stop(); } catch {}
  }
  isListening = false;
  updateListeningUI(false, true);
}

function processAnswer(text) {
  addMessage("You", text);
  if (socket?.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify({ answer: text }));
  }
  updateListeningUI(false, true);
}

// ======================= WEBSOCKET =======================
function buildWebSocketUrl(id) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const host =
    ["localhost", "127.0.0.1"].includes(location.hostname)
      ? "localhost:8000"
      : location.host;
  return `${proto}://${host}/ws/chat/${id}`;
}

function connectWebSocket() {
  socket = new WebSocket(buildWebSocketUrl(applicantId));

  socket.onopen = () => {
    statusDiv.textContent = "Connected - Interview Starting";
    statusDot.className = "connected";
    startVideoRecording();
  };

  socket.onmessage = async (event) => {
    try {
      const data = JSON.parse(event.data);
      if (data.type === "welcome") interviewStarted = true;

      else if (data.type === "question") {
        addMessage("AI", `${data.index}/${data.total_questions}: ${data.question}`);
        await speakText(`Question ${data.index}. ${data.question}`);
        startListening();
      }

      else if (data.type === "ack") updateListeningUI(false);

      else if (data.type === "complete") {
        addMessage("AI", data.message);
        if (data.summary) addMessage("AI", data.summary);
        stopListening();
        stopVideoRecording();
        updateListeningUI(false, true);
        micBtn.innerHTML = '<i class="bi bi-check-circle me-2"></i>Interview Completed';
        micBtn.disabled = true;

        // Smooth redirect after finish
        setTimeout(() => {
          if (socket.readyState === WebSocket.OPEN) socket.close();
          window.location.href = "/application-sent";
        }, 3500);
      }

      else if (data.type === "error") {
        addMessage("AI", data.message);
        updateListeningUI(false);
      }
    } catch (err) {
      console.error("WebSocket error:", err);
    }
  };

  socket.onclose = () => {
    statusDiv.textContent = "Interview ended";
    statusDot.className = "disconnected";
  };

  socket.onerror = () => {
    statusDiv.textContent = "Connection error";
    statusDot.className = "disconnected";
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
  window.speechSynthesis.cancel();
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden && isListening) stopListening();
});
