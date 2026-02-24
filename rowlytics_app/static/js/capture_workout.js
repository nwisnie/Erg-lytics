import {
  FilesetResolver,
  PoseLandmarker
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304";

const video = document.getElementById("liveCamera");
const toggleBtn = document.getElementById("toggleCamera");
const switchCameraBtn = document.getElementById("switchCamera");
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
const workoutSummaryText = "Workout session";
const mobileUserAgentRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i;

let stream = null;
let poseLandmarker = null;
let running = false;
let lastVideoTime = -1;
let poseReady = false;
let preferredFacingMode = "user";
let cameraSwitchInProgress = false;

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
let workoutStartAt = null;

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

function isLikelyMobileDevice() {
  if (navigator.userAgentData && typeof navigator.userAgentData.mobile === "boolean") {
    return navigator.userAgentData.mobile;
  }
  if (mobileUserAgentRegex.test(navigator.userAgent || "")) {
    return true;
  }
  return Boolean(
    window.matchMedia &&
    window.matchMedia("(pointer: coarse)").matches &&
    window.matchMedia("(max-width: 1024px)").matches
  );
}

function updateSwitchCameraButton() {
  if (!switchCameraBtn) return;
  switchCameraBtn.textContent = preferredFacingMode === "user"
    ? "Use Rear Camera"
    : "Use Front Camera";
}

function setupCameraSwitchControl() {
  if (!switchCameraBtn) return;
  if (isLikelyMobileDevice()) {
    switchCameraBtn.classList.remove("capture__switch--hidden");
    updateSwitchCameraButton();
    return;
  }
  switchCameraBtn.classList.add("capture__switch--hidden");
}

function applyViewportMirrorState() {
  if (!viewport) return;
  // Front camera previews are mirrored by many browsers; force an unmirrored view.
  viewport.classList.toggle("capture__viewport--unmirror", preferredFacingMode === "user");
}

async function getCameraStream() {
  const attempts = [
    { video: { facingMode: { exact: preferredFacingMode } }, audio: false },
    { video: { facingMode: { ideal: preferredFacingMode } }, audio: false },
    { video: true, audio: false }
  ];

  let lastError = null;
  for (const constraints of attempts) {
    try {
      return await navigator.mediaDevices.getUserMedia(constraints);
    } catch (err) {
      lastError = err;
    }
  }
  throw lastError || new Error("Unable to access camera");
}

async function attachStream(nextStream) {
  video.srcObject = nextStream;
  await video.play();
  resizeOverlay();
}

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

function recordLandmarks(landmarks) {
  const lms = landmarks[0] || [];
  const videoWidth = video.videoWidth || overlayWidth;
  const videoHeight = video.videoHeight || overlayHeight;
  if (!videoWidth || !videoHeight) return;

  const scale = Math.min(overlayWidth / videoWidth, overlayHeight / videoHeight);
  const offsetX = (overlayWidth - videoWidth * scale) / 2;
  const offsetY = (overlayHeight - videoHeight * scale) / 2;

  let frame = {
    header : [],
    data : []
  };

  for(let i = 0; i < lms.length; i++) {
    const lm = lms[i];


    const headerName = `landmark_${i}`;
    //console.log("Recording landmark:", headerName, lm);
    frame.header.push(headerName);

    if (!lm || (lm.visibility != null && lm.visibility < 0.3)) {
      frame.data.push("N/A");
      continue;
    }

    let x = offsetX + lm.x * videoWidth * scale;
    let y = offsetY + lm.y * videoHeight * scale;

    frame.data.push({ x: String(x), y: String(y) });

  }

  if(lms[24] && lms[12] && lms[23] && lms[11]) {
    let angle = Math.atan2(lms[24].y - lms[12].y, lms[24].x - lms[12].x) -
    Math.atan2(lms[23].y - lms[11].y, lms[23].x - lms[11].x);
    frame.header.push("body_angle");
    frame.data.push(String(angle));
  }
  else {
    frame.header.push("body_angle");
    frame.data.push("N/A");
  }
  if(lms[26] && lms[24] && lms[12] && lms[28]) {
    let knee_hip = Math.atan2(lms[26].y - lms[24].y, lms[26].x - lms[24].x) -
    Math.atan2(lms[24].y - lms[12].y, lms[24].x - lms[12].x);
    let knee_ankle = Math.atan2(lms[28].y - lms[26].y, lms[28].x - lms[26].x) -
    Math.atan2(lms[28].y - lms[12].y, lms[28].x - lms[12].x);

    let hip_ankle = Math.atan2(lms[28].y - lms[12].y, lms[28].x - lms[12].x) -
    Math.atan2(lms[24].y - lms[12].y, lms[24].x - lms[12].x);
    let knee_angle = Math.acos((knee_hip**2+knee_ankle**2-hip_ankle**2)/(2*knee_hip*knee_ankle));
    frame.header.push("knee_angle");
    frame.data.push(String(knee_angle));
  }
  else {
    frame.header.push("knee_angle");
    frame.data.push("N/A");
  }
  if(lms[20] && lms[16] && lms[12] && lms[19] && lms[15] && lms[11] && lms[18] && lms[14]
    && lms[10]) {
    let thumb_elbow = Math.atan2(lms[20].y - lms[16].y, lms[20].x - lms[16].x) -
    Math.atan2(lms[16].y - lms[12].y, lms[16].x - lms[12].x);
    let index_elbow = Math.atan2(lms[19].y - lms[15].y, lms[19].x - lms[15].x) -
    Math.atan2(lms[15].y - lms[11].y, lms[15].x - lms[11].x);
    let wrist_elbow = Math.atan2(lms[18].y - lms[14].y, lms[18].x - lms[14].x) -
    Math.atan2(lms[14].y - lms[10].y, lms[14].x - lms[10].x);
    let elbow_angle = Math.acos((thumb_elbow**2+index_elbow**2-wrist_elbow**2)/
    (2*thumb_elbow*index_elbow));
    frame.header.push("elbow_angle");
    frame.data.push(String(elbow_angle));
  }
  else {
    frame.header.push("elbow_angle");
    frame.data.push("N/A");
  }

  return frame;

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

async function uploadLandmarks(frame, createdAt) {
  try {
    const response = await fetch(`${apiBase}/api/landmarks`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        userId,
        frame,
        createdAt
      })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Unable to upload landmarks");
    }
  } catch (err) {
    console.warn("Landmarks not uploaded:", err);
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

async function saveWorkoutEntry(durationSec, startedAt, completedAt) {
  if (!apiBase) {
    console.warn("Workout not saved: missing apiBase");
    return;
  }
  try {
    const response = await fetch(`${apiBase}/api/workouts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        durationSec,
        startedAt,
        completedAt,
        summary: workoutSummaryText,
        workoutScore: null
      })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Unable to save workout");
    }
    poseStatus.textContent = "Workout saved";
  } catch (err) {
    console.warn("Workout not saved:", err);
    poseStatus.textContent = "Workout ended (not saved)";
  }
}

async function startCamera() {
  try {
    stream = await getCameraStream();
  } catch (err) {
    console.error("Camera access failed:", err);
    alert("Camera access failed. Check browser permissions.");
    return;
  }

  try {
    await attachStream(stream);
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

  // Update CTA immediately once camera preview is live.
  toggleBtn.textContent = "Stop";
  toggleBtn.classList.remove("btn--start");
  toggleBtn.classList.add("btn--danger");
  applyViewportMirrorState();

  const isPoseReady = await ensurePoseReady();
  running = isPoseReady;
  lastVideoTime = -1;
  resetRecordingTimers();
  workoutStartAt = new Date().toISOString();

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
  if (viewport) {
    viewport.classList.remove("capture__viewport--unmirror");
  }

  if (workoutStartAt) {
    const completedAt = new Date().toISOString();
    const durationMs = Date.parse(completedAt) - Date.parse(workoutStartAt);
    const durationSec = Math.max(1, Math.round(durationMs / 1000));
    saveWorkoutEntry(durationSec, workoutStartAt, completedAt);
  }
  workoutStartAt = null;

  toggleBtn.textContent = "Start";
  toggleBtn.classList.remove("btn--danger");
  toggleBtn.classList.add("btn--start");
}

async function switchCamera() {
  if (!stream || cameraSwitchInProgress) return;
  if (recordingInProgress) {
    poseStatus.textContent = "Wait for clip recording to finish before switching camera.";
    return;
  }

  const previousFacingMode = preferredFacingMode;
  const currentStream = stream;
  preferredFacingMode = preferredFacingMode === "user" ? "environment" : "user";
  updateSwitchCameraButton();
  applyViewportMirrorState();
  cameraSwitchInProgress = true;

  try {
    const nextStream = await getCameraStream();
    try {
      await attachStream(nextStream);
      stream = nextStream;
      currentStream.getTracks().forEach((track) => track.stop());
      poseStatus.textContent = "Camera switched";
    } catch (attachErr) {
      nextStream.getTracks().forEach((track) => track.stop());
      throw attachErr;
    }
  } catch (err) {
    preferredFacingMode = previousFacingMode;
    updateSwitchCameraButton();
    applyViewportMirrorState();
    console.error("Camera switch failed:", err);
    poseStatus.textContent = "Unable to switch camera";
  } finally {
    cameraSwitchInProgress = false;
  }
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
  const createdAt = new Date().toISOString();
  if (now !== lastVideoTime) {
    lastVideoTime = now;
    try {
      const result = poseLandmarker.detectForVideo(video, performance.now());
      drawLandmarks(result.landmarks);
      let recordedFrame = recordLandmarks(result.landmarks);
      if (recordingInProgress) {
        //recordedFrame.createdAt = createdAt;
        uploadLandmarks(recordedFrame, createdAt);
      }

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

if (switchCameraBtn) {
  switchCameraBtn.addEventListener("click", async () => {
    if (!stream) {
      preferredFacingMode = preferredFacingMode === "user" ? "environment" : "user";
      updateSwitchCameraButton();
      applyViewportMirrorState();
      return;
    }
    await switchCamera();
  });
}

setupCameraSwitchControl();
applyViewportMirrorState();
