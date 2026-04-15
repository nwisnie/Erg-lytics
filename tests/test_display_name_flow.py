from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient

from rowlytics_app import api_routes, create_app, routes


@pytest.fixture()
def app() -> Flask:
    flask_app = create_app()
    flask_app.config.update(TESTING=True, AUTH_REQUIRED=True)
    return flask_app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()


def test_auth_callback_redirects_new_user_to_display_name_setup(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(routes, "exchange_code_for_tokens", lambda _code: {"id_token": "token"})
    monkeypatch.setattr(
        routes,
        "decode_token_payload",
        lambda _token: {
            "sub": "user-1",
            "email": "rower@example.com",
            "cognito:username": "generated-user",
        },
    )
    monkeypatch.setattr(routes, "fetch_user_profile", lambda _user_id: {})
    monkeypatch.setattr(routes, "sync_user_profile", lambda *_args: "New Rower")
    monkeypatch.setattr(routes, "publish_login_latency", lambda **_kwargs: None)

    response = client.get("/auth/callback?code=test-code")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/display-name")
    with client.session_transaction() as session:
        assert session["display_name_required"] is True
        assert session["user_name"] == "New Rower"


def test_auth_callback_redirects_established_user_to_home(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(routes, "exchange_code_for_tokens", lambda _code: {"id_token": "token"})
    monkeypatch.setattr(
        routes,
        "decode_token_payload",
        lambda _token: {
            "sub": "user-1",
            "email": "rower@example.com",
            "name": "Boat Mover",
            "cognito:username": "generated-user",
        },
    )
    monkeypatch.setattr(routes, "fetch_user_profile", lambda _user_id: {})
    monkeypatch.setattr(routes, "sync_user_profile", lambda *_args: "Boat Mover")
    monkeypatch.setattr(routes, "publish_login_latency", lambda **_kwargs: None)

    response = client.get("/auth/callback?code=test-code")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/")
    with client.session_transaction() as session:
        assert session["display_name_required"] is False
        assert session["user_name"] == "Boat Mover"


def test_signed_in_user_is_gated_to_display_name_setup(client: FlaskClient) -> None:
    with client.session_transaction() as session:
        session["user_id"] = "user-1"
        session["user_name"] = "New Rower"
        session["display_name_required"] = True

    response = client.get("/")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/display-name")


def test_display_name_setup_page_is_available_while_gated(client: FlaskClient) -> None:
    with client.session_transaction() as session:
        session["user_id"] = "user-1"
        session["user_name"] = "New Rower"
        session["display_name_required"] = True

    response = client.get("/display-name")

    assert response.status_code == 200
    assert "Choose your display name" in response.get_data(as_text=True)


def test_update_account_name_rejects_duplicate_display_name(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with client.session_transaction() as session:
        session["user_id"] = "user-1"
        session["user_email"] = "rower@example.com"
        session["display_name_required"] = True

    monkeypatch.setattr(api_routes, "get_ddb_tables", lambda: (MagicMock(), MagicMock()))
    monkeypatch.setattr(api_routes, "display_name_exists", lambda *_args, **_kwargs: True)

    response = client.post("/api/account/name", json={"name": "Boat Mover"})

    assert response.status_code == 409
    assert response.get_json() == {"error": "Display name already in use"}
    with client.session_transaction() as session:
        assert session["display_name_required"] is True


def test_update_account_name_clears_onboarding_flag_on_success(
    client: FlaskClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    users_table = MagicMock()

    with client.session_transaction() as session:
        session["user_id"] = "user-1"
        session["user_email"] = "rower@example.com"
        session["display_name_required"] = True

    monkeypatch.setattr(api_routes, "get_ddb_tables", lambda: (users_table, MagicMock()))
    monkeypatch.setattr(api_routes, "display_name_exists", lambda *_args, **_kwargs: False)

    response = client.post("/api/account/name", json={"name": "Boat Mover"})

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok", "name": "Boat Mover"}
    users_table.update_item.assert_called_once()
    with client.session_transaction() as session:
        assert session["display_name_required"] is False
        assert session["user_name"] == "Boat Mover"
