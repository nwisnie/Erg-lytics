"""Tests for workout API validation."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient

from rowlytics_app import create_app


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
