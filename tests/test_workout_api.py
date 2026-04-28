"""Tests for workout API validation."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
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


def _load_example_clip_frames(filename: str) -> tuple[list[list[dict | None]], float]:
    path = Path(__file__).resolve().parents[1] / "example_clips" / filename
    payload = json.loads(path.read_text())
    return payload["recordedLandmarkFrames"], float(payload["recordingDurationSec"])


def _load_example_gate_frames(
    filename: str,
) -> tuple[list[list[dict | None]], float, str | None]:
    path = Path(__file__).resolve().parents[1] / "example_clips" / filename
    payload = json.loads(path.read_text())
    gate = payload["gateMovement"]
    return (
        gate["gateFrames"],
        float(gate["gateDurationSec"]),
        gate.get("dominantSide"),
    )


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
    good_frames, good_duration, good_side = _load_example_gate_frames(
        "rowlytics-capture-debug-clip-1-2026-04-28T03-15-13-704Z.json",
    )
    bad_frames, bad_duration, bad_side = _load_example_gate_frames(
        "rowlytics-capture-debug-clip-1-2026-04-28T03-20-28-534Z.json",
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
    bad_frames, bad_duration, bad_side = _load_example_gate_frames(
        "rowlytics-capture-debug-clip-1-2026-04-28T03-20-28-534Z.json",
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
