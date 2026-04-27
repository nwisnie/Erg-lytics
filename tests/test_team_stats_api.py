"""Tests for weekly team stats aggregation."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

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


def test_weekly_team_stats_requires_auth(client: FlaskClient) -> None:
    response = client.get("/api/team/stats/weekly")

    assert response.status_code == 401
    assert response.get_json() == {"error": "authentication required"}


def test_weekly_team_stats_returns_user_and_team_aggregates(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 4, 23, 15, 0, tzinfo=timezone.utc)
    workouts_by_user = {
        "user-1": [
            {
                "workoutId": "u1-a",
                "completedAt": "2026-04-22T14:00:00+00:00",
                "workoutScore": Decimal("80"),
                "armsStraightScore": Decimal("70"),
                "backStraightScore": Decimal("88"),
            },
            {
                "workoutId": "u1-b",
                "completedAt": "2026-04-20T16:00:00+00:00",
                "workoutScore": Decimal("90"),
                "armsStraightScore": Decimal("92"),
                "backStraightScore": Decimal("84"),
            },
            {
                "workoutId": "u1-c",
                "completedAt": "2026-04-21T16:00:00+00:00",
                "armsStraightScore": Decimal("81"),
            },
            {
                "workoutId": "u1-old",
                "completedAt": "2026-04-10T16:00:00+00:00",
                "workoutScore": Decimal("60"),
            },
        ],
        "user-2": [
            {
                "workoutId": "u2-a",
                "completedAt": "2026-04-21T09:00:00+00:00",
                "workoutScore": Decimal("70"),
                "armsStraightScore": Decimal("76"),
                "backStraightScore": Decimal("73"),
            },
            {
                "workoutId": "u2-b",
                "completedAt": "2026-04-19T11:00:00+00:00",
                "workoutScore": Decimal("100"),
                "armsStraightScore": Decimal("98"),
                "backStraightScore": Decimal("91"),
            },
        ],
    }

    monkeypatch.setattr("rowlytics_app.api_routes._now_utc", lambda: fixed_now)
    monkeypatch.setattr("rowlytics_app.api_routes.get_ddb_tables", lambda: (object(), object()))
    monkeypatch.setattr("rowlytics_app.api_routes.get_teams_table", lambda: object())
    monkeypatch.setattr("rowlytics_app.api_routes.get_workouts_table", lambda: object())
    monkeypatch.setattr(
        "rowlytics_app.api_routes.fetch_user_profile",
        lambda user_id: {"userId": user_id, "name": "Noah"},
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.get_team_membership",
        lambda team_members_table, user_id: {"teamId": "team-1", "memberRole": "rower"},
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.get_team",
        lambda teams_table, team_id: {"teamId": team_id, "teamName": "Erglytics Varsity"},
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.fetch_team_members",
        lambda users_table, team_members_table, team_id, allowed_roles: [
            {"userId": "user-1", "name": "Noah"},
            {"userId": "user-2", "name": "Ava"},
        ],
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.list_workouts",
        lambda workouts_table, user_id: workouts_by_user[user_id],
    )

    with client.session_transaction() as session:
        session["user_id"] = "user-1"
        session["user_name"] = "Noah"

    response = client.get("/api/team/stats/weekly")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["windowStart"] == "2026-04-16T15:00:00+00:00"
    assert payload["windowEnd"] == "2026-04-23T15:00:00+00:00"

    assert payload["user"]["title"] == "Noah"
    assert payload["user"]["workoutCount"] == 3
    assert payload["user"]["averageScore"] == 85.0
    assert payload["user"]["averageConsistencyScore"] == 85.0
    assert payload["user"]["averageArmsScore"] == 81.0
    assert payload["user"]["averageBackScore"] == 86.0
    assert [point["workoutId"] for point in payload["user"]["points"]] == ["u1-b", "u1-c", "u1-a"]
    assert [point["score"] for point in payload["user"]["points"]] == [88.67, 81.0, 79.33]

    assert payload["team"]["title"] == "Erglytics Varsity"
    assert payload["team"]["teamId"] == "team-1"
    assert payload["team"]["memberCount"] == 2
    assert payload["team"]["workoutCount"] == 5
    assert payload["team"]["averageScore"] == 85.0
    assert payload["team"]["averageConsistencyScore"] == 85.0
    assert payload["team"]["averageArmsScore"] == 83.4
    assert payload["team"]["averageBackScore"] == 84.0
    assert [point["workoutId"] for point in payload["team"]["points"]] == [
        "u2-b",
        "u1-b",
        "u2-a",
        "u1-c",
        "u1-a",
    ]
    assert [point["score"] for point in payload["team"]["points"]] == [
        96.33,
        88.67,
        73.0,
        81.0,
        79.33,
    ]
    assert [point["isCurrentUser"] for point in payload["team"]["points"]] == [
        False,
        True,
        False,
        True,
        True,
    ]


def test_weekly_team_stats_returns_empty_team_state_when_user_has_no_team(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed_now = datetime(2026, 4, 23, 15, 0, tzinfo=timezone.utc)

    monkeypatch.setattr("rowlytics_app.api_routes._now_utc", lambda: fixed_now)
    monkeypatch.setattr("rowlytics_app.api_routes.get_ddb_tables", lambda: (object(), object()))
    monkeypatch.setattr("rowlytics_app.api_routes.get_teams_table", lambda: object())
    monkeypatch.setattr("rowlytics_app.api_routes.get_workouts_table", lambda: object())
    monkeypatch.setattr(
        "rowlytics_app.api_routes.fetch_user_profile",
        lambda user_id: {"userId": user_id, "name": "Rower One"},
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.get_team_membership",
        lambda team_members_table, user_id: None,
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.list_workouts",
        lambda workouts_table, user_id: [
            {
                "workoutId": "solo-1",
                "completedAt": "2026-04-22T14:00:00+00:00",
                "workoutScore": Decimal("77.5"),
                "armsStraightScore": Decimal("81"),
                "backStraightScore": Decimal("88"),
            },
        ],
    )

    with client.session_transaction() as session:
        session["user_id"] = "user-1"
        session["user_name"] = "Rower One"

    response = client.get("/api/team/stats/weekly")

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["user"]["title"] == "Rower One"
    assert payload["user"]["workoutCount"] == 1
    assert payload["user"]["averageScore"] == 77.5
    assert payload["user"]["averageConsistencyScore"] == 77.5
    assert payload["user"]["averageArmsScore"] == 81.0
    assert payload["user"]["averageBackScore"] == 88.0
    assert payload["user"]["points"] == [
        {
            "armsScore": 81.0,
            "backScore": 88.0,
            "completedAt": "2026-04-22T14:00:00+00:00",
            "consistencyScore": 77.5,
            "displayName": "Rower One",
            "score": 82.17,
            "userId": "user-1",
            "workoutId": "solo-1",
        }
    ]
    assert payload["team"]["title"] == "No team yet"
    assert payload["team"]["teamId"] is None
    assert payload["team"]["workoutCount"] == 0
    assert payload["team"]["averageScore"] is None
    assert payload["team"]["averageConsistencyScore"] is None
    assert payload["team"]["averageArmsScore"] is None
    assert payload["team"]["averageBackScore"] is None
    assert payload["team"]["points"] == []
