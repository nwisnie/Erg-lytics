from flask import render_template

from rowlytics_app.services.ses_email import send_email


def send_mock_auto_email(to_email: str, name: str | None = None) -> str:
    subject = "Rowlytics Statistics Update"

    app_url = "https://ra7jdv1jj1.execute-api.us-east-2.amazonaws.com/Prod"

    body_html = render_template(
        "emails/mock_auto_email.html",

        # user info
        name=name or "Rower",
        app_url=app_url,

        # PERSONAL STATS (mock values)
        personal_total_workouts="12",
        personal_total_distance="52,000 m",
        personal_avg_split="2:03 / 500m",
        personal_avg_stroke_rate="28 spm",
        personal_recent_workout="2k Erg Test",

        # TEAM STATS (mock values)
        team_name="Varsity Women's Rowing",
        team_total_workouts="148",
        team_total_distance="602,000 m",
        team_avg_split="2:01 / 500m",
        team_avg_stroke_rate="29 spm",
    )

    body_text = (
        f"Hello {name or 'Rower'},\n\n"
        "Here is your latest Rowlytics statistics update.\n\n"

        "PERSONAL STATISTICS\n"
        "- Total Workouts: 12\n"
        "- Total Distance: 52,000 m\n"
        "- Average Split: 2:03 / 500m\n"
        "- Average Stroke Rate: 28 spm\n"
        "- Most Recent Workout: 2k Erg Test\n\n"

        "TEAM STATISTICS\n"
        "- Team Name: Varsity Women's Rowing\n"
        "- Total Team Workouts: 148\n"
        "- Total Team Distance: 602,000 m\n"
        "- Average Team Split: 2:01 / 500m\n"
        "- Average Team Stroke Rate: 29 spm\n\n"

        f"Open Rowlytics: {app_url}\n"
    )

    return send_email(
        to_email=to_email,
        subject=subject,
        body_text=body_text,
        body_html=body_html,
    )
