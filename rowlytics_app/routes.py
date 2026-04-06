"""Public-facing routes for the Rowlytics marketing site."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Iterable
from urllib import parse
from uuid import UUID

from flask import (
    Blueprint,
    abort,
    current_app,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from rowlytics_app.auth.cognito import (
    build_cognito_login_url,
    build_cognito_signup_url,
    decode_token_payload,
    exchange_code_for_tokens,
)
from rowlytics_app.auth.sessions import user_context
from rowlytics_app.services.dynamodb import fetch_user_profile, sync_user_profile
from rowlytics_app.services.metrics import publish_login_latency
from rowlytics_app.services.mock_email import send_mock_auto_email

public_bp = Blueprint("public", __name__)
APP_VERSION = "0.0.1"


@dataclass(frozen=True)
class TemplateCard:
    slug: str
    title: str
    blurb: str
    image_path: str
    template_name: str


TEMPLATE_CARDS: tuple[TemplateCard, ...] = (
    TemplateCard(
        slug="capture-workout",
        title="Capture Workout",
        blurb="Record your workout and get feedback live.",
        image_path=(
            "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com/"
            "images/camera_cool.png"
        ),
        template_name="capture_workout.html",
    ),
    TemplateCard(
        slug="snapshot-library",
        title="Snapshot Library",
        blurb="View important moments captured during workouts.",
        image_path=(
            "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com/"
            "images/snapshot_cool.png"
            ),
        template_name="snapshot_library.html",
    ),
    TemplateCard(
        slug="workout-summaries",
        title="Workout Summaries",
        blurb="View summaries and analytics from previous workouts.",
        image_path=(
            "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com/"
            "images/folder_cool.png"
            ),
        template_name="workout_summaries.html",
    ),
    TemplateCard(
        slug="team-view",
        title="Team View",
        blurb="Join a team of like minded athletes and track collective progress.",
        image_path=(
            "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com/"
            "images/team_cool.png"
            ),
        template_name="team_view.html",
    ),
    TemplateCard(
        slug="manage-team",
        title="Manage Team",
        blurb="Currently a placeholder.",
        image_path=(
            "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com/"
            "images/team_settings_cool.png"
            ),
        template_name="manage_team.html",
    ),
    TemplateCard(
        slug="team-stats",
        title="Team Stats",
        blurb="Currently a placeholder.",
        image_path=(
            "https://rowlytics-static-assets.s3.us-east-2.amazonaws.com/"
            "images/stats_cool.png"
            ),
        template_name="team_stats.html",
    ),
)


def _iter_cards() -> Iterable[TemplateCard]:
    return iter(TEMPLATE_CARDS)


def _get_card(slug: str) -> TemplateCard | None:
    return next((card for card in TEMPLATE_CARDS if card.slug == slug), None)


def _looks_generated_display_name(
    name: str | None,
    *,
    user_id: str | None = None,
    username: str | None = None,
) -> bool:
    if not name:
        return True

    candidate = name.strip()
    if not candidate:
        return True

    if candidate == "New Rower":
        return True

    if user_id and candidate == user_id:
        return True

    if username and candidate == username:
        return True

    try:
        UUID(candidate)
        return True
    except ValueError:
        return False


@public_bp.route("/")
def landing_page() -> str:
    return render_template("index.html", cards=TEMPLATE_CARDS, **user_context())


@public_bp.route("/templates/<slug>")
def template_detail(slug: str) -> str:
    card = _get_card(slug)
    if card is None:
        abort(404)
    return render_template(card.template_name, card=card, **user_context())


@public_bp.route("/workout-summaries/<workout_id>")
def workout_summary_detail(workout_id: str) -> str:
    return render_template(
        "workout_summary_detail.html",
        workout_id=workout_id,
        **user_context(),
    )


@public_bp.route("/profile")
def profile() -> str:
    return render_template("profile.html", **user_context())


@public_bp.route("/settings")
def settings() -> str:
    return render_template(
        "settings.html",
        display_name_required=request.args.get("require_display_name") == "1",
        **user_context(),
    )


@public_bp.route("/signin")
def signin() -> str:
    if session.get("user_id"):
        return redirect(url_for("public.landing_page"))
    login_url = build_cognito_login_url()
    signup_url = build_cognito_signup_url()
    return render_template("sign_in.html", login_url=login_url, signup_url=signup_url)


@public_bp.route("/auth/callback")
def auth_callback() -> str:
    start = time.perf_counter()
    code = request.args.get("code")
    if not code:
        return render_template("sign_in.html",
                               login_url=build_cognito_login_url(),
                               signup_url=build_cognito_signup_url(),
                               error="Missing auth code."), 400
    try:
        tokens = exchange_code_for_tokens(code)
    except Exception as err:
        return render_template(
            "sign_in.html",
            login_url=build_cognito_login_url(),
            signup_url=build_cognito_signup_url(),
            error=f"Auth failed: {err}",
        ), 400

    id_token = tokens.get("id_token")
    if not id_token:
        return render_template(
            "sign_in.html",
            login_url=build_cognito_login_url(),
            signup_url=build_cognito_signup_url(),
            error="Missing ID token from Cognito.",
        ), 400

    payload = decode_token_payload(id_token)
    raw_name = (payload.get("name") or "").strip() or None
    raw_username = (payload.get("cognito:username") or "").strip() or None
    user_id = payload.get("sub")
    existing_profile = fetch_user_profile(user_id)
    existing_name = (existing_profile.get("name") or "").strip() or None

    session["id_token"] = id_token
    session["access_token"] = tokens.get("access_token")
    session["user_id"] = user_id
    session["user_email"] = payload.get("email")
    session["user_name"] = raw_name or existing_name or raw_username

    end = time.perf_counter()
    latency = (end - start) * 1000
    publish_login_latency(
        latency_ms=latency,
        environment=current_app.config.get("ROWLYTICS_ENV", "development"),
    )

    stored_name = sync_user_profile(
        session.get("user_id"),
        session.get("user_email"),
        raw_name,
    )
    if stored_name:
        session["user_name"] = stored_name

    if _looks_generated_display_name(
        stored_name,
        user_id=session.get("user_id"),
        username=raw_username,
    ):
        return redirect(url_for("public.settings", require_display_name="1"))

    return redirect(url_for("public.landing_page"))


@public_bp.route("/logout")
def logout() -> str:
    session.clear()
    domain = current_app.config.get("COGNITO_DOMAIN")
    client_id = current_app.config.get("COGNITO_CLIENT_ID")
    logout_uri = current_app.config.get("COGNITO_LOGOUT_REDIRECT_URI")
    if not domain or not client_id or not logout_uri:
        return redirect(url_for("public.signin"))
    query = parse.urlencode({
        "client_id": client_id,
        "logout_uri": logout_uri,
    })
    return redirect(f"https://{domain}/logout?{query}")


@public_bp.route("/favicon.ico")
def favicon_redirect():
    """Redirect /favicon.ico to /static/favicon.ico to handle browser requests."""
    return redirect(url_for("static", filename="favicon.ico"), code=301)


@public_bp.route("/test-email")
def test_email():
    import os

    test_to = os.getenv("SES_TEST_TO")

    if not test_to:
        return "SES_TEST_TO is not configured"

    try:
        send_mock_auto_email(to_email=test_to, name="Beautiful Erglytics Devs")
        return f"Test email sent to {test_to}"
    except Exception as exc:
        return f"Failed to send email: {exc}"
