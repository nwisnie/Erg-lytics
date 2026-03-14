""""Tests for the /test-email route. (added with mock_email.py)"""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

import rowlytics_app.routes as routes
from rowlytics_app import create_app


@pytest.fixture()
def app() -> Flask:
    flask_app = create_app()
    flask_app.config.update(TESTING=True, AUTH_REQUIRED=False)
    return flask_app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_test_email_route_returns_message_when_env_missing(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SES_TEST_TO", raising=False)

    response = client.get("/test-email")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "SES_TEST_TO is not configured"


def test_test_email_route_sends_mock_email_when_env_present(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SES_TEST_TO", "test@example.com")

    called: dict[str, str] = {}

    def fake_send_mock_auto_email(to_email: str, name: str | None = None) -> str:
        called["to_email"] = to_email
        called["name"] = name or ""
        return "fake-message-id"

    monkeypatch.setattr(routes, "send_mock_auto_email", fake_send_mock_auto_email)

    response = client.get("/test-email")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Test email sent to test@example.com"
    assert called == {
        "to_email": "test@example.com",
        "name": "Beautiful Erglytics Devs",
    }


def test_test_email_route_returns_failure_message_when_send_fails(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SES_TEST_TO", "test@example.com")

    def fake_send_mock_auto_email(to_email: str, name: str | None = None) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(routes, "send_mock_auto_email", fake_send_mock_auto_email)

    response = client.get("/test-email")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Failed to send email: boom"
