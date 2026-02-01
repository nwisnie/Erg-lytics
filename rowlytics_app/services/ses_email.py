import os
import boto3
from botocore.exceptions import ClientError

AWS_REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-2")
FROM_EMAIL = os.getenv("SES_FROM_EMAIL")

def send_email(to_email: str, subject: str, body_text: str, body_html: str | None = None) -> str:
    if not FROM_EMAIL:
        raise ValueError("SES_FROM_EMAIL is not set")

    ses = boto3.client("ses", region_name=AWS_REGION)

    message = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
    }
    if body_html:
        message["Body"]["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    try:
        resp = ses.send_email(
            Source=FROM_EMAIL,
            Destination={"ToAddresses": [to_email]},
            Message=message,
        )
        return resp["MessageId"]
    except ClientError as e:
        err = e.response["Error"]
        raise RuntimeError(f"SES send failed: {err.get('Code')}: {err.get('Message')}") from e
