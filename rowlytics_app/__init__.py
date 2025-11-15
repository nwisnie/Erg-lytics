"""Application factory for the Rowlytics web app."""

from __future__ import annotations

import os

from flask import Flask

from .api_routes import api_bp
from .routes import public_bp


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_mapping(
        SECRET_KEY=os.getenv("ROWLYTICS_SECRET_KEY", "dev-secret-key"),
        ROWLYTICS_ENV=os.getenv("ROWLYTICS_ENV", "development"),
    )

    app.register_blueprint(public_bp)
    app.register_blueprint(api_bp)

    return app
