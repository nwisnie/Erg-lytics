"""Integration tests for the test-email flow."""
from __future__ import annotations

import pytest
from flask import Flask
from flask.testing import FlaskClient

import rowlytics_app.services.mock_email as mock_email
from rowlytics_app import create_app


@pytest.fixture()
def app() -> Flask:
    flask_app = create_app()
    flask_app.config.update(TESTING=True, AUTH_REQUIRED=False)
    return flask_app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_test_email_route_integrates_with_mock_email_pipeline(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SES_TEST_TO", "test@example.com")

    called: dict[str, str] = {}

    def fake_send_email(
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str,
    ) -> str:
        called["to_email"] = to_email
        called["subject"] = subject
        called["body_text"] = body_text
        called["body_html"] = body_html
        return "fake-message-id"

    monkeypatch.setattr(mock_email, "send_email", fake_send_email)

    response = client.get("/test-email")

    assert response.status_code == 200
    assert response.get_data(as_text=True) == "Test email sent to test@example.com"
    assert called["to_email"] == "test@example.com"
    assert called["subject"] == "Rowlytics Statistics Update"
    assert "Hello Beautiful Erglytics Devs" in called["body_text"]
    assert "Hello Beautiful Erglytics Devs" in called["body_html"]
    assert "Varsity Women's Rowing" in called["body_text"]
