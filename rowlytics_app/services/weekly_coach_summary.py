"""Weekly coach summary email service."""

from __future__ import annotations

import os

from flask import render_template

from rowlytics_app.services.dynamodb import (
    fetch_team_members,
    get_team,
    get_team_members_table,
    get_teams_table,
    get_users_table,
)
from rowlytics_app.services.ses_email import send_email


def _get_team_and_members(team_id: str):
    users_table = get_users_table()
    team_members_table = get_team_members_table()
    teams_table = get_teams_table()

    team = get_team(teams_table, team_id)
    if not team:
        raise RuntimeError(f"Team {team_id} was not found")

    members = fetch_team_members(
        users_table,
        team_members_table,
        team_id,
        allowed_roles={"coach", "rower"},
    )
    return team, members


def get_team_summary_for_email(team_id: str) -> dict:
    team, members = _get_team_and_members(team_id)

    member_names = [
        member.get("name") or "Unnamed athlete"
        for member in members
    ]
    coach_names = [
        member.get("name") or "Unnamed coach"
        for member in members
        if member.get("memberRole") == "coach"
    ]
    rower_names = [
        member.get("name") or "Unnamed athlete"
        for member in members
        if member.get("memberRole") == "rower"
    ]

    return {
        "team_id": team_id,
        "team_name": team.get("teamName") or "Unnamed Team",
        "member_names": member_names,
        "member_count": len(member_names),
        "coach_names": coach_names,
        "coach_count": len(coach_names),
        "rower_names": rower_names,
        "rower_count": len(rower_names),
        "workouts_completed": 12,
        "avg_split": "2:03.4",
        "avg_rate": 28,
    }


def get_team_coach_recipients(team_id: str) -> list[dict]:
    _, members = _get_team_and_members(team_id)

    coaches = []
    for member in members:
        if member.get("memberRole") != "coach":
            continue
        if not member.get("email"):
            continue

        coaches.append(
            {
                "name": member.get("name") or "Coach",
                "email": member["email"],
            }
        )

    return coaches


def send_weekly_coach_summary_email(to_email: str, summary: dict) -> None:
    subject = f"Weekly Team Summary - {summary['team_name']}"

    body_html = render_template(
        "emails/weekly_coach_summary.html",
        summary=summary,
    )

    send_email(
        to_email=to_email,
        subject=subject,
        body_text=f"Weekly Team Summary for {summary['team_name']}",
        body_html=body_html,
    )


def run_weekly_coach_summaries() -> dict:
    team_id = os.getenv("WEEKLY_SUMMARY_TEST_TEAM_ID")
    if not team_id:
        raise RuntimeError("WEEKLY_SUMMARY_TEST_TEAM_ID is not configured")

    summary = get_team_summary_for_email(team_id)
    coaches = get_team_coach_recipients(team_id)

    if not coaches:
        fallback = os.getenv("SES_TEST_TO")
        if not fallback:
            raise RuntimeError("No coach emails found and SES_TEST_TO is not configured")
        coaches = [{"name": "Coach", "email": fallback}]

    emails_sent = 0
    errors = []

    for coach in coaches:
        try:
            send_weekly_coach_summary_email(coach["email"], summary)
            emails_sent += 1
        except Exception as exc:
            errors.append(
                {
                    "coach_email": coach["email"],
                    "error": str(exc),
                }
            )

    status = "success" if not errors else "partial_failure"

    return {
        "status": status,
        "emails_attempted": len(coaches),
        "emails_sent": emails_sent,
        "errors": errors,
        "team_name": summary["team_name"],
        "member_count": summary["member_count"],
        "coach_emails": [coach["email"] for coach in coaches],
    }