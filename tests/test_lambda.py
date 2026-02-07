from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

# Provide stub awsgi if dependency is absent so importing app.py succeeds in CI.
if "awsgi" not in sys.modules:
    sys.modules["awsgi"] = MagicMock()

import app as lambda_app


def test_inject_stage_prefix_no_stage_returns_event_unchanged() -> None:
    event = {"headers": {"Some": "Header"}}
    assert lambda_app._inject_stage_prefix(event.copy()) == event


def test_inject_stage_prefix_sets_header_when_missing() -> None:
    event = {
        "requestContext": {"stage": "dev"},
        "headers": {"Host": "example.com"},
    }
    result = lambda_app._inject_stage_prefix(event)
    assert result["headers"]["X-Forwarded-Prefix"] == "/dev"
    # keep original headers too
    assert result["headers"]["Host"] == "example.com"


def test_inject_stage_prefix_preserves_existing_prefix_header() -> None:
    event = {
        "requestContext": {"stage": "prod"},
        "headers": {"X-Forwarded-Prefix": "/api"},
    }
    result = lambda_app._inject_stage_prefix(event)
    assert result["headers"]["X-Forwarded-Prefix"] == "/api"


def test_lambda_handler_calls_awsgi_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_response = {"statusCode": 200}
    awsgi_mock = MagicMock()
    awsgi_mock.response.return_value = fake_response
    monkeypatch.setattr(lambda_app, "awsgi", awsgi_mock)
    event = {"requestContext": {}, "headers": {}}
    ctx = MagicMock()

    result = lambda_app.lambda_handler(event, ctx)

    assert result is fake_response
    awsgi_mock.response.assert_called_once()
    _, args, kwargs = awsgi_mock.response.mock_calls[0]
    # args: (app, event, context)
    assert args[0] is lambda_app.app
    assert args[1]["headers"] == {}
    assert args[2] is ctx
    assert "base64_content_types" in kwargs
