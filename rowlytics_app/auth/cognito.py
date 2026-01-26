"""Cognito helpers for authentication flows."""

from __future__ import annotations

import base64
import json
import os
from urllib import parse
from urllib import request as urlrequest

from flask import current_app

try:
    import boto3
except ImportError:  # pragma: no cover - boto3 only needed when AWS is used
    boto3 = None

COGNITO_USER_POOL_ID = os.getenv("ROWLYTICS_COGNITO_USER_POOL_ID", "")


def decode_token_payload(token: str) -> dict:
    try:
        payload_segment = token.split(".")[1]
        padding = "=" * (-len(payload_segment) % 4)
        payload_bytes = base64.urlsafe_b64decode(payload_segment + padding)
        return json.loads(payload_bytes.decode("utf-8"))
    except Exception:
        return {}


def build_cognito_login_url() -> str | None:
    domain = current_app.config.get("COGNITO_DOMAIN")
    client_id = current_app.config.get("COGNITO_CLIENT_ID")
    redirect_uri = current_app.config.get("COGNITO_REDIRECT_URI")
    if not domain or not client_id or not redirect_uri:
        return None
    query = parse.urlencode({
        "client_id": client_id,
        "response_type": "code",
        "scope": "openid email profile aws.cognito.signin.user.admin",
        "redirect_uri": redirect_uri,
    })
    return f"https://{domain}/oauth2/authorize?{query}"


def exchange_code_for_tokens(code: str) -> dict:
    domain = current_app.config.get("COGNITO_DOMAIN")
    client_id = current_app.config.get("COGNITO_CLIENT_ID")
    redirect_uri = current_app.config.get("COGNITO_REDIRECT_URI")
    if not domain or not client_id or not redirect_uri:
        raise RuntimeError("Cognito configuration is missing")
    token_url = f"https://{domain}/oauth2/token"
    data = parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": redirect_uri,
    }).encode("utf-8")
    req = urlrequest.Request(
        token_url,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urlrequest.urlopen(req) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_cognito_client():
    if boto3 is None:
        raise RuntimeError("boto3 is required for Cognito access")
    return boto3.client("cognito-idp")


def delete_cognito_user(user_id: str, email: str | None, access_token: str | None):
    client = _get_cognito_client()
    last_error = None

    if access_token:
        try:
            client.delete_user(AccessToken=access_token)
            return
        except Exception as err:
            last_error = err

    username = email or user_id
    if not COGNITO_USER_POOL_ID or not username:
        raise RuntimeError("Missing Cognito pool id or username")

    try:
        client.admin_delete_user(UserPoolId=COGNITO_USER_POOL_ID, Username=username)
        return
    except Exception as err:
        last_error = err

    raise RuntimeError(str(last_error) if last_error else "Unable to delete Cognito user")
