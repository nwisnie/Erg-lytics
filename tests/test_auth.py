from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Flask

from rowlytics_app.auth import cognito, sessions


@pytest.fixture()
def app() -> Flask:
    flask_app = Flask(__name__)
    flask_app.config.update(TESTING=True)
    return flask_app


def test_decode_token_payload_returns_dict() -> None:
    header = json.dumps({"alg": "none"}).encode("utf-8")
    payload = json.dumps({"sub": "123"}).encode("utf-8")
    token = (
        cognito.base64.urlsafe_b64encode(header).decode().rstrip("=")
        + "."
        + cognito.base64.urlsafe_b64encode(payload).decode().rstrip("=")
        + ".sig"
    )
    assert cognito.decode_token_payload(token) == {"sub": "123"}


def test_decode_token_payload_handles_errors() -> None:
    assert cognito.decode_token_payload("not-a-jwt") == {}


def test_build_cognito_login_url_missing_config_returns_none(app: Flask) -> None:
    with app.app_context():
        assert cognito.build_cognito_login_url() is None


def test_build_cognito_login_url_builds_expected_url(app: Flask) -> None:
    app.config.update(
        COGNITO_DOMAIN="auth.example.com",
        COGNITO_CLIENT_ID="abc123",
        COGNITO_REDIRECT_URI="https://app.example.com/callback",
    )
    with app.app_context():
        url = cognito.build_cognito_login_url()
    assert url.startswith("https://auth.example.com/oauth2/authorize?")
    assert "client_id=abc123" in url
    assert "redirect_uri=https%3A%2F%2Fapp.example.com%2Fcallback" in url
    assert "scope=openid+email+profile+aws.cognito.signin.user.admin" in url


def test_exchange_code_for_tokens_requires_config(app: Flask) -> None:
    with app.app_context():
        with pytest.raises(RuntimeError):
            cognito.exchange_code_for_tokens("code")


def test_exchange_code_for_tokens_posts_and_parses_response(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    app.config.update(
        COGNITO_DOMAIN="auth.example.com",
        COGNITO_CLIENT_ID="abc123",
        COGNITO_REDIRECT_URI="https://app.example.com/callback",
    )
    fake_resp = MagicMock()
    fake_resp.read.return_value = json.dumps({"id_token": "token"}).encode("utf-8")
    fake_resp.__enter__.return_value = fake_resp

    def fake_urlopen(req):
        fake_urlopen.last_req = req
        return fake_resp

    monkeypatch.setattr(cognito.urlrequest, "urlopen", fake_urlopen)

    with app.app_context():
        tokens = cognito.exchange_code_for_tokens("abc")

    assert tokens == {"id_token": "token"}
    assert fake_urlopen.last_req.full_url == "https://auth.example.com/oauth2/token"


def test_get_cognito_client_requires_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cognito, "boto3", None)
    with pytest.raises(RuntimeError):
        cognito._get_cognito_client()


def test_get_cognito_client_returns_client(monkeypatch: pytest.MonkeyPatch) -> None:
    boto = MagicMock()
    client = MagicMock()
    boto.client.return_value = client
    monkeypatch.setattr(cognito, "boto3", boto)
    assert cognito._get_cognito_client() is client
    boto.client.assert_called_once_with("cognito-idp")


def test_delete_cognito_user_uses_access_token(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.delete_user.return_value = None
    monkeypatch.setattr(cognito, "_get_cognito_client", lambda: client)

    cognito.delete_cognito_user("u1", "u@example.com", "token")

    client.delete_user.assert_called_once_with(AccessToken="token")
    client.admin_delete_user.assert_not_called()


def test_delete_cognito_user_fallbacks_to_admin_delete(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.delete_user.side_effect = Exception("fail")
    client.admin_delete_user.return_value = None
    monkeypatch.setattr(cognito, "_get_cognito_client", lambda: client)
    monkeypatch.setattr(cognito, "COGNITO_USER_POOL_ID", "pool")

    cognito.delete_cognito_user("u1", "u@example.com", "token")

    client.delete_user.assert_called_once()
    client.admin_delete_user.assert_called_once_with(UserPoolId="pool", Username="u@example.com")


def test_delete_cognito_user_requires_pool_or_username(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cognito, "_get_cognito_client", lambda: MagicMock())
    monkeypatch.setattr(cognito, "COGNITO_USER_POOL_ID", "")
    with pytest.raises(RuntimeError):
        cognito.delete_cognito_user("u1", None, None)


def test_delete_cognito_user_raises_with_last_error(monkeypatch: pytest.MonkeyPatch) -> None:
    client = MagicMock()
    client.delete_user.side_effect = Exception("token fail")
    client.admin_delete_user.side_effect = Exception("admin fail")
    monkeypatch.setattr(cognito, "_get_cognito_client", lambda: client)
    monkeypatch.setattr(cognito, "COGNITO_USER_POOL_ID", "pool")

    with pytest.raises(RuntimeError) as err:
        cognito.delete_cognito_user("u1", "u@example.com", "token")

    assert "admin fail" in str(err.value)


def test_user_context_reads_from_flask_session(monkeypatch: pytest.MonkeyPatch) -> None:
    session_store = {"user_id": "u1", "user_email": "u@example.com", "user_name": "User"}
    monkeypatch.setattr(sessions, "session", SimpleNamespace(get=session_store.get))

    ctx = sessions.user_context()

    assert ctx == {
        "user_id": "u1",
        "user_email": "u@example.com",
        "user_name": "User",
    }
