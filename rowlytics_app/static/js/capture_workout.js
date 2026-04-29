import {
  FilesetResolver,
  PoseLandmarker
} from "https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.22-rc.20250304";
import { v4 as uuidv4 } from "https://cdn.skypack.dev/uuid";

const video = document.getElementById("liveCamera");
const toggleBtn = document.getElementById("toggleCamera");
const switchCameraBtn = document.getElementById("switchCamera");
const poseStatus = document.getElementById("poseStatus");
const overlay = document.getElementById("poseOverlay");
const overlayCtx = overlay ? overlay.getContext("2d") : null;
const viewport = document.querySelector(".capture__viewport");
const placeholder = document.getElementById("capturePlaceholder");
const captureSessionNotice = document.getElementById("captureSessionNotice");
const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");
let workoutId = null;
const workoutDetailBase = document.body?.dataset?.workoutDetailBase || "";
const urlParams = (() => {
  try {
    return new URLSearchParams(window.location.search || "");
  } catch (err) {
    return null;
  }
})();
const MP_BASE = "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com/mediapipe";
const MP_WASM_PATH = `${MP_BASE}/wasm`;
const MP_MODEL_FILES = Object.freeze({
  lite: "pose_landmarker_lite.task",
  full: "pose_landmarker_full.task",
  heavy: "pose_landmarker_heavy.task",
});
const requestedPoseModel = (urlParams?.get("poseModel") || "lite").toLowerCase();
function readDebugFlag(paramName, storageKey) {
  try {
    const fromQuery = urlParams?.get(paramName);
    if (fromQuery === "1" || fromQuery === "true") return true;
    if (fromQuery === "0" || fromQuery === "false") return false;
    return window.localStorage?.getItem(storageKey) === "1";
  } catch (err) {
    return false;
  }
}

const buildPoseModelCandidates = (requestedModel) => {
  const candidateKeys = [];
  if (Object.prototype.hasOwnProperty.call(MP_MODEL_FILES, requestedModel)) {
    candidateKeys.push(requestedModel);
  }
  if (!candidateKeys.includes("lite")) candidateKeys.push("lite");
  return candidateKeys.map((key) => ({
    key,
    path: `${MP_BASE}/${MP_MODEL_FILES[key]}`
  }));
};
const MP_MODEL_CANDIDATE_PATHS = buildPoseModelCandidates(requestedPoseModel);

const statusHiddenClass = "pose-status--hidden";
const defaultStatusText = "Side profile not in frame";
const readyStatusText = "Side profile in frame";
const userId = document.body?.dataset?.userId || "demo-user";
const recordingDurationMs = 5000;
const maxWorkoutDurationMs = 60 * 60 * 1000;
const maxWorkoutDurationSec = maxWorkoutDurationMs / 1000;
const maxRecordingClipsPerWorkout = 3;
const inFrameThresholdMs = 5000;
const recordingCooldownMs = 3000;
const inFrameDropoutGraceMs = 600;
const movementGateRetryMs = 1200;
const movementDebugLogIntervalMs = 500;
const activeSegmentMinFrames = 6;
const workoutSummaryText = "Workout session";
const workoutDurationLimitText = (
  "Workouts automatically stop after 1 hour. Recording uploads are capped at 2 hours per day."
);
const workoutDurationLimitReachedText = "Workout reached the 1-hour limit and stopped automatically.";
const workoutClipLimitReachedText = `Maximum of ${maxRecordingClipsPerWorkout} clips reached for this workout.`;
const mobileUserAgentRegex = /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i;
const recordingScoreThreshold = 100.0; // Only upload recordings with a movement gate score of 100.0 or below

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
let lastRawInFrameAtMs = null;
let recordedLandmarkFrames = [];
let waitingForStrokeGate = false;

let overlayWidth = 0;
let overlayHeight = 0;
let overlayDpr = 1;
let workoutStartAt = null;
let workoutStopDeadlineMs = null;
let workoutStopTimeout = null;
let workoutMovementFrames = [];
let workoutMovementFrameTimesMs = [];
let movementWindowClipCount = 0;
let lastMovementDebugLogAtMs = 0;
let latestWorkoutAnalysis = null;
let latestWorkoutAnalysisText = "";
let latestWorkoutScore = null;
let workoutAnalysisAggregate = null;

let bodyInFramePromptPlayed = false;
let readyToBeginPromptPlayed = false;
let noAthletePromptPlayed = false;

let badArmsStartMs = null;
let badBackStartMs = null;
let lastArmsPromptAtMs = 0;
let lastBackPromptAtMs = 0;
let lastNoAthletePromptAtMs = 0;

const noAthleteDelayMs = 5000;
const noAthleteRepeatMs = 20000;
const formBadDurationMs = 3500;
const formPromptCooldownMs = 5000;
const armsStraightThreshold = 90;
const backStraightThreshold = 90;

const STATIC_ASSET_BASE = "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com";

const audioClips = {
  straightenArms: new Audio(`${STATIC_ASSET_BASE}/audio/straighten_your_arms.mp3`),
  straightenBack: new Audio(`${STATIC_ASSET_BASE}/audio/straighten_your_back.mp3`),
  noAthleteDetected: new Audio(`${STATIC_ASSET_BASE}/audio/no_athlete_detected.mp3`),
  readyToBegin: new Audio(`${STATIC_ASSET_BASE}/audio/ready_to_begin.mp3`),
  bodyInFrame: new Audio(`${STATIC_ASSET_BASE}/audio/body_in_frame.mp3`),
  recordingSaved: new Audio(`${STATIC_ASSET_BASE}/audio/recording_saved.mp3`)
};

Object.values(audioClips).forEach((clip) => {
  clip.preload = "auto";
});

const audioQueue = [];
let audioPlaying = false;

function playAudio(key, { queued = true } = {}) {
  const clip = audioClips[key];
  if (!clip) return;

  if (!queued) {
    audioQueue.length = 0;
    audioPlaying = false;

    Object.values(audioClips).forEach((audio) => {
      audio.pause();
      audio.currentTime = 0;
    });

    clip.play().catch((err) => {
      console.warn(`Could not play audio "${key}":`, err);
    });
    return;
  }

  audioQueue.push(key);
  playNextAudio();
}

function playNextAudio() {
  if (audioPlaying || !audioQueue.length) return;

  const key = audioQueue.shift();
  const clip = audioClips[key];
  if (!clip) {
    playNextAudio();
    return;
  }

  audioPlaying = true;
  clip.currentTime = 0;

  const finish = () => {
    clip.removeEventListener("ended", finish);
    clip.removeEventListener("error", finish);
    audioPlaying = false;
    playNextAudio();
  };

  clip.addEventListener("ended", finish);
  clip.addEventListener("error", finish);

  clip.play().catch((err) => {
    console.warn(`Could not play audio "${key}":`, err);
    finish();
  });
}

const SIDE_PROFILE_LEFT = [11, 13, 15, 23, 25, 27];
const SIDE_PROFILE_RIGHT = [12, 14, 16, 24, 26, 28];
const sideProfileVisibilityThreshold = 0.35;
const sideProfileMinVisiblePoints = 4;
const movementMinStrokesRequired = 3;
const movementMinRangeOfMotion = 0.12;
const movementMinCycleSec = 0.35;
const movementMaxCycleSec = 6.0;
const movementTurnEpsilon = 0.0012;
const movementMinAmplitudeFloor = 0.009;
const movementAmplitudeScale = 0.14;
const movementAngleMinRangeOfMotion = 0.06;
const movementAngleMinAmplitudeFloor = 0.006;
const movementAngleAmplitudeScale = 0.11;
const movementHistoryMaxFrames = 1800;
const glitchFrameMaxDtSec = 0.2;
const glitchFrameMaxDelta = 0.14;
const glitchFrameMinComparablePoints = 3;
const motionSpikeMaxDeltaPerSec = 1.2;
const motionSpikeBaseDelta = 0.075;
const motionSignalVisibilityFloor = 0.12;
const motionComparisonLandmarkIndices = [11, 12, 13, 14, 15, 16];
const captureDebugEnabled = readDebugFlag("captureDebug", "rowlytics_capture_debug");
const captureExportEnabled = captureDebugEnabled &&
  readDebugFlag("captureExport", "rowlytics_capture_export");
const captureDebugExportVersion = "20260427a";

let latestClipDebugSnapshot = null;
let workoutClipDebugSnapshots = [];
let debugExportControls = null;

function cloneJsonCompatible(value) {
  if (value == null) return value;
  try {
    return JSON.parse(JSON.stringify(value));
  } catch (err) {
    return value;
  }
}

function safeFilenameSegment(value, fallback = "unknown") {
  const normalized = String(value ?? fallback)
    .trim()
    .replace(/[^a-z0-9_-]+/gi, "-")
    .replace(/-+/g, "-")
    .replace(/^-|-$/g, "");
  return normalized || fallback;
}

