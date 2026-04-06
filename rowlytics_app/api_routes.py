"""API routes for Rowlytics."""

import base64
import json
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from uuid import uuid4

from flask import Blueprint, jsonify, request, session

try:
    from botocore.exceptions import ClientError
except ImportError:  # pragma: no cover - boto3 only needed when AWS is used
    ClientError = None

from rowlytics_app.auth.cognito import delete_cognito_user
from rowlytics_app.cv.alignment import PracticeStrokeAssembler
from rowlytics_app.cv.feature_extraction.angles import normalized_joint_angle
from rowlytics_app.services.dynamodb import (
    display_name_exists,
    fetch_team_members,
    fetch_team_members_page,
    fetch_user_profile,
    get_ddb_tables,
    get_recordings_table,
    get_team,
    get_team_membership,
    get_teams_table,
    get_workouts_table,
    list_recordings,
    list_recordings_page,
    list_team_memberships,
    list_workouts_page,
    normalize_display_name,
    now_iso,
    team_name_exists,
)
from rowlytics_app.services.s3 import UPLOAD_BUCKET_NAME, get_s3_client

logger = logging.getLogger(__name__)

api_bp = Blueprint("api", __name__, url_prefix="/api")

ALLOWED_TEAM_ROLES = {"coach", "rower"}
MEDIAPIPE_LANDMARK_NAMES = (
    "nose",
    "left_eye_inner",
    "left_eye",
    "left_eye_outer",
    "right_eye_inner",
    "right_eye",
    "right_eye_outer",
    "left_ear",
    "right_ear",
    "mouth_left",
    "mouth_right",
    "left_shoulder",
    "right_shoulder",
    "left_elbow",
    "right_elbow",
    "left_wrist",
    "right_wrist",
    "left_pinky",
    "right_pinky",
    "left_index",
    "right_index",
    "left_thumb",
    "right_thumb",
    "left_hip",
    "right_hip",
    "left_knee",
    "right_knee",
    "left_ankle",
    "right_ankle",
    "left_heel",
    "right_heel",
    "left_foot_index",
    "right_foot_index",
)
ALIGNMENT_ANCHOR_CANDIDATES = (
    "left_wrist",
    "right_wrist",
    "left_elbow",
    "right_elbow",
    "nose",
)
# Current movement analysis assumes the user is captured primarily from one side.
SIDE_PROFILE_LANDMARKS = {
    "left": (
        "left_shoulder",
        "left_elbow",
        "left_wrist",
        "left_hip",
        "left_knee",
        "left_ankle",
    ),
    "right": (
        "right_shoulder",
        "right_elbow",
        "right_wrist",
        "right_hip",
        "right_knee",
        "right_ankle",
    ),
}
# Landmarks below this visibility threshold are ignored.
# This means lighting, clothing, body occlusion, camera quality, and framing
# can disproportionately reduce usable data and degrade scoring reliability.
MIN_VISIBILITY_FOR_ANALYSIS = 0.12
MIN_STROKES_REQUIRED = 3
MIN_RANGE_OF_MOTION = 0.12
MIN_STROKE_CYCLE_SEC = 0.35
MAX_STROKE_CYCLE_SEC = 6.0
MOTION_TURN_EPSILON = 0.0012
MIN_STROKE_AMPLITUDE = 0.009
STROKE_AMPLITUDE_SCALE = 0.14
ANGLE_MIN_RANGE_OF_MOTION = 0.06
ANGLE_MIN_STROKE_AMPLITUDE = 0.006
ANGLE_STROKE_AMPLITUDE_SCALE = 0.11
MOTION_SPIKE_MAX_DELTA_PER_SEC = 1.2
MOTION_SPIKE_BASE_DELTA = 0.075
MAX_WORKOUT_DURATION_SEC = 60 * 60


class MovementGateError(ValueError):
    def __init__(self, message, payload=None):
        super().__init__(message)
        self.payload = payload or {}


def _coerce_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _build_coordinate_series(frames, clip_duration_sec):
    if not isinstance(frames, list) or len(frames) < 2:
        raise ValueError("frames must contain at least 2 entries")

    frame_count = len(frames)
    frame_interval = clip_duration_sec / max(frame_count - 1, 1)
    coordinates = []

    for frame_index, frame in enumerate(frames):
        if not isinstance(frame, list):
            continue
        timestamp = round(frame_index * frame_interval, 6)
        for landmark_index, landmark_name in enumerate(MEDIAPIPE_LANDMARK_NAMES):
            if landmark_index >= len(frame):
                break
            landmark = frame[landmark_index]
            if not isinstance(landmark, dict):
                continue
            x_val = _coerce_float(landmark.get("x"))
            y_val = _coerce_float(landmark.get("y"))
            visibility = _coerce_float(landmark.get("visibility"))
            if x_val is None or y_val is None:
                continue
            if visibility is not None and visibility < MIN_VISIBILITY_FOR_ANALYSIS:
                continue
            coordinates.append({
                "name": landmark_name,
                "time": timestamp,
                "x": x_val,
                "y": y_val,
            })

    if len(coordinates) < 2:
        raise ValueError("landmark frames did not contain enough usable coordinates")

    return coordinates


def _smooth_coordinates(coordinates, alpha=0.35):
    grouped = {}
    for item in coordinates:
        grouped.setdefault(item["name"], []).append(item)

    smoothed = []
    for name, items in grouped.items():
        points = sorted(items, key=lambda item: item["time"])
        smooth_x = points[0]["x"]
        smooth_y = points[0]["y"]
        for point in points:
            smooth_x = alpha * point["x"] + (1 - alpha) * smooth_x
            smooth_y = alpha * point["y"] + (1 - alpha) * smooth_y
            smoothed.append({
                "name": name,
                "time": point["time"],
                "x": smooth_x,
                "y": smooth_y,
            })

    return sorted(smoothed, key=lambda item: (item["time"], item["name"]))


