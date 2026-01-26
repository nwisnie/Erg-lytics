"""S3 helpers for Rowlytics."""

from __future__ import annotations

import logging
import os

try:
    import boto3
except ImportError:  # pragma: no cover - boto3 only needed when AWS is used
    boto3 = None

logger = logging.getLogger(__name__)

UPLOAD_BUCKET_NAME = os.getenv("ROWLYTICS_UPLOAD_BUCKET", "rowlyticsuploads")


def get_s3_client():
    if boto3 is None:
        logger.error("boto3 is not installed")
        raise RuntimeError("boto3 is required for S3 access")
    if not UPLOAD_BUCKET_NAME:
        logger.error("ROWLYTICS_UPLOAD_BUCKET environment variable is not configured")
        raise RuntimeError("ROWLYTICS_UPLOAD_BUCKET is not configured")
    logger.debug(f"Creating S3 client for bucket: {UPLOAD_BUCKET_NAME}")
    return boto3.client("s3")
