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
const captureSessionNotice = document.getElementById("captureSessionNotice");
const apiBase = (document.body?.dataset?.apiBase || "").replace(/\/+$/, "");
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
const inFrameThresholdMs = 5000;
const recordingCooldownMs = 3000;
const inFrameDropoutGraceMs = 600;
const movementGateRetryMs = 1200;
const movementDebugLogIntervalMs = 500;
const workoutSummaryText = "Workout session";
const workoutDurationLimitText = "Workouts automatically stop after 1 hour.";
const workoutDurationLimitReachedText = "Workout reached the 1-hour limit and stopped automatically.";
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
const captureDebugEnabled = (() => {
  try {
    const fromQuery = urlParams?.get("captureDebug");
    if (fromQuery === "1" || fromQuery === "true") return true;
    return window.localStorage?.getItem("rowlytics_capture_debug") === "1";
  } catch (err) {
    return false;
  }
})();

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

function setupCameraSwitchControl() {
  if (!switchCameraBtn) return;
  if (isLikelyMobileDevice()) {
    switchCameraBtn.classList.remove("capture__switch--hidden");
    updateSwitchCameraButton();
    return;
  }
  switchCameraBtn.classList.add("capture__switch--hidden");
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
    `score: ${score}`,
    `summary: ${payload.summary || "No summary"}`,
    `anchor landmark: ${payload.anchorLandmark || "n/a"}`,
    `progression step: ${progression}`,
    `mean distance: ${meanDistance}`,
    `matched points: ${matchedPoints}`,
    `frames analyzed: ${frameCount}`,
    `coordinates used: ${coordinateCount}`
  ].join("\n");
}

function rememberWorkoutAnalysis(payload) {
  latestWorkoutAnalysis = payload;
  latestWorkoutAnalysisText = formatAlignmentOutput(payload);
  latestWorkoutScore = payload && payload.score != null ? payload.score : null;
}

