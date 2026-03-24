import os

import boto3
from botocore.exceptions import ClientError


def send_email(to_email: str, subject: str, body_text: str, body_html: str | None = None) -> str:
    aws_region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION", "us-east-2")
    from_email = os.getenv("SES_FROM_EMAIL")

    if not from_email:
        raise ValueError("SES_FROM_EMAIL is not set")

    ses = boto3.client("ses", region_name=aws_region)

    message = {
        "Subject": {"Data": subject, "Charset": "UTF-8"},
        "Body": {"Text": {"Data": body_text, "Charset": "UTF-8"}},
    }
    if body_html:
        message["Body"]["Html"] = {"Data": body_html, "Charset": "UTF-8"}

    try:
        resp = ses.send_email(
            Source=from_email,
            Destination={"ToAddresses": [to_email]},
            Message=message,
        )
        return resp["MessageId"]
    except ClientError as e:
        err = e.response["Error"]
        raise RuntimeError(f"SES send failed: {err.get('Code')}: {err.get('Message')}") from e
