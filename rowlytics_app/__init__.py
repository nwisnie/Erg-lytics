"""Application factory for the Rowlytics web app."""

from __future__ import annotations

import os

from flask import Flask, current_app, jsonify, redirect, request, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .api_routes import api_bp
from .logging_config import setup_logging
from .routes import public_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")

    # Initialize logging first
    setup_logging(app)

    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1, x_prefix=1)
    app.config.from_mapping(
        SECRET_KEY=os.getenv("ROWLYTICS_SECRET_KEY", "dev-secret-key"),
        ROWLYTICS_ENV=os.getenv("ROWLYTICS_ENV", "development"),
        AUTH_REQUIRED=os.getenv("ROWLYTICS_AUTH_REQUIRED", "true").lower() == "true",
        CLOUDFRONT_DOMAIN=os.getenv(
            "ROWLYTICS_CLOUDFRONT_DOMAIN",
            "d3oiecpdwfniky.cloudfront.net",
        ),

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

    # Register Jinja2 filter for CloudFront URLs
    @app.template_filter("cloudfront_url")
    def cloudfront_url(filename):
        """Generate CloudFront URL for static assets."""
        cf_domain = app.config.get("CLOUDFRONT_DOMAIN")
        if not filename.startswith("/"):
            filename = "/" + filename
        return f"https://{cf_domain}{filename}"

    @app.before_request
    def require_auth():
        current_app.logger.info(
            "request path=%s method=%s user=%s",
            request.path,
            request.method,
            session.get("user_id"),
        )
        if not app.config.get("AUTH_REQUIRED"):
            return None
        if request.path.startswith("/static/"):
            return None
        if request.endpoint in {
            "public.signin",
            "public.auth_callback",
            "public.logout",
            "public.favicon_redirect",
        }:
            return None
        if request.path.startswith("/api/"):
            # Allow health check without authentication
            if request.path == "/api/health":
                return None
            if not session.get("user_id"):
                return jsonify({"error": "authentication required"}), 401
            return None
        if not session.get("user_id"):
            return redirect(url_for("public.signin"))
        return None

    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)

    return app
