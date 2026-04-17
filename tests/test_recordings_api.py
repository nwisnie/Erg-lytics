"""Tests for recording upload API validation."""
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


def test_presign_recording_rejects_when_daily_limit_exceeded(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recordings_table = MagicMock()
    get_s3_client = MagicMock()
    monkeypatch.setattr(
        "rowlytics_app.api_routes.get_recordings_table",
        lambda: recordings_table,
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.sum_recording_durations_for_utc_date",
        lambda *_args, **_kwargs: 7198,
    )
    monkeypatch.setattr("rowlytics_app.api_routes.get_s3_client", get_s3_client)

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.post(
        "/api/recordings/presign",
        json={
            "userId": "other-user",
            "contentType": "video/webm",
            "durationSec": 5,
            "createdAt": "2026-04-05T10:00:00Z",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Daily recording upload limit of 2 hours exceeded"
    get_s3_client.assert_not_called()


def test_save_recording_metadata_rejects_when_daily_limit_exceeded(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recordings_table = MagicMock()
    monkeypatch.setattr(
        "rowlytics_app.api_routes.get_recordings_table",
        lambda: recordings_table,
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.sum_recording_durations_for_utc_date",
        lambda *_args, **_kwargs: 7198,
    )

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.post(
        "/api/recordings",
        json={
            "userId": "other-user",
            "objectKey": "recordings/user-123/clip.webm",
            "contentType": "video/webm",
            "durationSec": 5,
            "createdAt": "2026-04-05T10:00:00Z",
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Daily recording upload limit of 2 hours exceeded"
    recordings_table.put_item.assert_not_called()


def test_save_recording_metadata_uses_session_user_and_normalizes_fields(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recordings_table = MagicMock()
    monkeypatch.setattr(
        "rowlytics_app.api_routes.get_recordings_table",
        lambda: recordings_table,
    )
    monkeypatch.setattr(
        "rowlytics_app.api_routes.sum_recording_durations_for_utc_date",
        lambda *_args, **_kwargs: 0,
    )

    with client.session_transaction() as session:
        session["user_id"] = "user-123"

    response = client.post(
        "/api/recordings",
        json={
            "userId": "other-user",
            "objectKey": "recordings/user-123/clip.webm",
            "contentType": "video/webm",
            "durationSec": 5,
            "createdAt": "2026-04-05T10:15:30Z",
        },
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "ok"
    recordings_table.put_item.assert_called_once()
    item = recordings_table.put_item.call_args.kwargs["Item"]
    assert item["userId"] == "user-123"
    assert item["durationSec"] == 5
    assert item["createdAt"] == "2026-04-05T10:15:30+00:00"
