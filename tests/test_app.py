"""Basic smoke tests for the Rowlytics Flask application."""
from __future__ import annotations

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


def test_create_app_returns_flask_instance(app: Flask) -> None:
    assert isinstance(app, Flask)
    assert app.config["ROWLYTICS_ENV"] in {"development", "production", "staging"}


def test_landing_page_renders_expected_copy(client: FlaskClient) -> None:
    response = client.get("/")
    assert response.status_code == 200

    html = response.get_data(as_text=True)
    expected_snippets = [
        "Erglytics",
    ]
    for snippet in expected_snippets:
        assert snippet in html


def test_template_detail_route(client: FlaskClient) -> None:
    response = client.get("/templates/capture-workout")
    assert response.status_code == 200
    assert "Capture Workout" in response.get_data(as_text=True)
