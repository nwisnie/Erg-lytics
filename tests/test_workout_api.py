"""Tests for workout API validation."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient

from rowlytics_app import create_app
from rowlytics_app.api_routes import (
    _analyze_landmark_frames,
    _score_arms_straightness,
    _score_back_straightness,
    _summarize_team_workouts,
)


@pytest.fixture()
def app() -> Flask:
    flask_app = create_app()
    flask_app.config.update(TESTING=True, AUTH_REQUIRED=False)
    return flask_app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def _build_consistency_test_frames(
    cycle_offsets: list[float],
    phase_sequences: list[list[float]] | None = None,
) -> list[list[dict | None]]:
    if phase_sequences is None:
        phase_sequences = [[0.2, 0.5, 0.8] for _ in cycle_offsets]

    frames = []

    def point(x: float, y: float) -> dict[str, float]:
        return {"x": x, "y": y, "visibility": 0.99}

    for offset, phase_positions in zip(cycle_offsets, phase_sequences):
        for wrist_x in phase_positions:
            frame: list[dict | None] = [None] * 33
            frame[0] = point(0.18, 0.20 + (offset * 0.4))   # nose
            frame[7] = point(0.20, 0.19 + (offset * 0.4))   # left_ear
            frame[11] = point(0.30 + (offset * 0.1), 0.34 + offset)  # left_shoulder
            frame[13] = point(wrist_x - 0.12 + (offset * 0.08), 0.37 + (offset * 0.9))  # left_elbow
            frame[15] = point(wrist_x, 0.40 + offset)  # left_wrist
            frame[23] = point(0.28 + (offset * 0.08), 0.58 + (offset * 0.7))  # left_hip
            frame[25] = point(0.30 + (offset * 0.06), 0.77 + (offset * 0.5))  # left_knee
            frame[27] = point(0.32 + (offset * 0.05), 0.93 + (offset * 0.3))  # left_ankle
            frames.append(frame)

    return frames


def _build_export_like_gate_frames(
    cycle_offsets: list[float],
    *,
    bent_arms: bool,
    hunched_back: bool,
    dominant_side: str = "left",
) -> tuple[list[list[dict | None]], float, str]:
    phase_sequence = [0.18, 0.34, 0.50, 0.66, 0.82]
    landmark_indices = {
        "nose": 0,
        "left_ear": 7,
        "right_ear": 8,
        "left_shoulder": 11,
        "right_shoulder": 12,
        "left_elbow": 13,
        "right_elbow": 14,
        "left_wrist": 15,
        "right_wrist": 16,
        "left_hip": 23,
        "right_hip": 24,
        "left_knee": 25,
        "right_knee": 26,
        "left_ankle": 27,
        "right_ankle": 28,
    }

    def point(x: float, y: float) -> dict[str, float]:
        return {"x": round(x, 6), "y": round(y, 6), "visibility": 0.99}

    frames: list[list[dict | None]] = []
    side_prefix = "left" if dominant_side == "left" else "right"
    for offset in cycle_offsets:
        for wrist_x in phase_sequence:
            frame: list[dict | None] = [None] * 33
            base_x = offset * 0.08
            base_y = offset * 0.5
            hip_x = 0.28 + base_x
            hip_y = 0.60 + base_y
            shoulder_x = 0.40 + base_x
            shoulder_y = 0.38 + base_y
            wrist_y = 0.41 + (offset * 0.15)

            if bent_arms:
                elbow_x = wrist_x - 0.04 + (offset * 0.04)
                elbow_y = 0.29 + base_y
            else:
                elbow_x = ((shoulder_x + wrist_x) / 2.0) + (offset * 0.01)
                elbow_y = (shoulder_y + wrist_y) / 2.0

            if hunched_back:
                ear_x = shoulder_x + 0.04
                ear_y = shoulder_y + 0.10
            else:
                ear_x = shoulder_x + 0.11
                ear_y = shoulder_y - 0.11

            frame[landmark_indices["nose"]] = point(ear_x - 0.01, ear_y + 0.01)
            frame[landmark_indices[f"{side_prefix}_ear"]] = point(ear_x, ear_y)
            frame[landmark_indices[f"{side_prefix}_shoulder"]] = point(shoulder_x, shoulder_y)
            frame[landmark_indices[f"{side_prefix}_elbow"]] = point(elbow_x, elbow_y)
            frame[landmark_indices[f"{side_prefix}_wrist"]] = point(wrist_x, wrist_y)
            frame[landmark_indices[f"{side_prefix}_hip"]] = point(hip_x, hip_y)
            frame[landmark_indices[f"{side_prefix}_knee"]] = point(hip_x + 0.03, hip_y + 0.18)
            frame[landmark_indices[f"{side_prefix}_ankle"]] = point(hip_x + 0.05, hip_y + 0.34)
            frames.append(frame)

    return frames, 5.0, dominant_side


def test_save_workout_rejects_duration_over_one_hour(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_workouts_table = MagicMock()
    monkeypatch.setattr("rowlytics_app.api_routes.get_workouts_table", get_workouts_table)

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.post("/api/workouts", json={"durationSec": 3601})

    assert response.status_code == 400
    assert response.get_json() == {
        "error": "durationSec must be less than or equal to 3600",
    }
    get_workouts_table.assert_not_called()


def test_save_workout_accepts_one_hour_duration(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workouts_table = MagicMock()
    monkeypatch.setattr("rowlytics_app.api_routes.get_workouts_table", lambda: workouts_table)

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.post("/api/workouts", json={"durationSec": 3600})

    assert response.status_code == 201
    payload = response.get_json()
    assert payload["status"] == "ok"
    workouts_table.put_item.assert_called_once()
    item = workouts_table.put_item.call_args.kwargs["Item"]
    assert item["userId"] == "user-123"
    assert item["durationSec"] == 3600


def test_save_workout_persists_arms_straight_score(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workouts_table = MagicMock()
    monkeypatch.setattr("rowlytics_app.api_routes.get_workouts_table", lambda: workouts_table)

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.post(
        "/api/workouts",
        json={"durationSec": 120, "armsStraightScore": 91.25},
    )

    assert response.status_code == 201
    item = workouts_table.put_item.call_args.kwargs["Item"]
    assert item["armsStraightScore"] == Decimal("91.25")


def test_save_workout_persists_back_straight_score(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workouts_table = MagicMock()
    monkeypatch.setattr("rowlytics_app.api_routes.get_workouts_table", lambda: workouts_table)

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.post(
        "/api/workouts",
        json={"durationSec": 120, "backStraightScore": 88.5},
    )

    assert response.status_code == 201
    item = workouts_table.put_item.call_args.kwargs["Item"]
    assert item["backStraightScore"] == Decimal("88.5")


def test_alignment_preview_allows_partial_motion_when_requested(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_analyze_landmark_frames(
        frames: list[object],
        clip_duration_sec: float,
        *,
        require_movement_gate: bool = True,
    ) -> dict[str, object]:
        captured["frames"] = frames
        captured["clip_duration_sec"] = clip_duration_sec
        captured["require_movement_gate"] = require_movement_gate
        return {
            "movementQualified": False,
            "movementReason": "Need at least 3 strokes to save a clip.",
            "strokeCount": 2,
            "score": 84.0,
            "summary": "Alignment looks consistent.",
        }

    monkeypatch.setattr(
        "rowlytics_app.api_routes._analyze_landmark_frames",
        fake_analyze_landmark_frames,
    )

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.post(
        "/api/workouts/alignment-preview",
        json={
            "frames": [[{"x": 0.1, "y": 0.2, "visibility": 0.9}]],
            "clipDurationSec": 5,
            "clipCount": 1,
            "allowPartialMotion": True,
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["movementQualified"] is False
    assert payload["strokeCount"] == 2
    assert payload["score"] == 84.0
    assert captured["clip_duration_sec"] == 5.0
    assert captured["require_movement_gate"] is False


def test_analyze_landmark_frames_scores_repeatable_clip_higher_than_drifty_clip() -> None:
    stable_frames = _build_consistency_test_frames([0.0, 0.005, -0.004])
    drifty_frames = _build_consistency_test_frames([0.0, 0.09, -0.08])

    stable = _analyze_landmark_frames(
        stable_frames,
        5.0,
        require_movement_gate=False,
    )
    drifty = _analyze_landmark_frames(
        drifty_frames,
        5.0,
        require_movement_gate=False,
    )

    assert stable["score"] is not None
    assert drifty["score"] is not None
    assert stable["matchedPoints"] > 0
    assert drifty["matchedPoints"] > 0
    assert stable["score"] > drifty["score"]
    assert stable["score"] >= 90.0
    assert drifty["score"] <= 75.0


def test_analyze_landmark_frames_penalizes_inconsistent_timing() -> None:
    stable_frames = _build_consistency_test_frames(
        [0.0, 0.0, 0.0],
        phase_sequences=[
            [0.2, 0.35, 0.5, 0.65, 0.8],
            [0.2, 0.35, 0.5, 0.65, 0.8],
            [0.2, 0.35, 0.5, 0.65, 0.8],
        ],
    )
    irregular_timing_frames = _build_consistency_test_frames(
        [0.0, 0.0, 0.0],
        phase_sequences=[
            [0.2, 0.5, 0.8],
            [0.2, 0.28, 0.36, 0.44, 0.52, 0.6, 0.68, 0.74, 0.8],
            [0.2, 0.8],
        ],
    )

    stable = _analyze_landmark_frames(
        stable_frames,
        5.0,
        require_movement_gate=False,
    )
    irregular = _analyze_landmark_frames(
        irregular_timing_frames,
        5.0,
        require_movement_gate=False,
    )

    assert stable["score"] is not None
    assert irregular["score"] is not None
    assert irregular["timingPenalty"] > stable["timingPenalty"]
    assert stable["score"] > irregular["score"]


def test_exported_example_good_clip_scores_form_higher_than_bad_clip() -> None:
    good_frames, good_duration, good_side = _build_export_like_gate_frames(
        [0.0, 0.02, -0.01],
        bent_arms=False,
        hunched_back=False,
    )
    bad_frames, bad_duration, bad_side = _build_export_like_gate_frames(
        [0.0, 0.09, -0.08],
        bent_arms=True,
        hunched_back=True,
    )

    good = _analyze_landmark_frames(
        good_frames,
        good_duration,
        require_movement_gate=False,
        dominant_side_hint=good_side,
    )
    bad = _analyze_landmark_frames(
        bad_frames,
        bad_duration,
        require_movement_gate=False,
        dominant_side_hint=bad_side,
    )

    assert good["armsStraightScore"] is not None
    assert bad["armsStraightScore"] is not None
    assert good["backStraightScore"] is not None
    assert bad["backStraightScore"] is not None
    assert good["armsStraightScore"] > bad["armsStraightScore"]
    assert good["backStraightScore"] > bad["backStraightScore"]
    assert good["score"] > bad["score"]


def test_analyze_landmark_frames_respects_dominant_side_hint_for_exported_clip() -> None:
    bad_frames, bad_duration, bad_side = _build_export_like_gate_frames(
        [0.0, 0.09, -0.08],
        bent_arms=True,
        hunched_back=True,
    )

    hinted = _analyze_landmark_frames(
        bad_frames,
        bad_duration,
        require_movement_gate=False,
        dominant_side_hint=bad_side,
    )

    assert bad_side == "left"
    assert hinted["dominantSide"] == "left"


def test_list_workouts_passes_completed_at_range(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workouts_table = MagicMock()
    captured = {}

    def fake_list_workouts_page(_workouts_table, user_id, **kwargs):
        captured["user_id"] = user_id
        captured.update(kwargs)
        return (
            [
                {
                    "workoutId": "workout-1",
                    "completedAt": "2026-04-05T10:15:30+00:00",
                }
            ],
            None,
        )

    monkeypatch.setattr("rowlytics_app.api_routes.get_workouts_table", lambda: workouts_table)
    monkeypatch.setattr(
        "rowlytics_app.api_routes.list_workouts_page",
        fake_list_workouts_page,
    )

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.get(
        "/api/workouts"
        "?completedFrom=2026-04-05T04:00:00.000Z"
        "&completedTo=2026-04-06T03:59:59.999Z"
    )

    assert response.status_code == 200
    assert captured["user_id"] == "user-123"
    assert captured["completed_from"] == "2026-04-05T04:00:00.000Z"
    assert captured["completed_to"] == "2026-04-06T03:59:59.999Z"
    assert response.get_json()["workouts"][0]["workoutId"] == "workout-1"


def test_list_workouts_rejects_partial_completed_at_range(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_workouts_table = MagicMock()
    monkeypatch.setattr("rowlytics_app.api_routes.get_workouts_table", get_workouts_table)

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.get("/api/workouts?completedFrom=2026-04-05T04:00:00.000Z")

    assert response.status_code == 400
    assert response.get_json()["error"] == "completedFrom and completedTo must be provided together"
    get_workouts_table.assert_not_called()


def test_summarize_team_workouts_averages_available_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workouts_by_user = {
        "u1": [
            {
                "workoutScore": Decimal("80"),
                "armsStraightScore": Decimal("90"),
            },
            {
                "alignmentDetails": (
                    "consistency score: 70\n"
                    "arms straight score: n/a\n"
                    "back straight score: 60"
                ),
            },
        ],
        "u2": [
            {"backStraightScore": 100},
            {"summary": "No scores for this workout"},
        ],
    }

    def fake_list_workouts(_table, user_id: str):
        return workouts_by_user.get(user_id, [])

    monkeypatch.setattr("rowlytics_app.api_routes.list_workouts", fake_list_workouts)

    stats = _summarize_team_workouts(
        MagicMock(),
        [{"userId": "u2"}, {"userId": "u1"}, {"userId": "u1"}],
    )

    assert stats["memberCount"] == 2
    assert stats["workoutCount"] == 4
    assert stats["metrics"]["consistencyScore"] == {"average": 75.0, "count": 2}
    assert stats["metrics"]["armsStraightScore"] == {"average": 90.0, "count": 1}
    assert stats["metrics"]["backStraightScore"] == {"average": 80.0, "count": 2}


def test_score_arms_straightness_ignores_finish_phase_frames() -> None:
    anchor_progression = [
        {"name": "left_wrist", "time": 0.0, "progression_step": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "progression_step": 0.5, "x": 0.5, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "progression_step": 0.8, "x": 0.8, "y": 0.0},
        {"name": "left_wrist", "time": 3.0, "progression_step": 1.0, "x": 1.0, "y": 0.0},
    ]
    side_coordinates = [
        {"name": "left_shoulder", "time": 0.0, "x": -0.2, "y": 0.0},
        {"name": "left_elbow", "time": 0.0, "x": -0.1, "y": 0.0},
        {"name": "left_wrist", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_shoulder", "time": 1.0, "x": 0.3, "y": 0.0},
        {"name": "left_elbow", "time": 1.0, "x": 0.4, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "x": 0.5, "y": 0.0},
        {"name": "left_shoulder", "time": 2.0, "x": 0.6, "y": 0.0},
        {"name": "left_elbow", "time": 2.0, "x": 0.7, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "x": 0.8, "y": 0.0},
        {"name": "left_shoulder", "time": 3.0, "x": 0.8, "y": 0.0},
        {"name": "left_elbow", "time": 3.0, "x": 0.9, "y": 0.0},
        {"name": "left_wrist", "time": 3.0, "x": 1.0, "y": 0.1},
    ]

    score = _score_arms_straightness(
        side_coordinates,
        "left",
        anchor_progression,
    )

    assert score == 100.0


def test_score_arms_straightness_keeps_small_bend_high() -> None:
    anchor_progression = [
        {"name": "left_wrist", "time": 0.0, "progression_step": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "progression_step": 0.4, "x": 0.4, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "progression_step": 0.7, "x": 0.7, "y": 0.0},
    ]
    side_coordinates = [
        {"name": "left_shoulder", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_elbow", "time": 0.0, "x": 1.0, "y": 0.0},
        {"name": "left_wrist", "time": 0.0, "x": 1.95, "y": 0.2},
        {"name": "left_shoulder", "time": 1.0, "x": 0.0, "y": 0.0},
        {"name": "left_elbow", "time": 1.0, "x": 1.0, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "x": 1.95, "y": 0.2},
        {"name": "left_shoulder", "time": 2.0, "x": 0.0, "y": 0.0},
        {"name": "left_elbow", "time": 2.0, "x": 1.0, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "x": 1.95, "y": 0.2},
    ]

    score = _score_arms_straightness(
        side_coordinates,
        "left",
        anchor_progression,
    )

    assert score is not None
    assert score >= 85.0


def test_score_arms_straightness_penalizes_consistently_bent_early_drive() -> None:
    anchor_progression = [
        {"name": "left_wrist", "time": 0.0, "progression_step": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "progression_step": 0.2, "x": 0.2, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "progression_step": 0.4, "x": 0.4, "y": 0.0},
    ]
    side_coordinates = [
        {"name": "left_shoulder", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_elbow", "time": 0.0, "x": 0.65, "y": 0.45},
        {"name": "left_wrist", "time": 0.0, "x": 0.0, "y": 1.2},
        {"name": "left_shoulder", "time": 1.0, "x": 0.2, "y": 0.0},
        {"name": "left_elbow", "time": 1.0, "x": 0.85, "y": 0.45},
        {"name": "left_wrist", "time": 1.0, "x": 0.2, "y": 1.2},
        {"name": "left_shoulder", "time": 2.0, "x": 0.4, "y": 0.0},
        {"name": "left_elbow", "time": 2.0, "x": 1.05, "y": 0.45},
        {"name": "left_wrist", "time": 2.0, "x": 0.4, "y": 1.2},
    ]

    score = _score_arms_straightness(
        side_coordinates,
        "left",
        anchor_progression,
    )

    assert score is not None
    assert score <= 40.0


def test_score_back_straightness_keeps_aligned_back_high() -> None:
    anchor_progression = [
        {"name": "left_wrist", "time": 0.0, "progression_step": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "progression_step": 0.4, "x": 0.4, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "progression_step": 0.7, "x": 0.7, "y": 0.0},
    ]
    side_coordinates = [
        {"name": "left_hip", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_shoulder", "time": 0.0, "x": 1.0, "y": 1.0},
        {"name": "left_ear", "time": 0.0, "x": 2.0, "y": 2.0},
        {"name": "left_wrist", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_hip", "time": 1.0, "x": 0.4, "y": 0.0},
        {"name": "left_shoulder", "time": 1.0, "x": 1.4, "y": 1.0},
        {"name": "left_ear", "time": 1.0, "x": 2.4, "y": 2.0},
        {"name": "left_wrist", "time": 1.0, "x": 0.4, "y": 0.0},
        {"name": "left_hip", "time": 2.0, "x": 0.7, "y": 0.0},
        {"name": "left_shoulder", "time": 2.0, "x": 1.7, "y": 1.0},
        {"name": "left_ear", "time": 2.0, "x": 2.7, "y": 2.0},
        {"name": "left_wrist", "time": 2.0, "x": 0.7, "y": 0.0},
    ]

    score = _score_back_straightness(
        side_coordinates,
        "left",
        anchor_progression,
    )

    assert score == 100.0


def test_score_back_straightness_penalizes_visible_arch() -> None:
    anchor_progression = [
        {"name": "left_wrist", "time": 0.0, "progression_step": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "progression_step": 0.4, "x": 0.4, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "progression_step": 0.7, "x": 0.7, "y": 0.0},
    ]
    side_coordinates = [
        {"name": "left_hip", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_shoulder", "time": 0.0, "x": 1.0, "y": 0.0},
        {"name": "left_ear", "time": 0.0, "x": 1.2, "y": 0.7},
        {"name": "left_wrist", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_hip", "time": 1.0, "x": 0.4, "y": 0.0},
        {"name": "left_shoulder", "time": 1.0, "x": 1.4, "y": 0.0},
        {"name": "left_ear", "time": 1.0, "x": 1.6, "y": 0.7},
        {"name": "left_wrist", "time": 1.0, "x": 0.4, "y": 0.0},
        {"name": "left_hip", "time": 2.0, "x": 0.7, "y": 0.0},
        {"name": "left_shoulder", "time": 2.0, "x": 1.7, "y": 0.0},
        {"name": "left_ear", "time": 2.0, "x": 1.9, "y": 0.7},
        {"name": "left_wrist", "time": 2.0, "x": 0.7, "y": 0.0},
    ]

    score = _score_back_straightness(
        side_coordinates,
        "left",
        anchor_progression,
    )

    assert score is not None
    assert score < 50.0


def test_score_back_straightness_penalizes_hunched_catch_more_aggressively() -> None:
    anchor_progression = [
        {"name": "left_wrist", "time": 0.0, "progression_step": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "progression_step": 0.2, "x": 0.2, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "progression_step": 0.4, "x": 0.4, "y": 0.0},
    ]
    side_coordinates = [
        {"name": "left_hip", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_shoulder", "time": 0.0, "x": 1.0, "y": 0.0},
        {"name": "left_ear", "time": 0.0, "x": 1.05, "y": 0.35},
        {"name": "left_wrist", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_hip", "time": 1.0, "x": 0.2, "y": 0.0},
        {"name": "left_shoulder", "time": 1.0, "x": 1.2, "y": 0.0},
        {"name": "left_ear", "time": 1.0, "x": 1.25, "y": 0.35},
        {"name": "left_wrist", "time": 1.0, "x": 0.2, "y": 0.0},
        {"name": "left_hip", "time": 2.0, "x": 0.4, "y": 0.0},
        {"name": "left_shoulder", "time": 2.0, "x": 1.4, "y": 0.0},
        {"name": "left_ear", "time": 2.0, "x": 1.45, "y": 0.35},
        {"name": "left_wrist", "time": 2.0, "x": 0.4, "y": 0.0},
    ]

    score = _score_back_straightness(
        side_coordinates,
        "left",
        anchor_progression,
    )

    assert score is not None
    assert score <= 35.0
