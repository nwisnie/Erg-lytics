"""Session helpers for Rowlytics."""

from __future__ import annotations

from flask import session


def user_context() -> dict[str, str | None]:
    return {
        "user_id": session.get("user_id"),
        "user_email": session.get("user_email"),
        "user_name": session.get("user_name"),
    }
