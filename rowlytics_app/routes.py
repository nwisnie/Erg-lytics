"""Public-facing routes for the Rowlytics marketing site."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable
from urllib import parse

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
    decode_token_payload,
    exchange_code_for_tokens,
)
from rowlytics_app.auth.sessions import user_context
from rowlytics_app.services.dynamodb import sync_user_profile

public_bp = Blueprint("public", __name__)


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
        image_path="images/camera_cool.png",
        template_name="capture_workout.html",
    ),
    TemplateCard(
        slug="snapshot-library",
        title="Snapshot Library",
        blurb="View important moments captured during workouts.",
        image_path="images/snapshot_cool.png",
        template_name="snapshot_library.html",
    ),
    TemplateCard(
        slug="workout-summaries",
        title="Workout Summaries",
        blurb="View summaries and analytics from previous workouts.",
        image_path="images/folder_cool.png",
        template_name="workout_summaries.html",
    ),
    TemplateCard(
        slug="team-view",
        title="Team View",
        blurb="Join a team of like minded athletes and track collective progress.",
        image_path="images/team_cool.png",
        template_name="team_view.html",
    ),
)


def _iter_cards() -> Iterable[TemplateCard]:
    return iter(TEMPLATE_CARDS)


def _get_card(slug: str) -> TemplateCard | None:
    return next((card for card in TEMPLATE_CARDS if card.slug == slug), None)


@public_bp.route("/")
def landing_page() -> str:
    return render_template("index.html", **user_context())


@public_bp.route("/templates/<slug>")
def template_detail(slug: str) -> str:
    card = _get_card(slug)
    if card is None:
        abort(404)
    return render_template(card.template_name, card=card, **user_context())


@public_bp.route("/profile")
def profile() -> str:
    return render_template("profile.html", **user_context())


@public_bp.route("/account-settings")
def account_settings() -> str:
    return render_template("account_settings.html", **user_context())


@public_bp.route("/signin")
def signin() -> str:
    if session.get("user_id"):
        return redirect(url_for("public.landing_page"))
    login_url = build_cognito_login_url()
    return render_template("sign_in.html", login_url=login_url)


@public_bp.route("/auth/callback")
def auth_callback() -> str:
    code = request.args.get("code")
    if not code:
        return render_template("sign_in.html",
                               login_url=build_cognito_login_url(),
                               error="Missing auth code."), 400
    try:
        tokens = exchange_code_for_tokens(code)
    except Exception as err:
        return render_template(
            "sign_in.html",
            login_url=build_cognito_login_url(),
            error=f"Auth failed: {err}",
        ), 400

    id_token = tokens.get("id_token")
    if not id_token:
        return render_template(
            "sign_in.html",
            login_url=build_cognito_login_url(),
            error="Missing ID token from Cognito.",
        ), 400

    payload = decode_token_payload(id_token)
    session["id_token"] = id_token
    session["access_token"] = tokens.get("access_token")
    session["user_id"] = payload.get("sub")
    session["user_email"] = payload.get("email")
    session["user_name"] = payload.get("name") or payload.get("cognito:username")

    stored_name = sync_user_profile(
        session.get("user_id"),
        session.get("user_email"),
        session.get("user_name"),
    )
    if stored_name:
        session["user_name"] = stored_name

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