# Note: this heuristic picks the side with more detected landmarks, which works best
# for a clean side-profile recording. It is less reliable for diagonal camera angles,
# mirrored views, or partial visibility.
def _detect_dominant_side(coordinates):
    counts = {}
    for side_name, landmark_names in SIDE_PROFILE_LANDMARKS.items():
        counts[side_name] = sum(1 for item in coordinates if item["name"] in landmark_names)
    return "left" if counts.get("left", 0) >= counts.get("right", 0) else "right"


def _select_anchor_landmark(coordinates, candidates=None):
    best_name = None
    best_coords = []
    best_range = -1.0
    best_count = -1

    anchor_candidates = candidates or ALIGNMENT_ANCHOR_CANDIDATES
    for candidate in anchor_candidates:
        candidate_coords = [item for item in coordinates if item["name"] == candidate]
        if len(candidate_coords) < 2:
            continue
        min_x = min(item["x"] for item in candidate_coords)
        max_x = max(item["x"] for item in candidate_coords)
        x_range = max_x - min_x
        if x_range > best_range or (x_range == best_range and len(candidate_coords) > best_count):
            best_name = candidate
            best_coords = candidate_coords
            best_range = x_range
            best_count = len(candidate_coords)

    if not best_name:
        raise ValueError("unable to select an anchor landmark from frames")

    return best_name, sorted(best_coords, key=lambda item: item["time"])


def _alignment_score(mean_distance):
    if mean_distance is None:
        return None
    raw_score = 100 - (mean_distance * 140)
    return round(max(0, min(100, raw_score)), 2)


def _landmark_weight(name):
    if "shoulder" in name or "hip" in name:
        return 1.15
    if "elbow" in name or "knee" in name:
        return 1.0
    if "wrist" in name:
        return 0.85
    if "ankle" in name:
        return 0.65
    if name == "nose":
        return 0.7
    return 1.0


def _summarize_alignment(score):
    if score is None:
        return "Not enough matching coordinates to calculate a consistency score for this clip."
    if score >= 85:
        return "Great consistency for this clip."
    if score >= 65:
        return "Solid consistency, but there is room to tighten it further."
    if score >= 40:
        return "Moderate drift detected. Focus on more repeatable body positions."
    return "Large drift detected. Recheck posture and frame setup."


def _compute_elbow_angle_normalized(shoulder, elbow, wrist):
    if not shoulder or not elbow or not wrist:
        return None

    try:
        return normalized_joint_angle(shoulder, elbow, wrist)
    except ValueError:
        return None


# Motion features are currently derived from upper-body landmark relationships.
# This assumes the selected landmarks are visible and representative across users.
# Differences in body proportions, adaptive rowing form, mobility limitations,
# or non-standard technique may affect how well the current model generalizes.
def _extract_motion_series_candidates(coordinates, dominant_side):
    wrist_name = f"{dominant_side}_wrist"
    elbow_name = f"{dominant_side}_elbow"
    shoulder_name = f"{dominant_side}_shoulder"
    hip_name = f"{dominant_side}_hip"

    by_time = {}
    for item in coordinates:
        by_time.setdefault(item["time"], {})[item["name"]] = item

    translation_series = []
    angle_series = []
    for timestamp in sorted(by_time.keys()):
        frame = by_time[timestamp]
        shoulder = frame.get(shoulder_name)
        elbow = frame.get(elbow_name)
        wrist = frame.get(wrist_name)
        hip = frame.get(hip_name)

        value = None
        source = None
        if shoulder and wrist:
            value = wrist["x"] - shoulder["x"]
            source = f"{wrist_name}-{shoulder_name}"
        elif shoulder and elbow:
            value = elbow["x"] - shoulder["x"]
            source = f"{elbow_name}-{shoulder_name}"
        elif hip and wrist:
            value = wrist["x"] - hip["x"]
            source = f"{wrist_name}-{hip_name}"
        elif hip and elbow:
            value = elbow["x"] - hip["x"]
            source = f"{elbow_name}-{hip_name}"
        elif hip and shoulder:
            value = shoulder["x"] - hip["x"]
            source = f"{shoulder_name}-{hip_name}"

        if value is not None:
            if hip and shoulder:
                torso_length = (
                    (shoulder["x"] - hip["x"]) ** 2
                    + (shoulder["y"] - hip["y"]) ** 2
                ) ** 0.5
                if torso_length > 0.04:
                    value = value / torso_length
                    source = f"{source}_norm"
            translation_series.append({
                "time": timestamp,
                "value": value,
                "source": source,
            })

        angle_value = _compute_elbow_angle_normalized(shoulder, elbow, wrist)
        if angle_value is not None:
            angle_series.append({
                "time": timestamp,
                "value": angle_value,
                "source": f"{dominant_side}_elbow_angle_norm",
            })

    return [
        {
            "signalStrategy": "upper_body_translation",
            "rawSeries": translation_series,
            "minRangeOfMotion": MIN_RANGE_OF_MOTION,
            "minStrokeAmplitude": MIN_STROKE_AMPLITUDE,
            "strokeAmplitudeScale": STROKE_AMPLITUDE_SCALE,
        },
        {
            "signalStrategy": "elbow_angle",
            "rawSeries": angle_series,
            "minRangeOfMotion": ANGLE_MIN_RANGE_OF_MOTION,
            "minStrokeAmplitude": ANGLE_MIN_STROKE_AMPLITUDE,
            "strokeAmplitudeScale": ANGLE_STROKE_AMPLITUDE_SCALE,
        },
    ]


def _smooth_motion_series(series, alpha=0.35):
    if not series:
        return []

    smoothed = []
    smooth_value = series[0]["value"]
    for point in series:
        smooth_value = alpha * point["value"] + (1 - alpha) * smooth_value
        smoothed.append({
            "time": point["time"],
            "value": smooth_value,
            "source": point["source"],
        })

    return smoothed


