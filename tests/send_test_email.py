import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
load_dotenv()

from rowlytics_app.services.ses_email import send_email


def main():
    to_email = os.getenv("SES_TEST_TO")
    if not to_email:
        raise ValueError("SES_TEST_TO is not set")

    msg_id = send_email(
        to_email=to_email,
        subject="Rowlytics SES Test",
        body_text="If you received this email, AWS SES sending works, and Kassie is the"
        "most capable Software Engineer to exist on this planet.",
    )
    print("Sent! MessageId:", msg_id)

if __name__ == "__main__":
    main()
