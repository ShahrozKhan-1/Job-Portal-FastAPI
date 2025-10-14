
// const jobInfo = {
//   title: "Project Manager",
//   company: "Acme Corp",
//   location: "Remote",
//   type: "Full-time",
//   salary: "PKR 250,000 - 300,000",
//   posted_on: "2025-09-15",
//   link: "#",
//   description:
//     "Lead cross-functional teams to deliver projects on time and within scope. Manage stakeholders, risks, and continuous improvement.",
//   requirements: [
//     "3+ years of project management experience",
//     "Agile/Scrum methodology",
//     "Strong communication and leadership",
//     "Budget oversight and reporting"
//   ]
// };

function populateJob() {
  document.getElementById("jobTitle").textContent = jobInfo.title || "-";
  document.getElementById("jobCompany").textContent = jobInfo.company || "-";
  document.getElementById("jobLocation").textContent = jobInfo.location || "-";
  document.getElementById("jobType").textContent = jobInfo.type || "-";
  document.getElementById("jobSalary").textContent = jobInfo.salary || "-";
  document.getElementById("jobPosted").textContent = jobInfo.posted_on || "-";
  document.getElementById("jobDescription").textContent = jobInfo.description || "-";
  const reqWrap = document.getElementById("jobRequirements");
  reqWrap.innerHTML = "";
  (jobInfo.requirements || []).forEach((r) => {
    const span = document.createElement("span");
    span.className = "req-badge";
    span.textContent = r;
    reqWrap.appendChild(span);
  });
  const link = document.getElementById("jobLink");
  link.href = jobInfo.link || "#";
}

let mediaStream = null;
let mediaRecorder = null;
let chunks = [];
let timerInterval = null;
let seconds = 0;

const timerBox = document.getElementById("timerBox");
const statusDot = document.getElementById("statusDot");
const statusText = document.getElementById("statusText");
const startBtn = document.getElementById("startBtn");
const endBtn = document.getElementById("endBtn");
const recordingNote = document.getElementById("recordingNote");
const playbackWrap = document.getElementById("playbackWrap");
const playback = document.getElementById("playback");
const downloadLink = document.getElementById("downloadLink");
const sendToAiBtn = document.getElementById("sendToAiBtn");
const discardBtn = document.getElementById("discardBtn");
const aiStatus = document.getElementById("aiStatus");

function formatTime(s) {
  const mm = String(Math.floor(s / 60)).padStart(2, "0");
  const ss = String(s % 60).padStart(2, "0");
  return `${mm}:${ss}`;
}

function resetTimer() {
  clearInterval(timerInterval);
  seconds = 0;
  timerBox.textContent = "00:00";
}

function startTimer() {
  clearInterval(timerInterval);
  timerInterval = setInterval(() => {
    seconds++;
    timerBox.textContent = formatTime(seconds);
  }, 1000);
}

async function startInterview() {
  try {
    // Request microphone only
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks = [];

    // Prefer audio/webm; fallback if not supported
    try {
      mediaRecorder = new MediaRecorder(mediaStream, { mimeType: "audio/webm;codecs=opus" });
    } catch {
      mediaRecorder = new MediaRecorder(mediaStream); // let browser choose
    }

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    mediaRecorder.onstop = () => {
      const blob = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
      const url = URL.createObjectURL(blob);
      playback.src = url;
      downloadLink.href = url;
      playbackWrap.style.display = "block";
    };

    mediaRecorder.start();
    statusDot.classList.remove("status-idle");
    statusDot.classList.add("status-live");
    statusText.textContent = "Recording";
    recordingNote.style.display = "block";
    startBtn.disabled = true;
    endBtn.disabled = false;
    resetTimer();
    startTimer();
  } catch (err) {
    alert("Microphone access is required to start the interview. Please allow mic permissions.");
    console.error(err);
  }
}

function endInterview() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
  if (mediaStream) {
    mediaStream.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }
  clearInterval(timerInterval);
  statusDot.classList.remove("status-live");
  statusDot.classList.add("status-idle");
  statusText.textContent = "Idle";
  recordingNote.style.display = "none";
  startBtn.disabled = false;
  endBtn.disabled = true;
}

async function sendToAI(blob) {
  // Replace this stub with your real API call
  // Example:
  // const form = new FormData();
  // form.append("audio", blob, "voice-interview.webm");
  // form.append("job", JSON.stringify(jobInfo));
  // const res = await fetch("/api/voice-interview", { method: "POST", body: form });
  // const data = await res.json();
  // aiStatus.textContent = "AI response received.";

  aiStatus.textContent = "Sending audio to AI...";
  await new Promise((r) => setTimeout(r, 1000));
  aiStatus.textContent = "AI is processing your answers. You'll see results shortly.";
}

document.addEventListener("DOMContentLoaded", () => {
  populateJob();
});

startBtn.addEventListener("click", startInterview);
endBtn.addEventListener("click", endInterview);

sendToAiBtn.addEventListener("click", async () => {
  if (!chunks.length) {
    aiStatus.textContent = "No recording available to send.";
    return;
  }
  const blob = new Blob(chunks, { type: chunks[0]?.type || "audio/webm" });
  await sendToAI(blob);
});

discardBtn.addEventListener("click", () => {
  playback.removeAttribute("src");
  playback.load();
  playbackWrap.style.display = "none";
  chunks = [];
  aiStatus.textContent = "";
});