def _despike_motion_series(
    series,
    max_delta_per_sec=MOTION_SPIKE_MAX_DELTA_PER_SEC,
    base_delta=MOTION_SPIKE_BASE_DELTA,
):
    if len(series) < 3:
        return series

    filtered = [series[0]]
    for point in series[1:]:
        previous = filtered[-1]
        delta_t = point["time"] - previous["time"]
        if delta_t <= 0:
            continue
        allowed_delta = max(base_delta, max_delta_per_sec * delta_t)
        if abs(point["value"] - previous["value"]) > allowed_delta:
            continue
        filtered.append(point)

    return filtered if len(filtered) >= 2 else series


def _find_turning_points(series, epsilon=MOTION_TURN_EPSILON):
    if len(series) < 3:
        return []

    candidates = []
    for index in range(1, len(series) - 1):
        prev_delta = series[index]["value"] - series[index - 1]["value"]
        next_delta = series[index + 1]["value"] - series[index]["value"]

        if prev_delta >= epsilon and next_delta <= -epsilon:
            point_type = "peak"
        elif prev_delta <= -epsilon and next_delta >= epsilon:
            point_type = "trough"
        else:
            continue

        candidates.append({
            "type": point_type,
            "time": series[index]["time"],
            "value": series[index]["value"],
        })

    if not candidates:
        return []

    collapsed = [candidates[0]]
    for point in candidates[1:]:
        last_point = collapsed[-1]
        if point["type"] == last_point["type"]:
            replace_peak = point["type"] == "peak" and point["value"] > last_point["value"]
            replace_trough = point["type"] == "trough" and point["value"] < last_point["value"]
            if replace_peak or replace_trough:
                collapsed[-1] = point
            continue
        collapsed.append(point)

    return collapsed


def _count_strokes(turning_points, min_amplitude, min_cycle_sec, max_cycle_sec):
    if len(turning_points) < 3:
        return 0

    stroke_count = 0
    index = 0
    while index + 2 < len(turning_points):
        first = turning_points[index]
        middle = turning_points[index + 1]
        third = turning_points[index + 2]

        if first["type"] == third["type"] and first["type"] != middle["type"]:
            amp_1 = abs(middle["value"] - first["value"])
            amp_2 = abs(third["value"] - middle["value"])
            cycle_time = third["time"] - first["time"]

            if (
                amp_1 >= min_amplitude
                and amp_2 >= min_amplitude
                and min_cycle_sec <= cycle_time <= max_cycle_sec
            ):
                stroke_count += 1
                index += 2
                continue

        index += 1

    return stroke_count


def _evaluate_movement_gate(side_coordinates, dominant_side, clip_duration_sec):
    candidates = _extract_motion_series_candidates(side_coordinates, dominant_side)

    def _evaluate_candidate(candidate):
        raw_motion_series = candidate.get("rawSeries") or []
        motion_series = _despike_motion_series(raw_motion_series)
        signal_drop_count = max(0, len(raw_motion_series) - len(motion_series))
        if len(motion_series) < 6:
            return {
                "signalStrategy": candidate.get("signalStrategy", "n/a"),
                "movementQualified": False,
                "movementReason": "Not enough movement points detected for stroke analysis.",
                "strokeCount": 0,
                "rangeOfMotion": 0.0,
                "cadenceSpm": 0.0,
                "signalPointCount": len(motion_series),
                "rawSignalPointCount": len(raw_motion_series),
                "signalDropCount": signal_drop_count,
                "signalSource": "n/a",
                "analysisWindowSec": round(float(clip_duration_sec), 2),
            }

        smoothed_series = _smooth_motion_series(motion_series)
        values = [point["value"] for point in smoothed_series]
        range_of_motion = max(values) - min(values)
        amplitude_threshold = max(
            candidate.get("minStrokeAmplitude", MIN_STROKE_AMPLITUDE),
            range_of_motion * candidate.get("strokeAmplitudeScale", STROKE_AMPLITUDE_SCALE),
        )
        turning_points = _find_turning_points(smoothed_series)
        stroke_count = _count_strokes(
            turning_points,
            min_amplitude=amplitude_threshold,
            min_cycle_sec=MIN_STROKE_CYCLE_SEC,
            max_cycle_sec=MAX_STROKE_CYCLE_SEC,
        )

        active_duration_sec = smoothed_series[-1]["time"] - smoothed_series[0]["time"]
        if active_duration_sec <= 0:
            active_duration_sec = clip_duration_sec

        cadence_spm = 0.0
        if active_duration_sec > 0:
            cadence_spm = stroke_count / (active_duration_sec / 60.0)

        min_range = candidate.get("minRangeOfMotion", MIN_RANGE_OF_MOTION)
        if range_of_motion < min_range:
            qualified = False
            reason = (
                f"Not enough rowing motion. Range {range_of_motion:.3f} "
                f"is below required {min_range:.3f}."
            )
        elif stroke_count < MIN_STROKES_REQUIRED:
            qualified = False
            reason = f"Need at least {MIN_STROKES_REQUIRED} strokes to save a clip."
        else:
            qualified = True
            reason = "Movement gate passed."

        return {
            "signalStrategy": candidate.get("signalStrategy", "n/a"),
            "movementQualified": qualified,
            "movementReason": reason,
            "strokeCount": int(stroke_count),
            "rangeOfMotion": round(range_of_motion, 6),
            "cadenceSpm": round(cadence_spm, 2),
            "signalPointCount": len(smoothed_series),
            "rawSignalPointCount": len(raw_motion_series),
            "signalDropCount": signal_drop_count,
            "signalSource": smoothed_series[0]["source"] if smoothed_series else "n/a",
            "analysisWindowSec": round(active_duration_sec, 2),
        }

    evaluated = [_evaluate_candidate(candidate) for candidate in candidates]
    if not evaluated:
        return {
            "signalStrategy": "n/a",
            "movementQualified": False,
            "movementReason": "Not enough movement points detected for stroke analysis.",
            "strokeCount": 0,
            "rangeOfMotion": 0.0,
            "cadenceSpm": 0.0,
            "signalPointCount": 0,
            "rawSignalPointCount": 0,
            "signalDropCount": 0,
            "signalSource": "n/a",
            "analysisWindowSec": round(float(clip_duration_sec), 2),
        }

    best = evaluated[0]
    for candidate in evaluated[1:]:
        best_qualified = 1 if best["movementQualified"] else 0
        candidate_qualified = 1 if candidate["movementQualified"] else 0
        if candidate_qualified > best_qualified:
            best = candidate
            continue
        if candidate["strokeCount"] > best["strokeCount"]:
            best = candidate
            continue
        if (
            candidate["strokeCount"] == best["strokeCount"]
            and candidate["rangeOfMotion"] > best["rangeOfMotion"]
        ):
            best = candidate
            continue
        if (
            candidate["strokeCount"] == best["strokeCount"]
            and candidate["rangeOfMotion"] == best["rangeOfMotion"]
            and candidate["signalPointCount"] > best["signalPointCount"]
        ):
            best = candidate

    return best


