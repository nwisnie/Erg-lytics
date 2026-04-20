"""Weekly coach summary email service."""

from __future__ import annotations

import os

from rowlytics_app.services.mock_email import send_mock_auto_email


def run_weekly_coach_summaries() -> dict:
    """
    Temporary mock implementation for weekly coach summary emails.

    Later this should:
    - look up coach users
    - gather team summary data
    - render a reusable email template
    - send one email per coach/team
    """

    test_to = os.getenv("SES_TEST_TO")
    if not test_to:
        raise RuntimeError("SES_TEST_TO is not configured")

    send_mock_auto_email(
        to_email=test_to,
        name="Beautiful Erglytics Devs",
    )

    return {
        "status": "success",
        "emails_attempted": 1,
        "emails_sent": 1,
        "errors": [],
        "recipient": test_to,
    }