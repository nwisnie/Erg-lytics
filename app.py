"""Entry point for the Rowlytics Flask application"""

from __future__ import annotations

import os

from rowlytics_app import create_app

app = create_app()


def _str_to_bool(value: str | None) -> bool:
    return value is not None and value.lower() in {"1", "true", "yes", "on"}


if __name__ == "__main__":
    debug = _str_to_bool(os.getenv("FLASK_DEBUG", "0"))
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=debug)