def _analyze_landmark_frames(frames, clip_duration_sec):
    coordinates = _build_coordinate_series(frames, clip_duration_sec)
    coordinates = _smooth_coordinates(coordinates)
    dominant_side = _detect_dominant_side(coordinates)
    side_landmarks = set(SIDE_PROFILE_LANDMARKS[dominant_side]) | {"nose"}
    side_coordinates = [item for item in coordinates if item["name"] in side_landmarks]
    if len(side_coordinates) < 2:
        raise ValueError("not enough side-profile landmarks found for analysis")

    side_anchor_candidates = (
        f"{dominant_side}_wrist",
        f"{dominant_side}_elbow",
        f"{dominant_side}_shoulder",
        "nose",
    )
    anchor_name, anchor_coords = _select_anchor_landmark(
        side_coordinates,
        candidates=side_anchor_candidates,
    )
    movement_metrics = _evaluate_movement_gate(
        side_coordinates,
        dominant_side,
        clip_duration_sec,
    )
    if not movement_metrics["movementQualified"]:
        raise MovementGateError(
            movement_metrics["movementReason"],
            payload={
                "dominantSide": dominant_side,
                "frameCount": len(frames),
                "coordinateCount": len(side_coordinates),
                **movement_metrics,
            },
        )

    assembler = PracticeStrokeAssembler()
    progression_interval = 0.1

    anchor_progression = assembler.assemble_progression_steps(anchor_coords, progression_interval)

    ideal_model = []
    unique_names = sorted({item["name"] for item in side_coordinates})
    for landmark_name in unique_names:
        landmark_coords = [item for item in side_coordinates if item["name"] == landmark_name]
        if len(landmark_coords) < 3:
            continue
        landmark_coords = sorted(landmark_coords, key=lambda item: item["time"])
        steps = assembler.assemble_progression_steps(
            landmark_coords,
            progression_interval,
        )
        ideal_model.extend(steps)

    if not ideal_model:
        raise ValueError("unable to build an ideal alignment model from clip data")

    latest_time = max(item["time"] for item in side_coordinates)
    latest_coords = [item for item in side_coordinates if item["time"] == latest_time]
    current_progression = assembler.match_progression_interval(anchor_progression, latest_coords)
    ideal_coordinate_set = assembler.get_ideal_coordinate_set(current_progression, ideal_model)

    latest_by_name = {item["name"]: item for item in latest_coords}
    weighted_total = 0.0
    weight_sum = 0.0
    distances = []
    for ideal_coord in ideal_coordinate_set:
        current_coord = latest_by_name.get(ideal_coord["name"])
        if not current_coord:
            continue
        dx = current_coord["x"] - ideal_coord["x"]
        dy = current_coord["y"] - ideal_coord["y"]
        raw_distance = (dx * dx + dy * dy) ** 0.5
        clamped_distance = min(raw_distance, 0.18)
        weight = _landmark_weight(ideal_coord["name"])
        weighted_total += clamped_distance * weight
        weight_sum += weight
        distances.append(clamped_distance)

    mean_distance = (weighted_total / weight_sum) if weight_sum else None
    score = _alignment_score(mean_distance)

    return {
        "anchorLandmark": anchor_name,
        "dominantSide": dominant_side,
        "landmarksUsed": sorted(side_landmarks),
        "frameCount": len(frames),
        "coordinateCount": len(side_coordinates),
        **movement_metrics,
        "progressionStep": current_progression.get("progression_step"),
        "meanDistance": round(mean_distance, 6) if mean_distance is not None else None,
        "score": score,
        "summary": _summarize_alignment(score),
        "matchedPoints": len(distances),
    }


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid %s=%r; using default %d", name, raw, default)
        return default


MAX_PAGE_SIZE = max(1, _env_int("ROWLYTICS_MAX_PAGE_SIZE", 50))
TEAM_MEMBERS_PAGE_SIZE = max(
    1,
    min(_env_int("ROWLYTICS_TEAM_MEMBERS_PAGE_SIZE", 20), MAX_PAGE_SIZE),
)
RECORDINGS_PAGE_SIZE = max(
    1,
    min(_env_int("ROWLYTICS_RECORDINGS_PAGE_SIZE", 8), MAX_PAGE_SIZE),
)
WORKOUTS_PAGE_SIZE = max(
    1,
    min(_env_int("ROWLYTICS_WORKOUTS_PAGE_SIZE", 8), MAX_PAGE_SIZE),
)


def _parse_limit(raw_limit: str | None, default: int) -> int:
    if raw_limit is None:
        return default
    try:
        parsed = int(raw_limit)
    except ValueError as err:
        raise ValueError("limit must be an integer") from err
    if parsed < 1:
        raise ValueError("limit must be >= 1")
    return min(parsed, MAX_PAGE_SIZE)