function buildDebugExportFilename(scope, snapshot = null) {
  const clipLabel = snapshot?.clipIndex != null
    ? `clip-${safeFilenameSegment(snapshot.clipIndex, "0")}`
    : scope;
  const createdAtLabel = safeFilenameSegment(snapshot?.createdAt || new Date().toISOString(), "capture");
  return `rowlytics-${scope}-${clipLabel}-${createdAtLabel}.json`;
}

function downloadJsonFile(filename, payload) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json"
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

function buildClipDebugSnapshot({
  createdAt,
  clipIndex,
  recordedFrames,
  gateFrames,
  scoringFrames,
  scoringFrameSource,
  scoringDurationSec,
  gateMovement,
  localMovement,
  mergedMovement,
  analysisPayload,
  persistedPayload,
  aggregatePayload,
}) {
  return {
    exportedAt: new Date().toISOString(),
    exportVersion: captureDebugExportVersion,
    workoutId,
    clipIndex,
    createdAt,
    recordingDurationSec: recordingDurationMs / 1000,
    preferredFacingMode,
    requestedPoseModel,
    captureDebugEnabled,
    captureExportEnabled,
    landmarksFrameCount: Array.isArray(recordedFrames) ? recordedFrames.length : 0,
    recordedLandmarkFrames: cloneJsonCompatible(recordedFrames),
    gateFramesFrameCount: Array.isArray(gateFrames) ? gateFrames.length : 0,
    gateFrames: cloneJsonCompatible(gateFrames),
    scoringFramesFrameCount: Array.isArray(scoringFrames) ? scoringFrames.length : 0,
    scoringFrameSource,
    scoringDurationSec,
    gateMovement: cloneJsonCompatible(gateMovement),
    localMovement: cloneJsonCompatible(localMovement),
    mergedMovement: cloneJsonCompatible(mergedMovement),
    analysisPayload: cloneJsonCompatible(analysisPayload),
    persistedPayload: cloneJsonCompatible(persistedPayload),
    aggregatePayload: cloneJsonCompatible(aggregatePayload),
    alignmentDetailsText: aggregatePayload ? formatAlignmentOutput(aggregatePayload) : "",
  };
}

function updateDebugExportControlsState() {
  if (!debugExportControls) return;
  const { exportLastBtn, exportAllBtn, summary } = debugExportControls;
  const clipCount = workoutClipDebugSnapshots.length;
  if (exportLastBtn) {
    exportLastBtn.disabled = !latestClipDebugSnapshot;
  }
  if (exportAllBtn) {
    exportAllBtn.disabled = clipCount === 0;
  }
  if (summary) {
    summary.textContent = clipCount
      ? `Debug export ready: ${clipCount} clip${clipCount === 1 ? "" : "s"} captured.`
      : "Debug export ready: no saved clips yet.";
  }
}

function exportLastClipDebugSnapshot() {
  if (!latestClipDebugSnapshot) return;
  downloadJsonFile(
    buildDebugExportFilename("capture-debug", latestClipDebugSnapshot),
    latestClipDebugSnapshot,
  );
}

function exportAllClipDebugSnapshots() {
  if (!workoutClipDebugSnapshots.length) return;
  downloadJsonFile(
    buildDebugExportFilename("capture-debug-all"),
    {
      exportedAt: new Date().toISOString(),
      exportVersion: captureDebugExportVersion,
      workoutId,
      clipCount: workoutClipDebugSnapshots.length,
      clips: cloneJsonCompatible(workoutClipDebugSnapshots),
      latestWorkoutAnalysis: cloneJsonCompatible(latestWorkoutAnalysis),
      latestWorkoutAnalysisText,
      latestWorkoutScore,
    },
  );
}

function rememberClipDebugSnapshot(snapshot) {
  if (!captureDebugEnabled || !snapshot) return;
  latestClipDebugSnapshot = snapshot;
  workoutClipDebugSnapshots.push(snapshot);
  debugCapture("clip_debug_snapshot_saved", {
    clipIndex: snapshot.clipIndex,
    clipCount: workoutClipDebugSnapshots.length
  });
  updateDebugExportControlsState();
  if (captureExportEnabled) {
    downloadJsonFile(
      buildDebugExportFilename("capture-debug", snapshot),
      snapshot,
    );
  }
}

function resetClipDebugSnapshots() {
  latestClipDebugSnapshot = null;
  workoutClipDebugSnapshots = [];
  updateDebugExportControlsState();
}

function ensureDebugExportControls() {
  if (!captureDebugEnabled || debugExportControls || !captureSessionNotice?.parentElement) {
    return;
  }

  const controlsWrap = document.createElement("div");
  controlsWrap.className = "capture__controls";

  const exportLastBtn = document.createElement("button");
  exportLastBtn.type = "button";
  exportLastBtn.className = "btn btn--subtle";
  exportLastBtn.textContent = "Export Last Clip JSON";
  exportLastBtn.addEventListener("click", exportLastClipDebugSnapshot);

  const exportAllBtn = document.createElement("button");
  exportAllBtn.type = "button";
  exportAllBtn.className = "btn btn--subtle";
  exportAllBtn.textContent = "Export All Clip JSON";
  exportAllBtn.addEventListener("click", exportAllClipDebugSnapshots);

  controlsWrap.append(exportLastBtn, exportAllBtn);

  const summary = document.createElement("p");
  summary.className = "capture__note";

  captureSessionNotice.parentElement.append(controlsWrap, summary);
  debugExportControls = {
    exportLastBtn,
    exportAllBtn,
    summary,
  };
  updateDebugExportControlsState();
}

function debugCapture(event, details = {}) {
  if (!captureDebugEnabled) return;
  console.log(`[capture-workout] ${event}`, details);
}

function updateCaptureSessionNotice(message = workoutDurationLimitText) {
  if (!captureSessionNotice) return;
  captureSessionNotice.textContent = message;
}

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

