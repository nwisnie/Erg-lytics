import {
  FilesetResolver,
  PoseLandmarker
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304";

const video = document.getElementById("liveCamera");
const toggleBtn = document.getElementById("toggleCamera");
const poseStatus = document.getElementById("poseStatus");
const overlay = document.getElementById("poseOverlay");
const overlayCtx = overlay ? overlay.getContext("2d") : null;
const viewport = document.querySelector(".capture__viewport");
const placeholder = document.getElementById("capturePlaceholder");
const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");
const MP_BASE = "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com/mediapipe";
const MP_WASM_PATH = `${MP_BASE}/wasm`;
const MP_MODEL_PATH = `${MP_BASE}/pose_landmarker_lite.task`;

const statusHiddenClass = "pose-status--hidden";
const defaultStatusText = "Full body not in frame";
const userId = document.body?.dataset?.userId || "demo-user";
const recordingDurationMs = 5000;
const inFrameThresholdMs = 5000;
const recordingCooldownMs = 3000;

let stream = null;
let poseLandmarker = null;
let running = false;
let lastVideoTime = -1;
let poseReady = false;

let inFrameMs = 0;
let lastFrameTimestamp = null;
let recordingInProgress = false;
let activeRecorder = null;
let recorderStopTimeout = null;
let recordingCancelled = false;
let nextAllowedRecordTime = 0;
let lastInFrame = false;

let overlayWidth = 0;
let overlayHeight = 0;
let overlayDpr = 1;

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

function resizeOverlay() {
  if (!overlay || !overlayCtx) return;
  const rect = video.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const dpr = window.devicePixelRatio || 1;
  if (rect.width === overlayWidth && rect.height === overlayHeight && dpr === overlayDpr) {
    return;
  }
  overlayWidth = rect.width;
  overlayHeight = rect.height;
  overlayDpr = dpr;
  overlay.width = Math.round(rect.width * dpr);
  overlay.height = Math.round(rect.height * dpr);
  overlay.style.width = `${rect.width}px`;
  overlay.style.height = `${rect.height}px`;
  overlayCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
}

function clearOverlay() {
  if (!overlayCtx) return;
  resizeOverlay();
  overlayCtx.clearRect(0, 0, overlayWidth, overlayHeight);
}

function setViewportActive(active) {
  if (!viewport) return;
  viewport.classList.toggle("capture__viewport--active", active);
  if (placeholder) {
    placeholder.setAttribute("aria-hidden", active ? "true" : "false");
  }
}

function drawLandmarks(landmarks) {
  if (!overlayCtx) return;
  resizeOverlay();
  overlayCtx.clearRect(0, 0, overlayWidth, overlayHeight);
  if (!landmarks || landmarks.length === 0) return;

  const lms = landmarks[0] || [];
  const videoWidth = video.videoWidth || overlayWidth;
  const videoHeight = video.videoHeight || overlayHeight;
  if (!videoWidth || !videoHeight) return;

  const scale = Math.min(overlayWidth / videoWidth, overlayHeight / videoHeight);
  const offsetX = (overlayWidth - videoWidth * scale) / 2;
  const offsetY = (overlayHeight - videoHeight * scale) / 2;

  overlayCtx.fillStyle = "rgba(34, 197, 94, 0.9)";
  overlayCtx.strokeStyle = "rgba(15, 23, 42, 0.55)";
  overlayCtx.lineWidth = 1;

  for (const lm of lms) {
    if (!lm) continue;
    if (lm.visibility != null && lm.visibility < 0.3) continue;
    const x = offsetX + lm.x * videoWidth * scale;
    const y = offsetY + lm.y * videoHeight * scale;
    overlayCtx.beginPath();
    overlayCtx.arc(x, y, 4, 0, Math.PI * 2);
    overlayCtx.fill();
    overlayCtx.stroke();
  }
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
    clearOverlay();
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

function resetRecordingTimers() {
  inFrameMs = 0;
  lastFrameTimestamp = null;
  nextAllowedRecordTime = 0;
}

function cancelActiveRecording() {
  recordingCancelled = true;
  if (recorderStopTimeout) {
    clearTimeout(recorderStopTimeout);
    recorderStopTimeout = null;
  }
  if (activeRecorder && activeRecorder.state !== "inactive") {
    activeRecorder.stop();
  }
  activeRecorder = null;
  recordingInProgress = false;
}

function getRecorderOptions() {
  if (!window.MediaRecorder) return null;
  const candidates = [
    "video/webm;codecs=vp9",
    "video/webm;codecs=vp8",
    "video/webm"
  ];
  const supported = candidates.find((type) => MediaRecorder.isTypeSupported(type));
  return supported ? { mimeType: supported } : {};
}

async function requestUploadUrl(contentType) {
  const response = await fetch(`${apiBase}/api/recordings/presign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      userId,
      contentType
    })
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.error || "Unable to create upload URL");
  }
  return payload;
}

async function saveRecordingMetadata(metadata) {
  try {
    const response = await fetch(`${apiBase}/api/recordings`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(metadata)
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Unable to save recording metadata");
    }
  } catch (err) {
    console.warn("Recording metadata not saved:", err);
  }
}

async function uploadRecording(blob, createdAt) {
  const contentType = blob.type || "video/webm";
  const presign = await requestUploadUrl(contentType);

  const uploadResponse = await fetch(presign.uploadUrl, {
    method: "PUT",
    headers: {
      "Content-Type": contentType
    },
    body: blob
  });

  if (!uploadResponse.ok) {
    throw new Error("Upload failed");
  }

  await saveRecordingMetadata({
    userId,
    objectKey: presign.objectKey,
    contentType,
    durationSec: recordingDurationMs / 1000,
    createdAt
  });
}

async function recordClip() {
  if (!stream || recordingInProgress) return;

  const recorderOptions = getRecorderOptions();
  if (recorderOptions === null) {
    poseStatus.textContent = "Recording not supported in this browser.";
    return;
  }

  const createdAt = new Date().toISOString();
  const chunks = [];

  recordingInProgress = true;
  recordingCancelled = false;
  poseStatus.textContent = "Recording 5s clip...";

  const recorder = new MediaRecorder(stream, recorderOptions);
  activeRecorder = recorder;

  recorder.ondataavailable = (event) => {
    if (event.data && event.data.size) {
      chunks.push(event.data);
    }
  };

  recorder.onstop = async () => {
    if (recorderStopTimeout) {
      clearTimeout(recorderStopTimeout);
      recorderStopTimeout = null;
    }

    activeRecorder = null;
    recordingInProgress = false;

    if (recordingCancelled) {
      recordingCancelled = false;
      return;
    }

    if (!chunks.length) {
      poseStatus.textContent = lastInFrame ? "Full body in frame" : defaultStatusText;
      return;
    }

    const blob = new Blob(chunks, { type: recorder.mimeType || "video/webm" });
    try {
      await uploadRecording(blob, createdAt);
    } catch (err) {
      console.error("Recording upload failed:", err);
      poseStatus.textContent = "Upload failed";
      return;
    }

    poseStatus.textContent = lastInFrame ? "Full body in frame" : defaultStatusText;
  };

  recorder.start();
  recorderStopTimeout = setTimeout(() => {
    if (recorder.state !== "inactive") {
      recorder.stop();
    }
  }, recordingDurationMs);
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
    resizeOverlay();
  } catch (err) {
    console.error("Camera preview failed:", err);
    stopCamera();
    alert("Unable to start camera preview.");
    return;
  }

  setViewportActive(true);
  showPoseStatus();
  poseStatus.textContent = defaultStatusText;
  poseStatus.classList.remove("ready");
  clearOverlay();

  const isPoseReady = await ensurePoseReady();
  running = isPoseReady;
  lastVideoTime = -1;
  resetRecordingTimers();

  toggleBtn.textContent = "Stop";
  toggleBtn.classList.remove("btn--subtle");
  toggleBtn.classList.add("btn--danger");

  if (running) {
    requestAnimationFrame(loop);
  }
}

function stopCamera() {
  running = false;
  cancelActiveRecording();
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  video.pause();
  video.srcObject = null;
  video.load();

  poseStatus.classList.remove("ready");
  clearOverlay();
  setViewportActive(false);
  poseStatus.textContent = defaultStatusText;
  hidePoseStatus();
  lastVideoTime = -1;
  resetRecordingTimers();

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
      drawLandmarks(result.landmarks);
      const inFrame = fullBodyInFrame(result.landmarks);

      lastInFrame = inFrame;
      poseStatus.classList.toggle("ready", inFrame);
      if (!recordingInProgress) {
        poseStatus.textContent = inFrame
          ? "Full body in frame"
          : defaultStatusText;
      }

      const frameTime = performance.now();
      if (lastFrameTimestamp !== null) {
        const deltaMs = frameTime - lastFrameTimestamp;
        if (inFrame) {
          inFrameMs += deltaMs;
        } else {
          inFrameMs = 0;
        }
      }
      lastFrameTimestamp = frameTime;

      if (inFrame &&
          inFrameMs >= inFrameThresholdMs &&
          !recordingInProgress &&
          frameTime >= nextAllowedRecordTime) {
        inFrameMs = 0;
        nextAllowedRecordTime = frameTime + recordingCooldownMs;
        recordClip();
      }
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