def _encode_cursor(last_evaluated_key: dict | None) -> str | None:
    if not last_evaluated_key:
        return None
    payload = json.dumps(last_evaluated_key, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii")


def _decode_cursor(cursor: str | None) -> dict | None:
    if not cursor:
        return None
    try:
        padding = "=" * (-len(cursor) % 4)
        decoded = base64.urlsafe_b64decode((cursor + padding).encode("ascii"))
        payload = json.loads(decoded.decode("utf-8"))
    except Exception as err:
        raise ValueError("cursor is invalid") from err
    if not isinstance(payload, dict):
        raise ValueError("cursor is invalid")
    return payload


@api_bp.route("/health", methods=["GET"])
def health_check():
    """Simple health check endpoint - no auth required to test API connectivity."""
    logger.info("GET /api/health: health check")
    return jsonify({"status": "ok", "service": "rowlytics-api"}), 200


@api_bp.route("/teams/<team_id>/members", methods=["GET"])
def list_team_members(team_id):
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    try:
        limit = _parse_limit(request.args.get("limit"), TEAM_MEMBERS_PAGE_SIZE)
        cursor = _decode_cursor(request.args.get("cursor"))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    try:
        users_table, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        members, next_key = fetch_team_members_page(
            users_table,
            team_members_table,
            team_id,
            ALLOWED_TEAM_ROLES,
            limit=limit,
            exclusive_start_key=cursor,
        )
    except Exception as err:
        return jsonify({"error": "Unable to query team members", "detail": str(err)}), 500

    return jsonify({"teamId": team_id, "members": members, "nextCursor": _encode_cursor(next_key)})


@api_bp.route("/teams/<team_id>/members", methods=["POST"])
def add_team_member(team_id):
    if not team_id:
        return jsonify({"error": "team_id is required"}), 400

    data = request.get_json(silent=True) or {}
    user_id = (data.get("userId") or "").strip()
    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    member_role = (data.get("memberRole") or "rower").strip()
    member_role = member_role.lower()
    if member_role not in ALLOWED_TEAM_ROLES:
        return jsonify({"error": "memberRole must be coach or rower"}), 400

    joined_at = data.get("joinedAt") or now_iso()

    try:
        users_table, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        user_response = users_table.get_item(Key={"userId": user_id})
    except Exception as err:
        return jsonify({"error": "Unable to verify user", "detail": str(err)}), 500

    if not user_response.get("Item"):
        return jsonify({"error": "User does not exist"}), 404

    try:
        existing_membership = get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check user team", "detail": str(err)}), 500

    if existing_membership:
        existing_team_id = existing_membership.get("teamId")
        if existing_team_id == team_id:
            return jsonify({"error": "User already on this team", "teamId": existing_team_id}), 409
        return jsonify({
            "error": "User is already on a team. User must leave current team first.",
            "teamId": existing_team_id,
        }), 409

    item = {
        "teamId": team_id,
        "userId": user_id,
        "memberRole": member_role,
        "joinedAt": joined_at,
    }

    try:
        team_members_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(teamId) AND attribute_not_exists(userId)",
        )
    except Exception as err:
        error_code = None
        if ClientError and isinstance(err, ClientError):
            error_code = err.response.get("Error", {}).get("Code")
        if error_code == "ConditionalCheckFailedException":
            return jsonify({"error": "User already on team"}), 409
        return jsonify({"error": "Unable to add team member", "detail": str(err)}), 500

    return jsonify({"status": "ok", "teamId": team_id, "userId": user_id}), 201


@api_bp.route("/team/current", methods=["GET"])
def current_team():
    user_id = session.get("user_id")
    logger.info(f"GET /team/current: user={user_id}")

    if not user_id:
        logger.warning("GET /team/current: authentication required")
        return jsonify({"error": "authentication required"}), 401

    try:
        limit = _parse_limit(request.args.get("limit"), TEAM_MEMBERS_PAGE_SIZE)
        cursor = _decode_cursor(request.args.get("cursor"))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    try:
        users_table, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        logger.error(f"GET /team/current: DynamoDB tables not available: {err}")
        return jsonify({"error": str(err)}), 500

    try:
        logger.debug(f"GET /team/current: fetching membership for user {user_id}")
        membership = get_team_membership(team_members_table, user_id)
    except Exception as err:
        logger.error(f"GET /team/current: failed to load membership: {err}", exc_info=True)
        return jsonify({"error": "Unable to load team", "detail": str(err)}), 500

    if not membership:
        logger.info(f"GET /team/current: user {user_id} not on a team")
        return jsonify({"teamId": None, "members": [], "nextCursor": None})

    team_id = membership.get("teamId")
    logger.debug(f"GET /team/current: user {user_id} is on team {team_id}")

    try:
        members, next_key = fetch_team_members_page(
            users_table,
            team_members_table,
            team_id,
            ALLOWED_TEAM_ROLES,
            limit=limit,
            exclusive_start_key=cursor,
        )
        logger.info(
            "GET /team/current: successfully loaded team %s page with %d members",
            team_id,
            len(members),
        )
    except Exception as err:
        logger.error(f"GET /team/current: failed to load team members: {err}", exc_info=True)
        return jsonify({"error": "Unable to load team members", "detail": str(err)}), 500

    return jsonify({
        "teamId": team_id,
        "members": members,
        "memberRole": membership.get("memberRole"),
        "nextCursor": _encode_cursor(next_key),
    })


