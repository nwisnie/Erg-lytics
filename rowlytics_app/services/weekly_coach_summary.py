"""Weekly coach summary email service."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from flask import render_template

from rowlytics_app.services.dynamodb import (
    fetch_team_members,
    get_team,
    get_team_members_table,
    get_teams_table,
    get_users_table,
    get_workouts_table,
    list_workouts,
    scan_all,
    update_coach_summary_sent_at,
)
from rowlytics_app.services.ses_email import send_email


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _num(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError, Decimal.InvalidOperation):
        return None


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


def _list_all_teams() -> list[dict]:
    return scan_all(get_teams_table())


def _weekly_workouts_for_rowers(rower_ids: list[str]) -> list[dict]:
    workouts_table = get_workouts_table()
    week_start = _iso(_utc_now() - timedelta(days=7))

    workouts = []
    for user_id in rower_ids:
        for workout in list_workouts(workouts_table, user_id):
            completed_at = workout.get("completedAt") or workout.get("createdAt") or ""
            if completed_at >= week_start:
                workouts.append(workout)

    return workouts


def _average_metric(workouts: list[dict], key: str) -> float | None:
    values = []

    for workout in workouts:
        value = workout.get(key)
        if value is None:
            continue

        try:
            values.append(float(value))
        except (TypeError, ValueError):
            continue

    if not values:
        return None

    return round(sum(values) / len(values), 1)


def _summarize_workouts_for_email(workouts: list[dict]) -> dict:
    return {
        "workouts_completed": len(workouts),
        "average_consistency_score": _average_metric(workouts, "workoutScore"),
        "average_arms_score": _average_metric(workouts, "armsStraightScore"),
        "average_back_score": _average_metric(workouts, "backStraightScore"),
    }


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

    rowers = [
        member
        for member in members
        if member.get("memberRole") == "rower"
    ]

    rower_names = [
        rower.get("name") or "Unnamed athlete"
        for rower in rowers
    ]

    team_member_ids = [
        member["userId"]
        for member in members
        if member.get("userId")
    ]

    workout_summary = _summarize_workouts_for_email(
        _weekly_workouts_for_rowers(team_member_ids)
    )

    return {
        "team_id": team_id,
        "team_name": team.get("teamName") or "Unnamed Team",
        "member_names": member_names,
        "member_count": len(member_names),
        "coach_names": coach_names,
        "coach_count": len(coach_names),
        "rower_names": rower_names,
        "rower_count": len(rower_names),
        **workout_summary,
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
                "userId": member.get("userId"),
                "name": member.get("name") or "Coach",
                "email": member["email"],
                "emailUpdateIntervalValue": member.get("emailUpdateIntervalValue", 1),
                "emailUpdateIntervalUnit": member.get("emailUpdateIntervalUnit", "weeks"),
                "emailUpdateIntervalUpdatedAt": member.get("emailUpdateIntervalUpdatedAt"),
                "lastCoachSummarySentAt": member.get("lastCoachSummarySentAt"),
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
    teams = _list_all_teams()

    emails_sent = 0
    emails_attempted = 0
    errors = []
    processed_teams = []

    for team in teams:
        team_id = team.get("teamId")
        if not team_id:
            continue

        try:
            summary = get_team_summary_for_email(team_id)
            coaches = get_team_coach_recipients(team_id)

            if not coaches:
                processed_teams.append(
                    {
                        "team_id": team_id,
                        "team_name": summary["team_name"],
                        "emails_attempted": 0,
                        "emails_sent": 0,
                        "skipped_reason": "No coach emails found",
                    }
                )
                continue

            team_sent = 0

            now = datetime.now(timezone.utc)

            for coach in coaches:
                if not _coach_email_due(coach, now):
                    continue

                emails_attempted += 1
                try:
                    send_weekly_coach_summary_email(coach["email"], summary)
                    update_coach_summary_sent_at(coach["userId"], now.isoformat())
                    emails_sent += 1
                    team_sent += 1
                except Exception as exc:
                    errors.append(
                        {
                            "team_id": team_id,
                            "coach_email": coach["email"],
                            "error": str(exc),
                        }
                    )

            processed_teams.append(
                {
                    "team_id": team_id,
                    "team_name": summary["team_name"],
                    "emails_attempted": len(coaches),
                    "emails_sent": team_sent,
                    "member_count": summary["member_count"],
                    "workouts_completed": summary["workouts_completed"],
                }
            )

        except Exception as exc:
            errors.append(
                {
                    "team_id": team_id,
                    "error": str(exc),
                }
            )

    return {
        "status": "success" if not errors else "partial_failure",
        "teams_processed": len(processed_teams),
        "emails_attempted": emails_attempted,
        "emails_sent": emails_sent,
        "errors": errors,
        "teams": processed_teams,
    }


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    candidate = value.strip()
    if candidate.endswith("Z"):
        candidate = f"{candidate[:-1]}+00:00"

    try:
        parsed = datetime.fromisoformat(candidate)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _interval_to_timedelta(value, unit) -> timedelta:
    try:
        interval_value = int(value)
    except (TypeError, ValueError):
        interval_value = 1

    if interval_value < 1:
        interval_value = 1

    interval_unit = str(unit or "weeks").lower()

    if interval_unit == "minutes":
        return timedelta(minutes=interval_value)
    if interval_unit == "hours":
        return timedelta(hours=interval_value)
    if interval_unit == "days":
        return timedelta(days=interval_value)
    if interval_unit == "weeks":
        return timedelta(weeks=interval_value)
    if interval_unit == "months":
        return timedelta(days=interval_value * 30)

    return timedelta(weeks=1)


def _coach_email_due(coach: dict, now: datetime) -> bool:
    last_sent = _parse_iso_datetime(coach.get("lastCoachSummarySentAt"))

    if last_sent is None:
        updated_at = _parse_iso_datetime(coach.get("emailUpdateIntervalUpdatedAt"))
        if updated_at is None:
            return True

        return now >= updated_at + _interval_to_timedelta(
            coach.get("emailUpdateIntervalValue"),
            coach.get("emailUpdateIntervalUnit"),
        )

    return now >= last_sent + _interval_to_timedelta(
        coach.get("emailUpdateIntervalValue"),
        coach.get("emailUpdateIntervalUnit"),
    )