function reachedWorkoutClipLimit() {
  return movementWindowClipCount >= maxRecordingClipsPerWorkout;
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

function resetMovementHistory() {
  workoutMovementFrames = [];
  workoutMovementFrameTimesMs = [];
}

function appendMovementFrame(frame, frameTimeMs) {
  if (!Array.isArray(frame) || !frame.length) return;
  if (workoutMovementFrames.length && workoutMovementFrameTimesMs.length) {
    const previousFrame = workoutMovementFrames[workoutMovementFrames.length - 1];
    const previousTimeMs = workoutMovementFrameTimesMs[workoutMovementFrameTimesMs.length - 1];
    const dtSec = (frameTimeMs - previousTimeMs) / 1000;
    if (dtSec > 0 && dtSec <= glitchFrameMaxDtSec) {
      let comparablePoints = 0;
      let deltaTotal = 0;
      motionComparisonLandmarkIndices.forEach((index) => {
        const prevLandmark = usableLandmark(previousFrame, index);
        const nextLandmark = usableLandmark(frame, index);
        if (!prevLandmark || !nextLandmark) return;
        comparablePoints += 1;
        deltaTotal += Math.hypot(nextLandmark.x - prevLandmark.x, nextLandmark.y - prevLandmark.y);
      });
      if (comparablePoints >= glitchFrameMinComparablePoints) {
        const meanDelta = deltaTotal / comparablePoints;
        if (meanDelta > glitchFrameMaxDelta) {
          debugCapture("dropped_glitch_frame", {
            comparablePoints,
            meanDelta: Number(meanDelta.toFixed(4)),
            dtSec: Number(dtSec.toFixed(4))
          });
          return;
        }
      }
    }
  }

  workoutMovementFrames.push(frame);
  workoutMovementFrameTimesMs.push(frameTimeMs);
  if (workoutMovementFrames.length <= movementHistoryMaxFrames) {
    return;
  }
  const overflow = workoutMovementFrames.length - movementHistoryMaxFrames;
  workoutMovementFrames.splice(0, overflow);
  workoutMovementFrameTimesMs.splice(0, overflow);
}

function getMovementWindowSec() {
  if (workoutMovementFrameTimesMs.length >= 2) {
    const first = workoutMovementFrameTimesMs[0];
    const last = workoutMovementFrameTimesMs[workoutMovementFrameTimesMs.length - 1];
    const elapsedSec = (last - first) / 1000;
    if (elapsedSec > 0) {
      return Number(elapsedSec.toFixed(2));
    }
  }
  return recordingDurationMs / 1000;
}

function logMovementDebug(event, movement, extras = {}) {
  debugCapture(event, {
    inFrameMs: Number(inFrameMs.toFixed(0)),
    recordingInProgress,
    movementFrameCount: workoutMovementFrames.length,
    pendingClipIndex: movementWindowClipCount + 1,
    movementQualified: movement.movementQualified,
    movementReason: movement.movementReason,
    strokeCount: movement.strokeCount,
    rangeOfMotion: movement.rangeOfMotion,
    cadenceSpm: movement.cadenceSpm,
    signalPointCount: movement.signalPointCount,
    rawSignalPointCount: movement.rawSignalPointCount,
    signalDropCount: movement.signalDropCount,
    signalSource: movement.signalSource,
    analysisWindowSec: movement.analysisWindowSec,
    ...extras,
  });
}

function asNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function usableLandmark(frame, index, visibilityFloor = 0.2) {
  if (!Array.isArray(frame) || index >= frame.length) return null;
  const landmark = frame[index];
  if (!landmark || typeof landmark !== "object") return null;
  const x = asNumber(landmark.x);
  const y = asNumber(landmark.y);
  if (x == null || y == null) return null;
  const visibility = landmark.visibility == null ? 1 : asNumber(landmark.visibility);
  if (visibility != null && visibility < visibilityFloor) return null;
  return landmark;
}

function frameHasSideProfileChain(frame, preferredSide = null) {
  const margin = 0.06;
  const sideEntries = preferredSide === "left"
    ? [["left", SIDE_PROFILE_LEFT]]
    : preferredSide === "right"
      ? [["right", SIDE_PROFILE_RIGHT]]
      : [
        ["left", SIDE_PROFILE_LEFT],
        ["right", SIDE_PROFILE_RIGHT]
      ];

  return sideEntries.some(([, indices]) => {
    const visibleCount = indices.reduce((count, index) => {
      const landmark = usableLandmark(frame, index, sideProfileVisibilityThreshold);
      if (!landmark) return count;
      if (
        landmark.x >= margin &&
        landmark.x <= 1 - margin &&
        landmark.y >= margin &&
        landmark.y <= 1 - margin
      ) {
        return count + 1;
      }
      return count;
    }, 0);
    const shoulder = usableLandmark(frame, indices[0], sideProfileVisibilityThreshold);
    const hip = usableLandmark(frame, indices[3], sideProfileVisibilityThreshold);
    const shoulderInBounds = shoulder &&
      shoulder.x >= margin &&
      shoulder.x <= 1 - margin &&
      shoulder.y >= margin &&
      shoulder.y <= 1 - margin;
    const hipInBounds = hip &&
      hip.x >= margin &&
      hip.x <= 1 - margin &&
      hip.y >= margin &&
      hip.y <= 1 - margin;
    return Boolean(shoulderInBounds && hipInBounds && visibleCount >= sideProfileMinVisiblePoints);
  });
}

function trimFramesToActiveSegment(frames, clipDurationSec, preferredSide = null) {
  if (!Array.isArray(frames) || frames.length < 2) {
    return {
      frames: Array.isArray(frames) ? frames : [],
      durationSec: Number(clipDurationSec || 0),
    };
  }

  let bestStart = null;
  let bestEnd = null;
  let currentStart = null;

  frames.forEach((frame, index) => {
    const valid = frameHasSideProfileChain(frame, preferredSide);
    if (valid && currentStart === null) {
      currentStart = index;
      return;
    }
    if (valid) {
      return;
    }
    if (currentStart === null) {
      return;
    }
    const currentEnd = index - 1;
    if (
      bestStart === null ||
      (currentEnd - currentStart) > (bestEnd - bestStart)
    ) {
      bestStart = currentStart;
      bestEnd = currentEnd;
    }
    currentStart = null;
  });

  if (currentStart !== null) {
    const currentEnd = frames.length - 1;
    if (
      bestStart === null ||
      (currentEnd - currentStart) > (bestEnd - bestStart)
    ) {
      bestStart = currentStart;
      bestEnd = currentEnd;
    }
  }

  if (bestStart === null || bestEnd === null) {
    return { frames, durationSec: clipDurationSec };
  }

  const trimmedFrames = frames.slice(bestStart, bestEnd + 1);
  if (trimmedFrames.length < activeSegmentMinFrames) {
    return { frames, durationSec: clipDurationSec };
  }

  const frameIntervalSec = clipDurationSec / Math.max(frames.length - 1, 1);
  return {
    frames: trimmedFrames,
    durationSec: Number((frameIntervalSec * Math.max(trimmedFrames.length - 1, 1)).toFixed(6)),
  };
}

function detectDominantSideFromFrames(frames) {
  let leftVisible = 0;
  let rightVisible = 0;

  frames.forEach((frame) => {
    SIDE_PROFILE_LEFT.forEach((index) => {
      if (usableLandmark(frame, index)) leftVisible += 1;
    });
    SIDE_PROFILE_RIGHT.forEach((index) => {
      if (usableLandmark(frame, index)) rightVisible += 1;
    });
  });

  return leftVisible >= rightVisible ? "left" : "right";
}

function computeElbowAngleNormalized(shoulder, elbow, wrist) {
  if (!shoulder || !elbow || !wrist) return null;
  const upperX = shoulder.x - elbow.x;
  const upperY = shoulder.y - elbow.y;
  const foreX = wrist.x - elbow.x;
  const foreY = wrist.y - elbow.y;
  const upperMag = Math.hypot(upperX, upperY);
  const foreMag = Math.hypot(foreX, foreY);
  if (upperMag < 1e-4 || foreMag < 1e-4) return null;
  const cosine = ((upperX * foreX) + (upperY * foreY)) / (upperMag * foreMag);
  const clamped = Math.max(-1, Math.min(1, cosine));
  const angleRad = Math.acos(clamped);
  return angleRad / Math.PI;
}

function extractMotionSignalCandidates(frames, dominantSide, clipDurationSec) {
  const sideIndices = dominantSide === "left"
    ? { shoulder: 11, elbow: 13, wrist: 15, hip: 23 }
    : { shoulder: 12, elbow: 14, wrist: 16, hip: 24 };
  const frameIntervalSec = clipDurationSec / Math.max(frames.length - 1, 1);
  const translationSeries = [];
  const elbowAngleSeries = [];

  frames.forEach((frame, index) => {
    const timestamp = Number((index * frameIntervalSec).toFixed(6));
    const shoulder = usableLandmark(frame, sideIndices.shoulder, motionSignalVisibilityFloor);
    const elbow = usableLandmark(frame, sideIndices.elbow, motionSignalVisibilityFloor);
    const wrist = usableLandmark(frame, sideIndices.wrist, motionSignalVisibilityFloor);
    const hip = usableLandmark(frame, sideIndices.hip, motionSignalVisibilityFloor);

    let translationValue = null;
    let translationSource = null;
    if (shoulder && wrist) {
      translationValue = wrist.x - shoulder.x;
      translationSource = `${dominantSide}_wrist-${dominantSide}_shoulder`;
    } else if (shoulder && elbow) {
      translationValue = elbow.x - shoulder.x;
      translationSource = `${dominantSide}_elbow-${dominantSide}_shoulder`;
    } else if (hip && wrist) {
      translationValue = wrist.x - hip.x;
      translationSource = `${dominantSide}_wrist-${dominantSide}_hip`;
    } else if (hip && elbow) {
      translationValue = elbow.x - hip.x;
      translationSource = `${dominantSide}_elbow-${dominantSide}_hip`;
    } else if (hip && shoulder) {
      translationValue = shoulder.x - hip.x;
      translationSource = `${dominantSide}_shoulder-${dominantSide}_hip`;
    }

    if (translationValue != null) {
      if (hip && shoulder) {
        const torsoLength = Math.hypot(shoulder.x - hip.x, shoulder.y - hip.y);
        if (torsoLength > 0.04) {
          translationValue /= torsoLength;
          translationSource += "_norm";
        }
      }
      translationSeries.push({
        time: timestamp,
        value: translationValue,
        source: translationSource
      });
    }

    const elbowAngleValue = computeElbowAngleNormalized(shoulder, elbow, wrist);
    if (elbowAngleValue != null) {
      elbowAngleSeries.push({
        time: timestamp,
        value: elbowAngleValue,
        source: `${dominantSide}_elbow_angle_norm`
      });
    }
  });

  return [
    {
      signalStrategy: "upper_body_translation",
      rawSeries: translationSeries,
      minRangeOfMotion: movementMinRangeOfMotion,
      minAmplitudeFloor: movementMinAmplitudeFloor,
      amplitudeScale: movementAmplitudeScale
    },
    {
      signalStrategy: "elbow_angle",
      rawSeries: elbowAngleSeries,
      minRangeOfMotion: movementAngleMinRangeOfMotion,
      minAmplitudeFloor: movementAngleMinAmplitudeFloor,
      amplitudeScale: movementAngleAmplitudeScale
    }
  ];
}

function smoothMotionSeries(series, alpha = 0.35) {
  if (!series.length) return [];
  let smoothValue = series[0].value;
  return series.map((point) => {
    smoothValue = alpha * point.value + (1 - alpha) * smoothValue;
    return {
      time: point.time,
      value: smoothValue,
      source: point.source
    };
  });
}

function despikeMotionSeries(series) {
  if (!Array.isArray(series) || series.length < 3) {
    return series || [];
  }

  const filtered = [series[0]];
  for (let i = 1; i < series.length; i += 1) {
    const prev = filtered[filtered.length - 1];
    const point = series[i];
    const dt = point.time - prev.time;
    if (dt <= 0) continue;
    const allowedDelta = Math.max(motionSpikeBaseDelta, motionSpikeMaxDeltaPerSec * dt);
    if (Math.abs(point.value - prev.value) > allowedDelta) {
      continue;
    }
    filtered.push(point);
  }

  if (filtered.length < 2) {
    return series;
  }
  return filtered;
}

function findTurningPoints(series, epsilon = movementTurnEpsilon) {
  if (series.length < 3) return [];
  const candidates = [];

  for (let i = 1; i < series.length - 1; i += 1) {
    const prevDelta = series[i].value - series[i - 1].value;
    const nextDelta = series[i + 1].value - series[i].value;
    let type = null;
    if (prevDelta >= epsilon && nextDelta <= -epsilon) type = "peak";
    if (prevDelta <= -epsilon && nextDelta >= epsilon) type = "trough";
    if (!type) continue;
    candidates.push({ type, time: series[i].time, value: series[i].value });
  }

  if (!candidates.length) return [];
  const collapsed = [candidates[0]];
  for (let i = 1; i < candidates.length; i += 1) {
    const point = candidates[i];
    const last = collapsed[collapsed.length - 1];
    if (point.type === last.type) {
      const replacePeak = point.type === "peak" && point.value > last.value;
      const replaceTrough = point.type === "trough" && point.value < last.value;
      if (replacePeak || replaceTrough) {
        collapsed[collapsed.length - 1] = point;
      }
      continue;
    }
    collapsed.push(point);
  }
  return collapsed;
}

function countStrokes(turningPoints, minAmplitude, minCycleSec, maxCycleSec) {
  if (turningPoints.length < 3) return 0;
  let strokes = 0;
  let i = 0;
  while (i + 2 < turningPoints.length) {
    const first = turningPoints[i];
    const middle = turningPoints[i + 1];
    const third = turningPoints[i + 2];
    if (first.type === third.type && first.type !== middle.type) {
      const ampOne = Math.abs(middle.value - first.value);
      const ampTwo = Math.abs(third.value - middle.value);
      const cycleSec = third.time - first.time;
      if (
        ampOne >= minAmplitude &&
        ampTwo >= minAmplitude &&
        cycleSec >= minCycleSec &&
        cycleSec <= maxCycleSec
      ) {
        strokes += 1;
        i += 2;
        continue;
      }
    }
    i += 1;
  }
  return strokes;
}

function evaluateMovementGate(frames, clipDurationSec) {
  if (!Array.isArray(frames) || frames.length < 2) {
    return {
      movementQualified: false,
      movementReason: "Not enough frames captured.",
      strokeCount: 0,
      rangeOfMotion: 0,
      cadenceSpm: 0,
      signalPointCount: 0,
      signalSource: "n/a",
      analysisWindowSec: 0
    };
  }

  const dominantSide = detectDominantSideFromFrames(frames);
  const candidates = extractMotionSignalCandidates(frames, dominantSide, clipDurationSec);

  const evaluateCandidate = (candidate) => {
    const rawSeries = candidate.rawSeries || [];
    const filteredSeries = despikeMotionSeries(rawSeries);
    const signalDropCount = Math.max(0, rawSeries.length - filteredSeries.length);
    if (filteredSeries.length < 6) {
      return {
        dominantSide,
        signalStrategy: candidate.signalStrategy,
        movementQualified: false,
        movementReason: "Not enough movement points detected for stroke analysis.",
        strokeCount: 0,
        rangeOfMotion: 0,
        cadenceSpm: 0,
        signalPointCount: filteredSeries.length,
        rawSignalPointCount: rawSeries.length,
        signalDropCount,
        signalSource: "n/a",
        analysisWindowSec: Number(clipDurationSec.toFixed(2))
      };
    }

    const smoothedSignal = smoothMotionSeries(filteredSeries);
    const values = smoothedSignal.map((point) => point.value);
    const rangeOfMotion = Math.max(...values) - Math.min(...values);
    const minAmplitude = Math.max(
      candidate.minAmplitudeFloor,
      rangeOfMotion * candidate.amplitudeScale
    );
    const turningPoints = findTurningPoints(smoothedSignal);
    const strokeCount = countStrokes(
      turningPoints,
      minAmplitude,
      movementMinCycleSec,
      movementMaxCycleSec
    );

    const activeDurationSec = Math.max(
      smoothedSignal[smoothedSignal.length - 1].time - smoothedSignal[0].time,
      clipDurationSec
    );
    const cadenceSpm = activeDurationSec > 0 ? strokeCount / (activeDurationSec / 60) : 0;

    let movementQualified = true;
    let movementReason = "Movement gate passed.";
    if (rangeOfMotion < candidate.minRangeOfMotion) {
      movementQualified = false;
      movementReason = `Not enough rowing motion (range ${rangeOfMotion.toFixed(3)}).`;
    } else if (strokeCount < movementMinStrokesRequired) {
      movementQualified = false;
      movementReason = `Need at least ${movementMinStrokesRequired} strokes to save a clip.`;
    }

    return {
      dominantSide,
      signalStrategy: candidate.signalStrategy,
      movementQualified,
      movementReason,
      strokeCount,
      rangeOfMotion: Number(rangeOfMotion.toFixed(6)),
      cadenceSpm: Number(cadenceSpm.toFixed(2)),
      signalPointCount: smoothedSignal.length,
      rawSignalPointCount: rawSeries.length,
      signalDropCount,
      signalSource: smoothedSignal[0]?.source || "n/a",
      analysisWindowSec: Number(activeDurationSec.toFixed(2))
    };
  };

  const evaluated = candidates.map((candidate) => evaluateCandidate(candidate));
  if (!evaluated.length) {
    return {
      dominantSide,
      signalStrategy: "n/a",
      movementQualified: false,
      movementReason: "Not enough movement points detected for stroke analysis.",
      strokeCount: 0,
      rangeOfMotion: 0,
      cadenceSpm: 0,
      signalPointCount: 0,
      rawSignalPointCount: 0,
      signalDropCount: 0,
      signalSource: "n/a",
      analysisWindowSec: Number(clipDurationSec.toFixed(2))
    };
  }

  let best = evaluated[0];
  for (let i = 1; i < evaluated.length; i += 1) {
    const next = evaluated[i];
    const bestQualified = best.movementQualified ? 1 : 0;
    const nextQualified = next.movementQualified ? 1 : 0;
    if (nextQualified > bestQualified) {
      best = next;
      continue;
    }
    if (next.strokeCount > best.strokeCount) {
      best = next;
      continue;
    }
    if (next.strokeCount === best.strokeCount && next.rangeOfMotion > best.rangeOfMotion) {
      best = next;
      continue;
    }
    if (
      next.strokeCount === best.strokeCount &&
      next.rangeOfMotion === best.rangeOfMotion &&
      next.signalPointCount > best.signalPointCount
    ) {
      best = next;
    }
  }

  return best;
}

function formatAlignmentOutput(payload) {
  const movementGate = payload.movementQualified == null
    ? "n/a"
    : (payload.movementQualified ? "passed" : "failed");
  const strokeCount = payload.strokeCount == null ? "n/a" : payload.strokeCount;
  const rangeOfMotion = payload.rangeOfMotion == null ? "n/a" : payload.rangeOfMotion;
  const cadence = payload.cadenceSpm == null ? "n/a" : payload.cadenceSpm;
  const signalPoints = payload.signalPointCount == null ? "n/a" : payload.signalPointCount;
  const signalDropCount = payload.signalDropCount == null ? "n/a" : payload.signalDropCount;
  const rawSignalPoints = payload.rawSignalPointCount == null ? "n/a" : payload.rawSignalPointCount;
  const signalStrategy = payload.signalStrategy || "n/a";
  const signalSource = payload.signalSource || "n/a";
  const dominantSide = payload.dominantSide || "n/a";
  const analysisWindowSec = payload.analysisWindowSec == null ? "n/a" : payload.analysisWindowSec;
  const clipCount = payload.clipCount == null ? "n/a" : payload.clipCount;
  const score = payload.score == null ? "n/a" : payload.score.toFixed(2);
  const armsStraightScore = payload.armsStraightScore == null
    ? "n/a"
    : payload.armsStraightScore.toFixed(2);
  const backStraightScore = payload.backStraightScore == null
    ? "n/a"
    : payload.backStraightScore.toFixed(2);
  const progression = payload.progressionStep == null ? "n/a" : payload.progressionStep;
  const meanDistance = payload.meanDistance == null ? "n/a" : payload.meanDistance;
  const matchedPoints = payload.matchedPoints == null ? 0 : payload.matchedPoints;
  const frameCount = payload.frameCount == null ? 0 : payload.frameCount;
  const coordinateCount = payload.coordinateCount == null ? 0 : payload.coordinateCount;

  return [
    `movement gate: ${movementGate}`,
    `movement reason: ${payload.movementReason || "n/a"}`,
    `stroke count: ${strokeCount}`,
    `range of motion: ${rangeOfMotion}`,
    `cadence (spm): ${cadence}`,
    `dominant side: ${dominantSide}`,
    `signal strategy: ${signalStrategy}`,
    `signal points: ${signalPoints}`,
    `signal points raw: ${rawSignalPoints}`,
    `signal points dropped: ${signalDropCount}`,
    `signal source: ${signalSource}`,
    `analysis window (sec): ${analysisWindowSec}`,
    `clips observed: ${clipCount}`,
    `consistency score: ${score}`,
    `arms straight score: ${armsStraightScore}`,
    `back straight score: ${backStraightScore}`,
    `summary: ${payload.summary || "No summary"}`,
    `anchor landmark: ${payload.anchorLandmark || "n/a"}`,
    `progression step: ${progression}`,
    `consistency spread: ${meanDistance}`,
    `repeat samples: ${matchedPoints}`,
    `frames analyzed: ${frameCount}`,
    `coordinates used: ${coordinateCount}`
  ].join("\n");
}

function createWorkoutAnalysisAggregate() {
  return {
    clipCount: 0,
    movementQualifiedCount: 0,
    movementFailedCount: 0,
    strokeCount: 0,
    cadenceTotal: 0,
    cadenceCount: 0,
    rangeTotal: 0,
    rangeCount: 0,
    scoreTotal: 0,
    scoreCount: 0,
    armsTotal: 0,
    armsCount: 0,
    backTotal: 0,
    backCount: 0,
    dominantSideCounts: {
      left: 0,
      right: 0,
    },
    latestMovementQualified: null,
    latestMovementReason: null,
    latestSignalStrategy: "n/a",
    latestSignalSource: "n/a",
    latestAnalysisWindowSec: null,
    latestFrameCount: 0,
    latestCoordinateCount: 0,
    latestProgressionStep: null,
    latestMeanDistance: null,
    latestMatchedPoints: 0,
    latestAnchorLandmark: null,
  };
}

function summarizeConsistencyScore(score) {
  if (score == null) {
    return "Not enough valid strokes were detected to calculate a score.";
  }
  if (score >= 85) {
    return "Great stroke-to-stroke consistency for this workout.";
  }
  if (score >= 65) {
    return "Solid repeatability, but there is room to tighten it further.";
  }
  if (score >= 40) {
    return "Moderate drift detected. Focus on more repeatable body positions.";
  }
  return "Large drift detected. Recheck posture and frame setup.";
}

function sanitizeWorkoutAnalysisForPersistence(payload) {
  if (!payload || typeof payload !== "object") {
    return null;
  }

  if (payload.movementQualified === false) {
    return {
      ...payload,
      summary: "Not enough valid strokes were detected to calculate a score.",
      score: null,
      armsStraightScore: null,
      backStraightScore: null,
    };
  }

  return payload;
}

function resetWorkoutAnalysisAggregate() {
  workoutAnalysisAggregate = createWorkoutAnalysisAggregate();
}

function averageAggregateMetric(total, count) {
  if (!count) return null;
  return Number((total / count).toFixed(2));
}

function dominantSideFromAggregate(counts) {
  const left = counts?.left || 0;
  const right = counts?.right || 0;
  if (!left && !right) return null;
  return left >= right ? "left" : "right";
}

function updateWorkoutAnalysisAggregate(payload) {
  if (!workoutAnalysisAggregate) {
    resetWorkoutAnalysisAggregate();
  }
  if (!payload || typeof payload !== "object") {
    return null;
  }

  workoutAnalysisAggregate.clipCount += 1;
  if (payload.movementQualified === true) {
    workoutAnalysisAggregate.movementQualifiedCount += 1;
  } else if (payload.movementQualified === false) {
    workoutAnalysisAggregate.movementFailedCount += 1;
  }

  const strokeCount = asNumber(payload.strokeCount);
  if (strokeCount != null) {
    workoutAnalysisAggregate.strokeCount += Math.max(0, Math.round(strokeCount));
  }

  const cadenceSpm = asNumber(payload.cadenceSpm);
  if (cadenceSpm != null) {
    workoutAnalysisAggregate.cadenceTotal += cadenceSpm;
    workoutAnalysisAggregate.cadenceCount += 1;
  }

  const rangeOfMotion = asNumber(payload.rangeOfMotion);
  if (rangeOfMotion != null) {
    workoutAnalysisAggregate.rangeTotal += rangeOfMotion;
    workoutAnalysisAggregate.rangeCount += 1;
  }

  const score = asNumber(payload.score);
  if (score != null) {
    workoutAnalysisAggregate.scoreTotal += score;
    workoutAnalysisAggregate.scoreCount += 1;
  }

  const armsStraightScore = asNumber(payload.armsStraightScore);
  if (armsStraightScore != null) {
    workoutAnalysisAggregate.armsTotal += armsStraightScore;
    workoutAnalysisAggregate.armsCount += 1;
  }

  const backStraightScore = asNumber(payload.backStraightScore);
  if (backStraightScore != null) {
    workoutAnalysisAggregate.backTotal += backStraightScore;
    workoutAnalysisAggregate.backCount += 1;
  }

  if (payload.dominantSide === "left" || payload.dominantSide === "right") {
    workoutAnalysisAggregate.dominantSideCounts[payload.dominantSide] += 1;
  }

  workoutAnalysisAggregate.latestMovementQualified = payload.movementQualified ?? null;
  workoutAnalysisAggregate.latestMovementReason = payload.movementReason || null;
  workoutAnalysisAggregate.latestSignalStrategy = payload.signalStrategy || "n/a";
  workoutAnalysisAggregate.latestSignalSource = payload.signalSource || "n/a";
  workoutAnalysisAggregate.latestAnalysisWindowSec = payload.analysisWindowSec ?? null;
  workoutAnalysisAggregate.latestFrameCount = payload.frameCount ?? 0;
  workoutAnalysisAggregate.latestCoordinateCount = payload.coordinateCount ?? 0;
  workoutAnalysisAggregate.latestProgressionStep = payload.progressionStep ?? null;
  workoutAnalysisAggregate.latestMeanDistance = payload.meanDistance ?? null;
  workoutAnalysisAggregate.latestMatchedPoints = payload.matchedPoints ?? 0;
  workoutAnalysisAggregate.latestAnchorLandmark = payload.anchorLandmark || null;

  const aggregateScore = averageAggregateMetric(
    workoutAnalysisAggregate.scoreTotal,
    workoutAnalysisAggregate.scoreCount,
  );
  const aggregateMovementQualified = workoutAnalysisAggregate.scoreCount > 0
    ? true
    : (workoutAnalysisAggregate.movementQualifiedCount > 0
      ? true
      : (workoutAnalysisAggregate.movementFailedCount > 0 ? false : null));
  const aggregateMovementReason = aggregateMovementQualified === true
    ? `Movement gate passed on ${workoutAnalysisAggregate.scoreCount} of ${workoutAnalysisAggregate.clipCount} saved clips.`
    : workoutAnalysisAggregate.latestMovementReason;

  return {
    ...payload,
    clipCount: workoutAnalysisAggregate.clipCount,
    strokeCount: workoutAnalysisAggregate.strokeCount,
    cadenceSpm: averageAggregateMetric(
      workoutAnalysisAggregate.cadenceTotal,
      workoutAnalysisAggregate.cadenceCount,
    ),
    rangeOfMotion: averageAggregateMetric(
      workoutAnalysisAggregate.rangeTotal,
      workoutAnalysisAggregate.rangeCount,
    ),
    score: aggregateScore,
    summary: summarizeConsistencyScore(aggregateScore),
    armsStraightScore: averageAggregateMetric(
      workoutAnalysisAggregate.armsTotal,
      workoutAnalysisAggregate.armsCount,
    ),
    backStraightScore: averageAggregateMetric(
      workoutAnalysisAggregate.backTotal,
      workoutAnalysisAggregate.backCount,
    ),
    dominantSide: dominantSideFromAggregate(workoutAnalysisAggregate.dominantSideCounts),
    movementQualified: aggregateMovementQualified,
    movementReason: aggregateMovementReason,
    signalStrategy: workoutAnalysisAggregate.latestSignalStrategy,
    signalSource: workoutAnalysisAggregate.latestSignalSource,
    analysisWindowSec: workoutAnalysisAggregate.latestAnalysisWindowSec,
    frameCount: workoutAnalysisAggregate.latestFrameCount,
    coordinateCount: workoutAnalysisAggregate.latestCoordinateCount,
    progressionStep: workoutAnalysisAggregate.latestProgressionStep,
    meanDistance: workoutAnalysisAggregate.latestMeanDistance,
    matchedPoints: workoutAnalysisAggregate.latestMatchedPoints,
    anchorLandmark: workoutAnalysisAggregate.latestAnchorLandmark,
  };
}

function rememberWorkoutAnalysis(payload) {
  const persistedPayload = sanitizeWorkoutAnalysisForPersistence(payload);
  const aggregatePayload = updateWorkoutAnalysisAggregate(persistedPayload);
  latestWorkoutAnalysis = aggregatePayload;
  latestWorkoutAnalysisText = aggregatePayload ? formatAlignmentOutput(aggregatePayload) : "";
  latestWorkoutScore = aggregatePayload && aggregatePayload.score != null
    ? aggregatePayload.score
    : null;
  return {
    persistedPayload,
    aggregatePayload,
  };
}

function handleFormAudio(frameTime, analysisPayload) {
  if (!analysisPayload) {
    badArmsStartMs = null;
    badBackStartMs = null;
    return;
  }

  const armsScore = analysisPayload.armsStraightScore;
  const backScore = analysisPayload.backStraightScore;

  console.log("live form scores", { armsScore, backScore });

  if (armsScore != null && armsScore < armsStraightThreshold) {
    if (badArmsStartMs === null) {
      badArmsStartMs = frameTime;
    } else if (
      frameTime - badArmsStartMs >= formBadDurationMs &&
      frameTime - lastArmsPromptAtMs >= formPromptCooldownMs
    ) {
      console.log("Triggering straightenArms", { armsScore });
      playAudio("straightenArms");
      lastArmsPromptAtMs = frameTime;
      badArmsStartMs = frameTime;
    }
  } else {
    badArmsStartMs = null;
  }

  if (backScore != null && backScore < backStraightThreshold) {
    if (badBackStartMs === null) {
      badBackStartMs = frameTime;
    } else if (
      frameTime - badBackStartMs >= formBadDurationMs &&
      frameTime - lastBackPromptAtMs >= formPromptCooldownMs
    ) {
      console.log("Triggering straightenBack", { backScore });
      playAudio("straightenBack");
      lastBackPromptAtMs = frameTime;
      badBackStartMs = frameTime;
    }
  } else {
    badBackStartMs = null;
  }
}

async function analyzeLandmarkFrames(frames, createdAt, clipDurationSec, clipCount, options = {}) {
  if (!apiBase || !Array.isArray(frames) || frames.length < 2) {
    throw new Error("Not enough landmark frames to analyze.");
  }

  const dominantSideHint = options?.dominantSideHint === "left" || options?.dominantSideHint === "right"
    ? options.dominantSideHint
    : null;
  const signalStrategyHint = options?.signalStrategyHint === "upper_body_translation" ||
    options?.signalStrategyHint === "elbow_angle"
    ? options.signalStrategyHint
    : null;

  const response = await fetch(`${apiBase}/api/workouts/alignment-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      createdAt,
      clipDurationSec,
      clipCount,
      allowPartialMotion: true,
      dominantSideHint,
      signalStrategyHint,
      frames,
    })
  });

  let payload = {};
  try {
    payload = await response.json();
  } catch (err) {
    payload = {};
  }

  if (!response.ok) {
    const error = new Error(payload.error || "Unable to analyze clip");
    error.payload = payload;
    throw error;
  }

  return payload;
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
  let lastError = null;
  for (const candidate of MP_MODEL_CANDIDATE_PATHS) {
    try {
      poseLandmarker = await PoseLandmarker.createFromOptions(vision, {
        baseOptions: {
          modelAssetPath: candidate.path
        },
        runningMode: "VIDEO",
        numPoses: 1
      });
      debugCapture("pose_model_loaded", {
        requestedPoseModel,
        loadedPoseModel: candidate.key,
        modelAssetPath: candidate.path
      });
      return;
    } catch (err) {
      lastError = err;
      const message = err instanceof Error ? err.message : String(err);
      debugCapture("pose_model_load_failed", {
        requestedPoseModel,
        attemptedPoseModel: candidate.key,
        message
      });
    }
  }
  throw lastError || new Error("Unable to initialize pose model");
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
  if (!landmarks || landmarks.length === 0) return [];
  const lms = landmarks[0] || [];
  return lms.map((lm) => {
    if (!lm) return null;
    return {
      x: lm.x,
      y: lm.y,
      z: lm.z,
      visibility: lm.visibility ?? null
    };
  });
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
  return frameHasSideProfileChain(recordLandmarks(landmarks));
}

function resetRecordingTimers() {
  inFrameMs = 0;
  lastFrameTimestamp = null;
  nextAllowedRecordTime = 0;
  lastRawInFrameAtMs = null;
  waitingForStrokeGate = false;
}

function clearWorkoutStopTimeout() {
  if (workoutStopTimeout) {
    clearTimeout(workoutStopTimeout);
    workoutStopTimeout = null;
  }
}

function stopWorkoutForDurationLimit() {
  if (!stream) return;
  const completedAt = workoutStopDeadlineMs
    ? new Date(workoutStopDeadlineMs).toISOString()
    : new Date().toISOString();
  debugCapture("workout_duration_limit_reached", {
    completedAt,
    maxWorkoutDurationSec
  });
  updateCaptureSessionNotice(workoutDurationLimitReachedText);
  stopCamera({
    stopReason: "time-limit",
    completedAtOverride: completedAt
  });
}

function scheduleWorkoutStopTimeout() {
  clearWorkoutStopTimeout();
  if (!workoutStartAt) {
    workoutStopDeadlineMs = null;
    return;
  }

  const workoutStartMs = Date.parse(workoutStartAt);
  if (!Number.isFinite(workoutStartMs)) {
    workoutStopDeadlineMs = null;
    return;
  }

  workoutStopDeadlineMs = workoutStartMs + maxWorkoutDurationMs;
  const remainingMs = Math.max(0, workoutStopDeadlineMs - Date.now());
  workoutStopTimeout = setTimeout(() => {
    stopWorkoutForDurationLimit();
  }, remainingMs);
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

async function requestUploadUrl(contentType, durationSec, createdAt) {
  const response = await fetch(`${apiBase}/api/recordings/presign`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify({
      userId,
      contentType,
      durationSec,
      createdAt
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

async function uploadRecording(blob, createdAt, analysisPayload) {
  const contentType = blob.type || "video/webm";
  const durationSec = recordingDurationMs / 1000;

  if (analysisPayload?.score == null || analysisPayload.score > recordingScoreThreshold) {
    return false;
  }

  const presign = await requestUploadUrl(contentType, durationSec, createdAt);

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
    durationSec,
    createdAt,
    workoutId

  });

  return true;
}

async function recordClip(gateMovement = null) {
  if (!stream || recordingInProgress || reachedWorkoutClipLimit()) return;

  const recorderOptions = getRecorderOptions();
  if (recorderOptions === null) {
    poseStatus.textContent = "Recording not supported in this browser.";
    return;
  }

  const createdAt = new Date().toISOString();
  const chunks = [];
  recordedLandmarkFrames = [];
  const gateFrames = Array.isArray(gateMovement?.gateFrames)
    ? cloneJsonCompatible(gateMovement.gateFrames)
    : [];
  const gateDurationSec = asNumber(gateMovement?.gateDurationSec) ?? 0;

  recordingInProgress = true;
  recordingCancelled = false;
  waitingForStrokeGate = false;
  poseStatus.textContent = "Recording 5s clip...";
  debugCapture("recording_started", {
    clipIndex: movementWindowClipCount + 1,
    movementFrameCount: workoutMovementFrames.length,
    analysisWindowSec: getMovementWindowSec(),
    gateStrokeCount: gateMovement?.strokeCount ?? null,
  });

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
      resetMovementHistory();
      return;
    }

    if (!chunks.length) {
      resetMovementHistory();
      poseStatus.textContent = lastInFrame ? readyStatusText : defaultStatusText;
      return;
    }

    const clipDurationSec = recordingDurationMs / 1000;
    const preferredSide = gateMovement?.dominantSide || null;
    const trimmedRecordedSegment = trimFramesToActiveSegment(
      recordedLandmarkFrames,
      clipDurationSec,
      preferredSide,
    );
    const trimmedGateSegment = trimFramesToActiveSegment(
      gateFrames,
      gateDurationSec,
      preferredSide,
    );
    const localMovement = evaluateMovementGate(
      trimmedRecordedSegment.frames,
      trimmedRecordedSegment.durationSec
    );
    const gateLooksCleaner = trimmedGateSegment.frames.length >= activeSegmentMinFrames && (
      ((gateMovement?.movementQualified ?? false) && !localMovement.movementQualified) ||
      ((asNumber(gateMovement?.strokeCount) ?? 0) > (asNumber(localMovement.strokeCount) ?? 0)) ||
      (trimmedGateSegment.frames.length > trimmedRecordedSegment.frames.length)
    );
    const useGateFramesForAnalysis = gateLooksCleaner || (
      trimmedGateSegment.frames.length >= trimmedRecordedSegment.frames.length &&
      trimmedGateSegment.durationSec > trimmedRecordedSegment.durationSec
    );
    const scoringFrames = useGateFramesForAnalysis
      ? trimmedGateSegment.frames
      : trimmedRecordedSegment.frames;
    const scoringDurationSec = useGateFramesForAnalysis
      ? trimmedGateSegment.durationSec
      : trimmedRecordedSegment.durationSec;
    const scoringFrameSource = useGateFramesForAnalysis ? "gate_window" : "recorded_clip";
    const mergedMovement = {
      ...localMovement,
      movementQualified: gateMovement?.movementQualified ?? localMovement.movementQualified,
      movementReason: gateMovement?.movementReason || localMovement.movementReason,
      strokeCount: Math.max(
        asNumber(localMovement.strokeCount) ?? 0,
        asNumber(gateMovement?.strokeCount) ?? 0,
      ),
      cadenceSpm: Math.max(
        asNumber(localMovement.cadenceSpm) ?? 0,
        asNumber(gateMovement?.cadenceSpm) ?? 0,
      ),
      rangeOfMotion: Math.max(
        asNumber(localMovement.rangeOfMotion) ?? 0,
        asNumber(gateMovement?.rangeOfMotion) ?? 0,
      ),
      signalStrategy: gateMovement?.signalStrategy || localMovement.signalStrategy,
      signalSource: gateMovement?.signalSource || localMovement.signalSource,
      analysisWindowSec: Math.max(
        asNumber(localMovement.analysisWindowSec) ?? 0,
        asNumber(gateMovement?.analysisWindowSec) ?? 0,
      ),
      preRecordStrokeCount: asNumber(gateMovement?.strokeCount) ?? null,
      preRecordCadenceSpm: asNumber(gateMovement?.cadenceSpm) ?? null,
      preRecordRangeOfMotion: asNumber(gateMovement?.rangeOfMotion) ?? null,
    };
    resetMovementHistory();
    mergedMovement.clipCount = movementWindowClipCount;
    logMovementDebug("recording_stopped_gate_eval", mergedMovement, {
      clipIndex: movementWindowClipCount
    });
    const blob = new Blob(chunks, { type: recorder.mimeType || "video/webm" });
    let analysisPayload = null;
    try {
      analysisPayload = await analyzeLandmarkFrames(
        scoringFrames,
        createdAt,
        scoringDurationSec,
        movementWindowClipCount + 1,
        {
          dominantSideHint: gateMovement?.dominantSide || localMovement?.dominantSide || null,
          signalStrategyHint: gateMovement?.signalStrategy || localMovement?.signalStrategy || null,
        }
      );
      debugCapture("server_analysis_ok", {
        clipIndex: movementWindowClipCount,
        strokeCount: analysisPayload.strokeCount,
        movementReason: analysisPayload.movementReason,
        score: analysisPayload.score,
        scoringFrameSource,
        scoringFrameCount: scoringFrames.length,
      });
    } catch (err) {
      const payload = err && typeof err === "object" ? err.payload : null;
      if (payload && typeof payload === "object") {
        debugCapture("server_analysis_rejected", {
          clipIndex: movementWindowClipCount,
          status: payload.status || "unknown",
          error: payload.error || "unknown",
          movementReason: payload.movementReason || "unknown",
          strokeCount: payload.strokeCount,
          rangeOfMotion: payload.rangeOfMotion,
          signalPointCount: payload.signalPointCount,
          rawSignalPointCount: payload.rawSignalPointCount,
          signalDropCount: payload.signalDropCount
        });
        poseStatus.textContent = payload.error || "Clip rejected";
      } else {
        const message = err instanceof Error ? err.message : String(err);
        debugCapture("server_analysis_failed", {
          clipIndex: movementWindowClipCount,
          message
        });
        poseStatus.textContent = "Analysis failed";
      }
      return;
    }

    try {
      const saved = await uploadRecording(
        blob,
        createdAt,
        analysisPayload
      );

      if (!saved) {
        poseStatus.textContent = "Clip did not meet save requirements.";
        return;
      }

    } catch (err) {
      console.error("Recording upload failed:", err);
      poseStatus.textContent = err instanceof Error ? err.message : "Upload failed";
      return;
    }
    movementWindowClipCount += 1;
    const rememberedAnalysis = rememberWorkoutAnalysis({
      ...analysisPayload,
      ...mergedMovement,
      anchorLandmark: analysisPayload?.anchorLandmark ?? null,
      frameCount: analysisPayload?.frameCount ?? 0,
      coordinateCount: analysisPayload?.coordinateCount ?? 0,
      progressionStep: analysisPayload?.progressionStep ?? null,
      meanDistance: analysisPayload?.meanDistance ?? null,
      matchedPoints: analysisPayload?.matchedPoints ?? 0,
      score: analysisPayload?.score ?? null,
      summary: analysisPayload?.summary || mergedMovement.movementReason,
      armsStraightScore: analysisPayload?.armsStraightScore ?? null,
      backStraightScore: analysisPayload?.backStraightScore ?? null,
    });
    rememberClipDebugSnapshot(buildClipDebugSnapshot({
      createdAt,
      clipIndex: movementWindowClipCount,
      recordedFrames: recordedLandmarkFrames,
      gateFrames,
      trimmedRecordedFrames: trimmedRecordedSegment.frames,
      trimmedGateFrames: trimmedGateSegment.frames,
      scoringFrames,
      scoringFrameSource,
      scoringDurationSec,
      gateMovement,
      localMovement,
      mergedMovement,
      analysisPayload,
      persistedPayload: rememberedAnalysis?.persistedPayload ?? null,
      aggregatePayload: rememberedAnalysis?.aggregatePayload ?? null,
    }));
    debugCapture("clip_saved", {
      clipIndex: movementWindowClipCount,
      strokeCount: (analysisPayload && analysisPayload.strokeCount) || mergedMovement.strokeCount
    });
    poseStatus.textContent = reachedWorkoutClipLimit()
      ? workoutClipLimitReachedText
      : "Clip analyzed and saved";

    playAudio("recordingSaved");
  };

  recorder.start();
  recorderStopTimeout = setTimeout(() => {
    if (recorder.state !== "inactive") {
      recorder.stop();
    }
  }, recordingDurationMs);
}

async function saveWorkoutEntry(durationSec, startedAt, completedAt, workoutId = null, workoutAnalysis = null, workoutAnalysisText = "", workoutScore = null) {

  if (!apiBase) {
    console.warn("Workout not saved: missing apiBase");
    return;
  }
  const fallbackSummary = "Not enough valid strokes were detected to calculate a score.";
  try {
    const response = await fetch(`${apiBase}/api/workouts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        durationSec,
        startedAt,
        completedAt,
        workoutId: workoutId,
        summary: workoutAnalysis?.summary || fallbackSummary,
        workoutScore: workoutScore,
        alignmentDetails: workoutAnalysisText,
        strokeCount: workoutAnalysis?.strokeCount ?? null,
        cadenceSpm: workoutAnalysis?.cadenceSpm ?? null,
        rangeOfMotion: workoutAnalysis?.rangeOfMotion ?? null,
        armsStraightScore: workoutAnalysis?.armsStraightScore ?? null,
        backStraightScore: workoutAnalysis?.backStraightScore ?? null,
        dominantSide: workoutAnalysis?.dominantSide || null,
      })
    });
    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.error || "Unable to save workout");
    }
    poseStatus.textContent = "Workout saved";
    setTimeout(() => {
      const detailUrl = workoutDetailBase.replace("__WORKOUT_ID__", payload.workoutId);
      const fallbackUrl = `/workout-summaries/${payload.workoutId}?captured=1`;
      window.location.href = detailUrl
        ? `${detailUrl}${detailUrl.includes("?") ? "&" : "?"}captured=1`
        : fallbackUrl;
    }, 500);

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
  scheduleWorkoutStopTimeout();
  resetMovementHistory();
  movementWindowClipCount = 0;
  lastMovementDebugLogAtMs = 0;
  latestWorkoutAnalysis = null;
  latestWorkoutAnalysisText = "";
  latestWorkoutScore = null;
  resetWorkoutAnalysisAggregate();
  resetClipDebugSnapshots();
  updateCaptureSessionNotice();
  ensureDebugExportControls();
  debugCapture("camera_started", {
    facingMode: preferredFacingMode
  });

  bodyInFramePromptPlayed = false;
  readyToBeginPromptPlayed = false;
  noAthletePromptPlayed = false;
  badArmsStartMs = null;
  badBackStartMs = null;
  lastArmsPromptAtMs = 0;
  lastBackPromptAtMs = 0;
  lastNoAthletePromptAtMs = 0;

  if (running) {
    requestAnimationFrame(loop);
  }
  playAudio("readyToBegin", { queued: false });
  readyToBeginPromptPlayed = true;

}