@api_bp.route("/team/join", methods=["POST"])
def join_team():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    team_id = (data.get("teamId") or "").strip()
    if not team_id:
        return jsonify({"error": "teamId is required"}), 400

    member_role = (data.get("memberRole") or "rower").strip().lower()
    if member_role not in ALLOWED_TEAM_ROLES:
        return jsonify({"error": "memberRole must be coach or rower"}), 400

    joined_at = data.get("joinedAt") or now_iso()

    try:
        users_table, team_members_table = get_ddb_tables()
        teams_table = get_teams_table()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    team_item = get_team(teams_table, team_id)
    if not team_item:
        return jsonify({"error": "Team not found"}), 404

    try:
        existing = get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check current team", "detail": str(err)}), 500

    if existing and existing.get("teamId") != team_id:
        return jsonify({
            "error": "Already on a team. Leave your current team first.",
            "teamId": existing.get("teamId"),
        }), 409

    if existing and existing.get("teamId") == team_id:
        try:
            members = fetch_team_members(
                users_table,
                team_members_table,
                team_id,
                ALLOWED_TEAM_ROLES,
            )
        except Exception as err:
            return jsonify({"error": "Unable to load team members", "detail": str(err)}), 500
        return jsonify({"status": "ok", "teamId": team_id, "members": members})

    if not existing:
        item = {
            "teamId": team_id,
            "userId": user_id,
            "memberRole": member_role,
            "joinedAt": joined_at,
        }
        try:
            team_members_table.put_item(
                Item=item,
                ConditionExpression="attribute_not_exists(teamId) AND attribute_not_exists(userId)",
            )
        except Exception as err:
            error_code = None
            if ClientError and isinstance(err, ClientError):
                error_code = err.response.get("Error", {}).get("Code")
            if error_code != "ConditionalCheckFailedException":
                return jsonify({"error": "Unable to join team", "detail": str(err)}), 500

    try:
        members = fetch_team_members(
            users_table,
            team_members_table,
            team_id,
            ALLOWED_TEAM_ROLES,
        )
    except Exception as err:
        return jsonify({"error": "Unable to load team members", "detail": str(err)}), 500

    return jsonify({"status": "ok", "teamId": team_id, "members": members})


@api_bp.route("/team/create", methods=["POST"])
def create_team():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    team_name = (data.get("teamName") or "").strip()
    if not team_name:
        return jsonify({"error": "teamName is required"}), 400

    created_at = data.get("createdAt") or now_iso()

    try:
        users_table, team_members_table = get_ddb_tables()
        teams_table = get_teams_table()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        existing = get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check current team", "detail": str(err)}), 500

    if existing:
        return jsonify({
            "error": "Already on a team. Leave your current team first.",
            "teamId": existing.get("teamId"),
        }), 409

    try:
        if team_name_exists(teams_table, team_name):
            return jsonify({"error": "Team name already exists"}), 409
    except Exception as err:
        return jsonify({"error": "Unable to check team name", "detail": str(err)}), 500

    team_id = uuid4().hex
    team_item = {
        "teamId": team_id,
        "teamName": team_name,
        "coachUserId": user_id,
        "createdAt": created_at,
    }

    try:
        teams_table.put_item(
            Item=team_item,
            ConditionExpression="attribute_not_exists(teamId)",
        )
    except Exception as err:
        return jsonify({"error": "Unable to create team", "detail": str(err)}), 500

    member_item = {
        "teamId": team_id,
        "userId": user_id,
        "memberRole": "coach",
        "joinedAt": created_at,
    }

    try:
        team_members_table.put_item(
            Item=member_item,
            ConditionExpression="attribute_not_exists(teamId) AND attribute_not_exists(userId)",
        )
    except Exception as err:
        return jsonify({"error": "Unable to add team owner", "detail": str(err)}), 500

    try:
        members = fetch_team_members(
            users_table,
            team_members_table,
            team_id,
            ALLOWED_TEAM_ROLES,
        )
    except Exception as err:
        return jsonify({"error": "Unable to load team members", "detail": str(err)}), 500

    return jsonify({
        "status": "ok",
        "teamId": team_id,
        "teamName": team_name,
        "members": members,
    }), 201


