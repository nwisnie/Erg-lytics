import os
import boto3


def _ses_client():
    region = os.getenv("SES_REGION")
    if not region:
        raise RuntimeError("SES_REGION is not set")
    return boto3.client("ses", region_name=region)


def send_email(*, to_address: str, subject: str, body_text: str) -> None:
    from_email = os.getenv("SES_FROM_EMAIL")
    if not from_email:
        raise RuntimeError("SES_FROM_EMAIL is not set")

    ses = _ses_client()
    ses.send_email(
        Source=from_email,
        Destination={"ToAddresses": [to_address]},
        Message={
            "Subject": {"Data": subject},
            "Body": {"Text": {"Data": body_text}},
        },
    )