async function analyzeLandmarkFrames(frames, createdAt, clipDurationSec, clipCount) {
  if (!apiBase || !Array.isArray(frames) || frames.length < 2) {
    throw new Error("Not enough landmark frames to analyze.");
  }

  const response = await fetch(`${apiBase}/api/workouts/alignment-preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      createdAt,
      clipDurationSec,
      clipCount,
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
  const lms = landmarks[0];
  const margin = 0.06;

  const isVisibleInFrame = (lm) => {
    if (!lm) return false;
    const visibility = lm.visibility == null ? 1 : lm.visibility;
    return visibility >= sideProfileVisibilityThreshold &&
      lm.x >= margin &&
      lm.x <= 1 - margin &&
      lm.y >= margin &&
      lm.y <= 1 - margin;
  };

  const sideChainReady = (indices) => {
    const visibleCount = indices.reduce((count, index) => {
      return count + (isVisibleInFrame(lms[index]) ? 1 : 0);
    }, 0);
    const hasShoulder = isVisibleInFrame(lms[indices[0]]);
    const hasHip = isVisibleInFrame(lms[indices[3]]);
    return hasShoulder && hasHip && visibleCount >= sideProfileMinVisiblePoints;
  };

  return sideChainReady(SIDE_PROFILE_LEFT) || sideChainReady(SIDE_PROFILE_RIGHT);
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
  recordedLandmarkFrames = [];

  recordingInProgress = true;
  recordingCancelled = false;
  waitingForStrokeGate = false;
  poseStatus.textContent = "Recording 5s clip...";
  debugCapture("recording_started", {
    clipIndex: movementWindowClipCount + 1,
    movementFrameCount: workoutMovementFrames.length,
    analysisWindowSec: getMovementWindowSec()
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
      return;
    }

    if (!chunks.length) {
      poseStatus.textContent = lastInFrame ? readyStatusText : defaultStatusText;
      return;
    }

    movementWindowClipCount += 1;
    const movementWindowSec = getMovementWindowSec();
    const localMovement = evaluateMovementGate(
      workoutMovementFrames,
      movementWindowSec
    );
    localMovement.clipCount = movementWindowClipCount;
    logMovementDebug("recording_stopped_gate_eval", localMovement, {
      clipIndex: movementWindowClipCount
    });
    if (!localMovement.movementQualified) {
      waitingForStrokeGate = true;
      poseStatus.textContent = "Take a few strokes before recording.";
      return;
    }

    const blob = new Blob(chunks, { type: recorder.mimeType || "video/webm" });
    let analysisPayload = null;
    try {
      analysisPayload = await analyzeLandmarkFrames(
        workoutMovementFrames,
        createdAt,
        movementWindowSec,
        movementWindowClipCount
      );
      debugCapture("server_analysis_ok", {
        clipIndex: movementWindowClipCount,
        strokeCount: analysisPayload.strokeCount,
        movementReason: analysisPayload.movementReason,
        score: analysisPayload.score
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
      await uploadRecording(blob, createdAt);
    } catch (err) {
      console.error("Recording upload failed:", err);
      poseStatus.textContent = "Upload failed";
      return;
    }

    rememberWorkoutAnalysis({ ...localMovement, ...analysisPayload });
    debugCapture("clip_saved", {
      clipIndex: movementWindowClipCount,
      strokeCount: (analysisPayload && analysisPayload.strokeCount) || localMovement.strokeCount
    });
    poseStatus.textContent = "Clip analyzed and saved";
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
  const fallbackSummary = "Not enough valid strokes were detected to calculate a score.";
  try {
    const response = await fetch(`${apiBase}/api/workouts`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        durationSec,
        startedAt,
        completedAt,
        summary: latestWorkoutAnalysis?.summary || fallbackSummary,
        workoutScore: latestWorkoutScore,
        alignmentDetails: latestWorkoutAnalysisText,
        strokeCount: latestWorkoutAnalysis?.strokeCount ?? null,
        cadenceSpm: latestWorkoutAnalysis?.cadenceSpm ?? null,
        rangeOfMotion: latestWorkoutAnalysis?.rangeOfMotion ?? null,
        dominantSide: latestWorkoutAnalysis?.dominantSide || null,
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
  scheduleWorkoutStopTimeout();
  workoutMovementFrames = [];
  workoutMovementFrameTimesMs = [];
  movementWindowClipCount = 0;
  lastMovementDebugLogAtMs = 0;
  latestWorkoutAnalysis = null;
  latestWorkoutAnalysisText = "";
  latestWorkoutScore = null;
  updateCaptureSessionNotice();
  debugCapture("camera_started", {
    facingMode: preferredFacingMode
  });

  if (running) {
    requestAnimationFrame(loop);
  }
}

function stopCamera({ stopReason = "manual", completedAtOverride = null } = {}) {
  running = false;
  cancelActiveRecording();
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
  workoutMovementFrames = [];
  workoutMovementFrameTimesMs = [];
  movementWindowClipCount = 0;
  lastMovementDebugLogAtMs = 0;
  if (viewport) {
    viewport.classList.remove("capture__viewport--unmirror");
  }

  if (workoutStartAt) {
    const durationMs = Date.parse(completedAt) - Date.parse(workoutStartAt);
    const durationSec = Math.min(
      maxWorkoutDurationSec,
      Math.max(1, Math.round(durationMs / 1000))
    );
    saveWorkoutEntry(durationSec, workoutStartAt, completedAt);
  }
  workoutStartAt = null;
  latestWorkoutAnalysis = null;
  latestWorkoutAnalysisText = "";
  latestWorkoutScore = null;
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

      lastInFrame = inFrame;
      poseStatus.classList.toggle("ready", inFrame);
      if (!recordingInProgress) {
        if (!inFrame) {
          waitingForStrokeGate = false;
          poseStatus.textContent = defaultStatusText;
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
          recordClip();
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
window.__rowlyticsCaptureDebugEnabled = captureDebugEnabled;
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
});
debugCapture("debug_enabled", {
  enabled: captureDebugEnabled
});