@api_bp.route("/team/leave", methods=["DELETE"])
def leave_team():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    try:
        _, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        membership = get_team_membership(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to check current team", "detail": str(err)}), 500

    if not membership:
        return jsonify({"error": "User is not on a team"}), 404

    team_id = membership.get("teamId")
    try:
        team_members_table.delete_item(Key={"teamId": team_id, "userId": user_id})
    except Exception as err:
        return jsonify({"error": "Unable to leave team", "detail": str(err)}), 500

    return jsonify({"status": "ok", "teamId": team_id})


@api_bp.route("/account/name", methods=["POST"])
def update_account_name():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    if not name:
        return jsonify({"error": "name is required"}), 400

    try:
        users_table, _ = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        if display_name_exists(users_table, name, excluding_user_id=user_id):
            return jsonify({"error": "Display name already in use"}), 409
    except Exception as err:
        return jsonify({"error": "Unable to check display name", "detail": str(err)}), 500

    update_expr = "SET #name = :name, nameKey = :nameKey, updatedAt = :updatedAt"
    expr_attr_names = {"#name": "name"}
    expr_attr_values = {
        ":name": name,
        ":nameKey": normalize_display_name(name),
        ":updatedAt": now_iso(),
    }

    user_email = session.get("user_email")
    if user_email:
        update_expr += ", email = if_not_exists(email, :email)"
        expr_attr_values[":email"] = user_email

    try:
        users_table.update_item(
            Key={"userId": user_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )
    except Exception as err:
        return jsonify({"error": "Unable to update name", "detail": str(err)}), 500

    session["user_name"] = name
    session["display_name_required"] = False
    return jsonify({"status": "ok", "name": name})


@api_bp.route("/account/profile", methods=["GET"])
def get_account_profile():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    try:
        profile = fetch_user_profile(user_id)
    except Exception as err:
        return jsonify({"error": "Unable to load account profile", "detail": str(err)}), 500

    current_name = profile.get("name") or session.get("user_name")
    current_email = profile.get("email") or session.get("user_email")

    if current_name:
        session["user_name"] = current_name
    if current_email:
        session["user_email"] = current_email

    return jsonify({
        "userId": user_id,
        "name": current_name,
        "email": current_email,
    })


@api_bp.route("/account/delete", methods=["POST"])
def delete_account():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    try:
        users_table, team_members_table = get_ddb_tables()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    try:
        delete_cognito_user(user_id, session.get("user_email"), session.get("access_token"))
    except Exception as err:
        return jsonify({"error": "Unable to delete Cognito user", "detail": str(err)}), 500

    recordings_table = None
    s3 = None
    try:
        recordings_table = get_recordings_table()
        s3 = get_s3_client()
    except RuntimeError:
        recordings_table = None
        s3 = None

    if recordings_table is not None:
        try:
            recordings = list_recordings(recordings_table, user_id)
        except Exception as err:
            return jsonify({"error": "Unable to load recordings", "detail": str(err)}), 500

        for item in recordings:
            recording_id = item.get("recordingId")
            object_key = item.get("objectKey")
            if s3 and object_key:
                try:
                    s3.delete_object(Bucket=UPLOAD_BUCKET_NAME, Key=object_key)
                except Exception:
                    pass
            if recording_id:
                recordings_table.delete_item(Key={"userId": user_id, "recordingId": recording_id})

    try:
        memberships = list_team_memberships(team_members_table, user_id)
    except Exception as err:
        return jsonify({"error": "Unable to load team memberships", "detail": str(err)}), 500

    for membership in memberships:
        team_id = membership.get("teamId")
        if team_id:
            team_members_table.delete_item(Key={"teamId": team_id, "userId": user_id})

    try:
        users_table.delete_item(Key={"userId": user_id})
    except Exception as err:
        return jsonify({"error": "Unable to delete user", "detail": str(err)}), 500

    session.clear()
    return jsonify({"status": "ok"})


@api_bp.route("/recordings/presign", methods=["POST"])
def presign_recording_upload():
    data = request.get_json(silent=True) or {}
    user_id = (data.get("userId") or "").strip()
    content_type = (data.get("contentType") or "video/webm").strip()

    if not user_id:
        return jsonify({"error": "userId is required"}), 400

    try:
        s3 = get_s3_client()
    except RuntimeError as err:
        return jsonify({"error": str(err)}), 500

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    recording_id = uuid4().hex
    extension = "webm" if "webm" in content_type else "bin"
    object_key = f"recordings/{user_id}/{timestamp}-{recording_id}.{extension}"

    try:
        upload_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": UPLOAD_BUCKET_NAME,
                "Key": object_key,
                "ContentType": content_type,
            },
            ExpiresIn=900,
        )
    except Exception as err:
        return jsonify({"error": "Unable to create upload URL", "detail": str(err)}), 500

    return jsonify({
        "uploadUrl": upload_url,
        "objectKey": object_key,
        "bucket": UPLOAD_BUCKET_NAME,
        "expiresIn": 900,
    })


@api_bp.route("/recordings", methods=["POST"])
def save_recording_metadata():
    data = request.get_json(silent=True) or {}
    user_id = (data.get("userId") or "").strip()
    object_key = (data.get("objectKey") or "").strip()
    content_type = (data.get("contentType") or "video/webm").strip()
    duration_sec = data.get("durationSec")
    created_at = data.get("createdAt") or now_iso()

    if not user_id or not object_key:
        return jsonify({"error": "userId and objectKey are required"}), 400

    try:
        recordings_table = get_recordings_table()
    except RuntimeError as err:
        return jsonify({"status": "skipped", "reason": str(err)}), 200

    recording_id = uuid4().hex
    item = {
        "userId": user_id,
        "recordingId": recording_id,
        "objectKey": object_key,
        "contentType": content_type,
        "durationSec": duration_sec,
        "createdAt": created_at,
    }

    try:
        recordings_table.put_item(Item=item)
    except Exception as err:
        return jsonify({"error": "Unable to save recording metadata", "detail": str(err)}), 500

    return jsonify({"status": "ok", "recordingId": recording_id})


@api_bp.route("/recordings/<user_id>", methods=["GET"])
def list_recordings_for_user(user_id):
    logger.info(f"GET /recordings/{user_id}")

    if not user_id:
        logger.warning("GET /recordings: user_id is required")
        return jsonify({"error": "user_id is required"}), 400

    try:
        limit = _parse_limit(request.args.get("limit"), RECORDINGS_PAGE_SIZE)
        cursor = _decode_cursor(request.args.get("cursor"))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    try:
        recordings_table = get_recordings_table()
    except RuntimeError as err:
        logger.error(f"GET /recordings: recordings table not available: {err}")
        return jsonify({"error": str(err)}), 500

    try:
        logger.debug(f"GET /recordings: querying recordings for user {user_id}")
        items, next_key = list_recordings_page(
            recordings_table,
            user_id,
            limit=limit,
            exclusive_start_key=cursor,
        )
        logger.info("GET /recordings: found %d recordings for user %s", len(items), user_id)
    except Exception as err:
        logger.error(f"GET /recordings: failed to load recordings: {err}", exc_info=True)
        return jsonify({"error": "Unable to load recordings", "detail": str(err)}), 500

    try:
        logger.debug("GET /recordings: creating S3 client for presigned URLs")
        s3 = get_s3_client()
    except RuntimeError as err:
        logger.error(f"GET /recordings: S3 client not available: {err}")
        return jsonify({"error": str(err)}), 500

    for item in items:
        object_key = item.get("objectKey")
        if object_key:
            try:
                logger.debug(f"GET /recordings: generating presigned URL for {object_key}")
                item["playbackUrl"] = s3.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": UPLOAD_BUCKET_NAME, "Key": object_key},
                    ExpiresIn=900,
                )
            except Exception as e:
                logger.error(
                    "GET /recordings: failed to generate presigned URL for %s: %s",
                    object_key,
                    e,
                )
                item["playbackUrl"] = None
        else:
            logger.warning("GET /recordings: recording missing objectKey")
            item["playbackUrl"] = None

    logger.info("GET /recordings: returning %d recordings with playback URLs", len(items))
    return jsonify({
        "userId": user_id,
        "recordings": items,
        "nextCursor": _encode_cursor(next_key),
    })


