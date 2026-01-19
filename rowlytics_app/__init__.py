"""Application factory for the Rowlytics web app."""

from __future__ import annotations

import os

from flask import Flask, jsonify, redirect, request, session, url_for

from .api_routes import api_bp
from .routes import public_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_mapping(
        SECRET_KEY=os.getenv("ROWLYTICS_SECRET_KEY", "dev-secret-key"),
        ROWLYTICS_ENV=os.getenv("ROWLYTICS_ENV", "development"),
        AUTH_REQUIRED=os.getenv("ROWLYTICS_AUTH_REQUIRED", "true").lower() == "true",

        # change these or set in .env if we change from Cognito
        COGNITO_DOMAIN=os.getenv(
            "ROWLYTICS_COGNITO_DOMAIN",
            "https://rowlytics-auth.auth.us-east-2.amazoncognito.com",
        ),
        COGNITO_CLIENT_ID=os.getenv(
            "ROWLYTICS_COGNITO_CLIENT_ID",
            "6na8lcnrau96407c76atn8641b",
        ),
        COGNITO_REDIRECT_URI=os.getenv(
            "ROWLYTICS_COGNITO_REDIRECT_URI",
            "http://localhost:5000/auth/callback",
        ),
        COGNITO_LOGOUT_REDIRECT_URI=os.getenv(
            "ROWLYTICS_COGNITO_LOGOUT_REDIRECT_URI",
            "http://localhost:5000/signin",
        ),
    )

    @app.before_request
    def require_auth():
        if not app.config.get("AUTH_REQUIRED"):
            return None
        if request.path.startswith("/static/") or request.path == "/favicon.ico":
            return None
        if request.endpoint in {"public.signin", "public.auth_callback", "public.logout"}:
            return None
        if request.path.startswith("/api/"):
            if not session.get("user_id"):
                return jsonify({"error": "authentication required"}), 401
            return None
        if not session.get("user_id"):
            return redirect(url_for("public.signin"))
        return None

    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)

    return app
