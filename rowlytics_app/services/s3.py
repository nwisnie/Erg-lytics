"""S3 helpers for Rowlytics."""

from __future__ import annotations

import os

try:
    import boto3
except ImportError:  # pragma: no cover - boto3 only needed when AWS is used
    boto3 = None

UPLOAD_BUCKET_NAME = os.getenv("ROWLYTICS_UPLOAD_BUCKET", "rowlyticsuploads")


def get_s3_client():
    if boto3 is None:
        raise RuntimeError("boto3 is required for S3 access")
    if not UPLOAD_BUCKET_NAME:
        raise RuntimeError("ROWLYTICS_UPLOAD_BUCKET is not configured")
    return boto3.client("s3")