@api_bp.route("/workouts", methods=["POST"])
def save_workout():
    user_id = session.get("user_id")
    logger.info(f"POST /workouts: user={user_id}")

    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    duration_sec = data.get("durationSec")
    workout_score = data.get("workoutScore")
    summary = (data.get("summary") or "").strip()
    alignment_details = (data.get("alignmentDetails") or "").strip()
    stroke_count = data.get("strokeCount")
    cadence_spm = data.get("cadenceSpm")
    range_of_motion = data.get("rangeOfMotion")
    dominant_side = (data.get("dominantSide") or "").strip()
    started_at = data.get("startedAt")
    completed_at = data.get("completedAt") or now_iso()
    created_at = data.get("createdAt") or completed_at

    try:
        duration_value = float(duration_sec)
    except (TypeError, ValueError):
        duration_value = None

    if duration_value is None or duration_value <= 0:
        return jsonify({"error": "durationSec must be a positive number"}), 400
    if duration_value > MAX_WORKOUT_DURATION_SEC:
        return jsonify({
            "error": f"durationSec must be less than or equal to {MAX_WORKOUT_DURATION_SEC}",
        }), 400

    duration_value = int(round(duration_value))

    try:
        workouts_table = get_workouts_table()
    except RuntimeError as err:
        logger.warning("POST /workouts: workouts table not configured: %s", err)
        return jsonify({"status": "skipped", "reason": str(err)}), 200

    workout_id = uuid4().hex
    item = {
        "userId": user_id,
        "workoutId": workout_id,
        "durationSec": duration_value,
        "createdAt": created_at,
        "completedAt": completed_at,
    }

    if started_at:
        item["startedAt"] = started_at

    if workout_score is not None:
        try:
            score_value = Decimal(str(workout_score))
        except (InvalidOperation, TypeError, ValueError):
            return jsonify({"error": "workoutScore must be numeric"}), 400
        item["workoutScore"] = score_value

    if summary:
        item["summary"] = summary

    if alignment_details:
        item["alignmentDetails"] = alignment_details

    if stroke_count is not None:
        try:
            item["strokeCount"] = int(round(float(stroke_count)))
        except (TypeError, ValueError):
            return jsonify({"error": "strokeCount must be numeric"}), 400

    if cadence_spm is not None:
        try:
            item["cadenceSpm"] = Decimal(str(cadence_spm))
        except (InvalidOperation, TypeError, ValueError):
            return jsonify({"error": "cadenceSpm must be numeric"}), 400

    if range_of_motion is not None:
        try:
            item["rangeOfMotion"] = Decimal(str(range_of_motion))
        except (InvalidOperation, TypeError, ValueError):
            return jsonify({"error": "rangeOfMotion must be numeric"}), 400

    if dominant_side:
        item["dominantSide"] = dominant_side

    try:
        workouts_table.put_item(Item=item)
    except Exception as err:
        logger.error("POST /workouts: failed to save workout: %s", err, exc_info=True)
        return jsonify({"error": "Unable to save workout", "detail": str(err)}), 500

    return jsonify({"status": "ok", "workoutId": workout_id}), 201


@api_bp.route("/workouts", methods=["GET"])
def list_workouts_for_current_user():
    user_id = session.get("user_id")
    logger.info(f"GET /workouts: user={user_id}")

    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    try:
        limit = _parse_limit(request.args.get("limit"), WORKOUTS_PAGE_SIZE)
        cursor = _decode_cursor(request.args.get("cursor"))
    except ValueError as err:
        return jsonify({"error": str(err)}), 400

    try:
        workouts_table = get_workouts_table()
    except RuntimeError as err:
        logger.warning("GET /workouts: workouts table not configured: %s", err)
        return jsonify({"error": str(err)}), 500

    try:
        items, next_key = list_workouts_page(
            workouts_table,
            user_id,
            limit=limit,
            exclusive_start_key=cursor,
        )
    except Exception as err:
        logger.error("GET /workouts: failed to load workouts: %s", err, exc_info=True)
        return jsonify({"error": "Unable to load workouts", "detail": str(err)}), 500

    return jsonify({
        "userId": user_id,
        "workouts": items,
        "nextCursor": _encode_cursor(next_key),
    })


@api_bp.route("/workouts/alignment-preview", methods=["POST"])
def preview_workout_alignment():
    user_id = session.get("user_id")
    if not user_id:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    frames = data.get("frames")
    clip_duration_sec = _coerce_float(data.get("clipDurationSec"))
    clip_count = _coerce_float(data.get("clipCount"))
    if clip_duration_sec is None or clip_duration_sec <= 0:
        clip_duration_sec = 5.0
    if clip_count is not None and clip_count > 0:
        clip_count = int(round(clip_count))
    else:
        clip_count = None

    try:
        result = _analyze_landmark_frames(frames, clip_duration_sec)
    except MovementGateError as err:
        payload = err.payload.copy()
        if clip_count is not None:
            payload["clipCount"] = clip_count
        return jsonify({
            "status": "rejected",
            "error": str(err),
            **payload,
        }), 422
    except ValueError as err:
        return jsonify({"error": str(err)}), 400
    except Exception as err:  # pragma: no cover - defensive safety
        logger.error("POST /workouts/alignment-preview failed: %s", err, exc_info=True)
        return jsonify({"error": "Unable to analyze workout frames"}), 500

    return jsonify({
        "status": "ok",
        "userId": user_id,
        "clipCount": clip_count,
        **result,
    })
