"""Entry point for the Rowlytics Flask application."""

from __future__ import annotations

import json

import awsgi

from rowlytics_app import create_app
from rowlytics_app.services.weekly_coach_summary import run_weekly_coach_summaries

app = create_app()


def _inject_stage_prefix(event):
    request_context = event.get("requestContext") or {}
    stage = request_context.get("stage")
    if not stage:
        return event

    headers = event.get("headers") or {}
    header_keys = {key.lower() for key in headers}
    if "x-forwarded-prefix" not in header_keys:
        headers["X-Forwarded-Prefix"] = f"/{stage}"
    event["headers"] = headers
    return event


def lambda_handler(event, context):
    if event.get("scheduled_task") == "weekly_coach_summary":
        with app.app_context():
            results = run_weekly_coach_summaries()
        return {
            "statusCode": 200,
            "body": json.dumps(results),
        }
    event = _inject_stage_prefix(event)
    return awsgi.response(
        app,
        event,
        context,
        base64_content_types={
            "image/png",
            "image/jpeg",
            "image/jpg",
            "image/gif",
            "image/webp",
            "image/svg+xml",
            "image/vnd.microsoft.icon",
            "image/x-icon",
            "application/octet-stream",
            "video/webm",
        },
    )
