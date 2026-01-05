import {
  FilesetResolver,
  PoseLandmarker
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.14";

const video = document.getElementById("liveCamera");
const toggleBtn = document.getElementById("toggleCamera");
const poseStatus = document.getElementById("poseStatus");
const MP_BASE = "/static/mediapipe";
const MP_WASM_PATH = `${MP_BASE}/wasm`;
const MP_MODEL_PATH = `${MP_BASE}/pose_landmarker_lite.task`;

const statusHiddenClass = "pose-status--hidden";
const defaultStatusText = "Full body not in frame";

let stream = null;
let poseLandmarker = null;
let running = false;
let lastVideoTime = -1;
let poseReady = false;

// for final thing maybe we
// only require like left should hip and knee
// or right or sum like that idk
const REQUIRED = [
  0,   // nose
  11,  // left shoulder
  12,  // right shoulder
  23,  // left hip
  24,  // right hip
  25,  // left knee
  26,  // right knee
  27,  // left ankle
  28   // right ankle
];

async function initPose() {
  const vision = await FilesetResolver.forVisionTasks(MP_WASM_PATH);
  poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
    baseOptions: {
      modelAssetPath: MP_MODEL_PATH
    },
    runningMode: "VIDEO",
    numPoses: 1
  });
}

function showPoseStatus() {
  poseStatus.classList.remove(statusHiddenClass);
}

function hidePoseStatus() {
  poseStatus.classList.add(statusHiddenClass);
}

async function ensurePoseReady() {
  if (poseReady) return true;
  try {
    await initPose();
    poseReady = true;
    return true;
  } catch (err) {
    console.error("Pose model failed to load:", err);
    const message = err instanceof Error ? err.message : String(err);
    poseStatus.textContent = message.includes("Failed to fetch")
      ? "Pose assets missing. Run scripts/setup_mediapipe_assets.sh"
      : "Pose model failed to load";
    poseStatus.classList.remove("ready");
    return false;
  }
}

function fullBodyInFrame(landmarks) {
  if (!landmarks || landmarks.length === 0) return false;
  const lms = landmarks[0];

  const visThreshold = 0.6;
  const margin = 0.05; // keep inside frame edges

  return REQUIRED.every((i) => {
    const lm = lms[i];
    if (!lm) return false;
    const visible = (lm.visibility ?? 0) >= visThreshold;
    const inside =
      lm.x >= margin &&
      lm.x <= 1 - margin &&
      lm.y >= margin &&
      lm.y <= 1 - margin;
    return visible && inside;
  });
}

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
  } catch (err) {
    console.error("Camera access failed:", err);
    alert("Camera access failed. Check browser permissions.");
    return;
  }

  try {
    video.srcObject = stream;
    await video.play();
  } catch (err) {
    console.error("Camera preview failed:", err);
    stopCamera();
    alert("Unable to start camera preview.");
    return;
  }

  showPoseStatus();
  poseStatus.textContent = defaultStatusText;
  poseStatus.classList.remove("ready");

  const isPoseReady = await ensurePoseReady();
  running = isPoseReady;
  lastVideoTime = -1;

  toggleBtn.textContent = "Stop";
  toggleBtn.classList.remove("btn--subtle");
  toggleBtn.classList.add("btn--danger");

  if (running) {
    requestAnimationFrame(loop);
  }
}

function stopCamera() {
  running = false;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  video.pause();
  video.srcObject = null;
  video.load();

  poseStatus.classList.remove("ready");
  poseStatus.textContent = defaultStatusText;
  hidePoseStatus();
  lastVideoTime = -1;

  toggleBtn.textContent = "Start";
  toggleBtn.classList.remove("btn--danger");
  toggleBtn.classList.add("btn--subtle");
}

function loop() {
  if (!running) return;
  if (!poseLandmarker) {
    requestAnimationFrame(loop);
    return;
  }
  if (video.readyState < 2) {
    requestAnimationFrame(loop);
    return;
  }

  const now = video.currentTime;
  if (now !== lastVideoTime) {
    lastVideoTime = now;
    try {
      const result = poseLandmarker.detectForVideo(video, performance.now());
      const inFrame = fullBodyInFrame(result.landmarks);

      poseStatus.classList.toggle("ready", inFrame);
      poseStatus.textContent = inFrame
        ? "Full body in frame"
        : defaultStatusText;
    } catch (err) {
      console.warn("Pose detection failed:", err);
    }
  }

  requestAnimationFrame(loop);
}

toggleBtn.addEventListener("click", async () => {
  if (stream) {
    stopCamera();
    return;
  }

  await startCamera();
});
