"""Basic smoke tests for the Rowlytics Flask application."""
from __future__ import annotations

from urllib.parse import parse_qs, urlparse

import pytest
from flask import Flask
from flask.testing import FlaskClient

from rowlytics_app import create_app
from rowlytics_app.auth import cognito


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


def test_unknown_route_returns_404(client: FlaskClient) -> None:
    response = client.get("/misc")
    assert response.status_code == 404


def test_landing_page_post_not_allowed(client: FlaskClient) -> None:
    response = client.post("/")
    assert response.status_code in {405, 404}


def test_cognito_login_url_integration() -> None:
    app = Flask(__name__)
    app.config.update(
        COGNITO_DOMAIN="auth.example.com",
        COGNITO_CLIENT_ID="client123",
        COGNITO_REDIRECT_URI="https://app.example.com/callback",
    )

    with app.app_context():
        url = cognito.build_cognito_login_url()

    parsed = urlparse(url)
    query = parse_qs(parsed.query)

    assert parsed.scheme == "https"
    assert parsed.netloc == "auth.example.com"
    assert parsed.path == "/oauth2/authorize"
    assert query["client_id"] == ["client123"]
    assert query["response_type"] == ["code"]
    assert query["redirect_uri"] == ["https://app.example.com/callback"]