function stopCamera({ stopReason = "manual", completedAtOverride = null } = {}) {
  running = false;
  cancelActiveRecording();
  audioQueue.length = 0;
  audioPlaying = false;
  Object.values(audioClips).forEach((clip) => {
    clip.pause();
    clip.currentTime = 0;
  });
  clearWorkoutStopTimeout();
  const deadlineCompletedAt = workoutStopDeadlineMs
    ? new Date(workoutStopDeadlineMs).toISOString()
    : null;
  const completedAt = completedAtOverride || (
    stopReason === "time-limit" && deadlineCompletedAt
      ? deadlineCompletedAt
      : new Date().toISOString()
  );
  workoutStopDeadlineMs = null;
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
  recordedLandmarkFrames = [];
  resetMovementHistory();
  movementWindowClipCount = 0;
  lastMovementDebugLogAtMs = 0;

  bodyInFramePromptPlayed = false;
  readyToBeginPromptPlayed = false;
  noAthletePromptPlayed = false;
  badArmsStartMs = null;
  badBackStartMs = null;

  if (viewport) {
    viewport.classList.remove("capture__viewport--unmirror");
  }

  if (workoutStartAt) {
    const durationMs = Date.parse(completedAt) - Date.parse(workoutStartAt);
    const durationSec = Math.min(
      maxWorkoutDurationSec,
      Math.max(1, Math.round(durationMs / 1000))
    );
    console.log("SAVING WORKOUT", {
      latestWorkoutAnalysis,
      latestWorkoutScore,
      latestWorkoutAnalysisText
    });
    saveWorkoutEntry(durationSec, workoutStartAt, completedAt, workoutId, latestWorkoutAnalysis, latestWorkoutAnalysisText, latestWorkoutScore);
  }
  workoutStartAt = null;
  latestWorkoutAnalysis = null;
  latestWorkoutAnalysisText = "";
  latestWorkoutScore = null;
  resetWorkoutAnalysisAggregate();
  workoutId = null;
  if (stopReason !== "time-limit") {
    updateCaptureSessionNotice();
  }

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

function evaluateLiveFormScores(landmarks) {
  if (!landmarks || !landmarks.length) {
    return {
      armsStraightScore: null,
      backStraightScore: null
    };
  }

  const dominantSide = detectDominantSideFromFrames([recordLandmarks(landmarks)]);
  const side = dominantSide === "left"
    ? { shoulder: 11, elbow: 13, wrist: 15, hip: 23, head: 7 }
    : { shoulder: 12, elbow: 14, wrist: 16, hip: 24, head: 8 };

  const frame = recordLandmarks(landmarks);

  const shoulder = usableLandmark(frame, side.shoulder, motionSignalVisibilityFloor);
  const elbow = usableLandmark(frame, side.elbow, motionSignalVisibilityFloor);
  const wrist = usableLandmark(frame, side.wrist, motionSignalVisibilityFloor);
  const hip = usableLandmark(frame, side.hip, motionSignalVisibilityFloor);
  const head = usableLandmark(frame, side.head, motionSignalVisibilityFloor);

  let armsStraightScore = null;
  let backStraightScore = null;

  const elbowAngleNorm = computeElbowAngleNormalized(shoulder, elbow, wrist);
  if (elbowAngleNorm != null) {
    const elbowClosenessToStraight = 1 - Math.abs(1 - elbowAngleNorm);
    armsStraightScore = Number((elbowClosenessToStraight * 100).toFixed(2));
  }

  const backAngleNorm = computeElbowAngleNormalized(hip, shoulder, head);
  if (backAngleNorm != null) {
    const backClosenessToStraight = 1 - Math.abs(1 - backAngleNorm);
    backStraightScore = Number((backClosenessToStraight * 100).toFixed(2));
  }

  return {
    armsStraightScore,
    backStraightScore
  };
}

function loop() {
  if (!running) return;
  if (workoutStopDeadlineMs && Date.now() >= workoutStopDeadlineMs) {
    stopWorkoutForDurationLimit();
    return;
  }
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
      const frameTime = performance.now();
      const result = poseLandmarker.detectForVideo(video, frameTime);
      drawLandmarks(result.landmarks);

      const recordedFrame = recordLandmarks(result.landmarks);
      if (recordingInProgress) {
        recordedLandmarkFrames.push(recordedFrame);
      }
      appendMovementFrame(recordedFrame, frameTime);

      if (recordingInProgress) {
        const shouldLogRecording = captureDebugEnabled &&
          frameTime - lastMovementDebugLogAtMs >= movementDebugLogIntervalMs;
        if (shouldLogRecording) {
          const recordingGate = evaluateMovementGate(
            workoutMovementFrames,
            getMovementWindowSec()
          );
          logMovementDebug("recording_progress", recordingGate);
          lastMovementDebugLogAtMs = frameTime;
        }
      }

      const rawInFrame = fullBodyInFrame(result.landmarks);
      if (rawInFrame) {
        lastRawInFrameAtMs = frameTime;
      }
      const inFrame = rawInFrame || (
        lastRawInFrameAtMs !== null &&
        frameTime - lastRawInFrameAtMs <= inFrameDropoutGraceMs
      );

      if (running && stream && inFrame) {
        const liveFormScores = evaluateLiveFormScores(result.landmarks);
        handleFormAudio(frameTime, liveFormScores);
      } else {
        badArmsStartMs = null;
        badBackStartMs = null;
      }

      if (!rawInFrame) {
        bodyInFramePromptPlayed = false;
        readyToBeginPromptPlayed = false;

        if (
          frameTime >= noAthleteDelayMs &&
          frameTime - lastNoAthletePromptAtMs >= noAthleteRepeatMs
        ) {
          playAudio("noAthleteDetected", { queued: false });
          lastNoAthletePromptAtMs = frameTime;
          noAthletePromptPlayed = true;
        }
      } else {
        noAthletePromptPlayed = false;

        if (!bodyInFramePromptPlayed) {
          playAudio("bodyInFrame", { queued: false });
          bodyInFramePromptPlayed = true;
        }
      }

      lastInFrame = inFrame;

      poseStatus.classList.toggle("ready", inFrame);
      if (!recordingInProgress) {
        if (!inFrame) {
          waitingForStrokeGate = false;
          poseStatus.textContent = defaultStatusText;
        } else if (reachedWorkoutClipLimit()) {
          waitingForStrokeGate = false;
          poseStatus.textContent = workoutClipLimitReachedText;
        } else if (waitingForStrokeGate) {
          poseStatus.textContent = "Row until at least 3 strokes are detected.";
        } else {
          poseStatus.textContent = readyStatusText;
        }
      }


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
          !reachedWorkoutClipLimit() &&
          frameTime >= nextAllowedRecordTime) {
        const movementWindowSec = getMovementWindowSec();
        const liveMovement = evaluateMovementGate(
          workoutMovementFrames,
          movementWindowSec
        );
        const shouldLogGate = captureDebugEnabled &&
          (frameTime - lastMovementDebugLogAtMs >= movementDebugLogIntervalMs || !liveMovement.movementQualified);
        if (shouldLogGate) {
          logMovementDebug("pre_record_gate_check", liveMovement, {
            inFrame,
            rawInFrame,
            inFrameGraceActive: !rawInFrame && inFrame,
            canRecordNow: liveMovement.movementQualified
          });
          lastMovementDebugLogAtMs = frameTime;
        }

        if (!liveMovement.movementQualified) {
          waitingForStrokeGate = true;
          poseStatus.textContent = "Row until at least 3 strokes are detected.";
          nextAllowedRecordTime = frameTime + movementGateRetryMs;
        } else {
          waitingForStrokeGate = false;
          inFrameMs = 0;
          nextAllowedRecordTime = frameTime + recordingCooldownMs;
          recordClip({
            ...liveMovement,
            gateFrames: workoutMovementFrames,
            gateDurationSec: movementWindowSec,
          });
        }
      } else if (
        captureDebugEnabled &&
        !recordingInProgress &&
        frameTime - lastMovementDebugLogAtMs >= movementDebugLogIntervalMs
      ) {
        const snapshotMovement = evaluateMovementGate(
          workoutMovementFrames,
          getMovementWindowSec()
        );
        logMovementDebug("live_snapshot", snapshotMovement, {
          inFrame,
          rawInFrame,
          inFrameGraceActive: !rawInFrame && inFrame
        });
        lastMovementDebugLogAtMs = frameTime;
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
  workoutId = uuidv4();
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
ensureDebugExportControls();
window.__rowlyticsCaptureDebugEnabled = captureDebugEnabled;
window.__rowlyticsCaptureExportEnabled = captureExportEnabled;
window.__rowlyticsExportLastClipDebugSnapshot = exportLastClipDebugSnapshot;
window.__rowlyticsExportAllClipDebugSnapshots = exportAllClipDebugSnapshots;
window.__rowlyticsCaptureState = () => ({
  inFrameMs: Number(inFrameMs.toFixed(0)),
  recordingInProgress,
  nextAllowedRecordTime,
  movementFrameCount: workoutMovementFrames.length,
  movementWindowSec: getMovementWindowSec(),
  movementWindowClipCount,
  lastInFrame,
  lastRawInFrameAtMs,
  waitingForStrokeGate,
  workoutStopDeadlineMs,
  requestedPoseModel,
  modelCandidates: MP_MODEL_CANDIDATE_PATHS.map((item) => item.key),
  latestWorkoutAnalysis,
  latestClipDebugSnapshot,
  workoutClipDebugSnapshots,
});
debugCapture("debug_enabled", {
  enabled: captureDebugEnabled,
  exportEnabled: captureExportEnabled
});
