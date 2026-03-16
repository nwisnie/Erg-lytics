"""Tests for mock auto email composition and send behavior."""
from __future__ import annotations

import pytest
from flask import Flask

from rowlytics_app import create_app
from rowlytics_app.services import mock_email


@pytest.fixture()
def app() -> Flask:
    flask_app = create_app()
    flask_app.config.update(TESTING=True, AUTH_REQUIRED=False)
    return flask_app


def test_send_mock_auto_email_calls_send_email_with_expected_arguments(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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

    with app.app_context():
        result = mock_email.send_mock_auto_email("test@example.com", "Kassie")

    assert result == "fake-message-id"
    assert called["to_email"] == "test@example.com"
    assert called["subject"] == "Rowlytics Statistics Update"
    assert "Hello Kassie" in called["body_text"]
    assert "Hello Kassie" in called["body_html"]


def test_send_mock_auto_email_uses_default_name_when_name_is_none(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, str] = {}

    def fake_send_email(
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str,
    ) -> str:
        called["body_text"] = body_text
        called["body_html"] = body_html
        return "fake-message-id"

    monkeypatch.setattr(mock_email, "send_email", fake_send_email)

    with app.app_context():
        mock_email.send_mock_auto_email("test@example.com", None)

    assert "Hello Rower" in called["body_text"]
    assert "Hello Rower" in called["body_html"]


def test_send_mock_auto_email_includes_expected_content(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, str] = {}

    def fake_send_email(
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str,
    ) -> str:
        called["body_text"] = body_text
        called["body_html"] = body_html
        return "fake-message-id"

    monkeypatch.setattr(mock_email, "send_email", fake_send_email)

    with app.app_context():
        mock_email.send_mock_auto_email("test@example.com", "Kassie")

    assert "PERSONAL STATISTICS" in called["body_text"]
    assert "TEAM STATISTICS" in called["body_text"]
    assert "52,000 m" in called["body_text"]
    assert "Varsity Women's Rowing" in called["body_text"]
    assert "https://ra7jdv1jj1.execute-api.us-east-2.amazonaws.com/Prod" in called["body_text"]

    assert "Personal Statistics" in called["body_html"]
    assert "Team Statistics" in called["body_html"]
    assert "52,000 m" in called["body_html"]
    assert "Varsity Women" in called["body_html"]
    assert "https://ra7jdv1jj1.execute-api.us-east-2.amazonaws.com/Prod" in called["body_html"]


def test_send_mock_auto_email_propagates_send_email_error(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_send_email(
        to_email: str,
        subject: str,
        body_text: str,
        body_html: str,
    ) -> str:
        raise RuntimeError("boom")

    monkeypatch.setattr(mock_email, "send_email", fake_send_email)

    with app.app_context():
        with pytest.raises(RuntimeError, match="boom"):
            mock_email.send_mock_auto_email("test@example.com", "Kassie")
