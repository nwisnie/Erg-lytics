"""Tests for workout API validation."""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient

from rowlytics_app import create_app
from rowlytics_app.api_routes import (
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
    assert score >= 90.0


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


def test_score_arms_straightness_penalizes_large_bend() -> None:
    anchor_progression = [
        {"name": "left_wrist", "time": 0.0, "progression_step": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_wrist", "time": 1.0, "progression_step": 0.2, "x": 1.0, "y": 0.0},
        {"name": "left_wrist", "time": 2.0, "progression_step": 0.4, "x": 2.0, "y": 0.0},
    ]

    side_coordinates = [
        # frame 0: bent elbow
        {"name": "left_shoulder", "time": 0.0, "x": 0.0, "y": 0.0},
        {"name": "left_elbow", "time": 0.0, "x": 1.0, "y": 1.0},
        {"name": "left_wrist", "time": 0.0, "x": 2.0, "y": 0.0},

        # frame 1: bent elbow
        {"name": "left_shoulder", "time": 1.0, "x": 1.0, "y": 0.0},
        {"name": "left_elbow", "time": 1.0, "x": 2.0, "y": 1.0},
        {"name": "left_wrist", "time": 1.0, "x": 3.0, "y": 0.0},

        # frame 2: bent elbow
        {"name": "left_shoulder", "time": 2.0, "x": 2.0, "y": 0.0},
        {"name": "left_elbow", "time": 2.0, "x": 3.0, "y": 1.0},
        {"name": "left_wrist", "time": 2.0, "x": 4.0, "y": 0.0},
    ]

    score = _score_arms_straightness(
        side_coordinates,
        "left",
        anchor_progression,
    )

    assert score is not None
    assert score < 100.0
