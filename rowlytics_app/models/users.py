"""User-related helpers."""

from __future__ import annotations

from uuid import UUID


def canonicalize_display_name(name: str | None) -> str:
    """Trim and collapse whitespace in a display name."""
    if not name:
        return ""
    return " ".join(str(name).split())


def normalize_display_name(name: str | None) -> str:
    """Canonical form used for uniqueness checks."""
    return canonicalize_display_name(name).casefold()


def looks_generated_display_name(
    name: str | None,
    *,
    user_id: str | None = None,
    username: str | None = None,
) -> bool:
    candidate = canonicalize_display_name(name)
    if not candidate:
        return True

    if candidate == "New Rower":
        return True

    if user_id and candidate == user_id:
        return True

    if username and candidate == canonicalize_display_name(username):
        return True

    try:
        UUID(candidate)
        return True
    except ValueError:
        return False
