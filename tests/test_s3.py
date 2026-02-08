from __future__ import annotations

from unittest.mock import MagicMock

import pytest

import rowlytics_app.services.s3 as s3


def test_get_s3_client_requires_boto3(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(s3, "boto3", None)
    with pytest.raises(RuntimeError):
        s3.get_s3_client()


def test_get_s3_client_requires_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(s3, "UPLOAD_BUCKET_NAME", "")
    with pytest.raises(RuntimeError):
        s3.get_s3_client()


def test_get_s3_client_returns_boto_client(monkeypatch: pytest.MonkeyPatch) -> None:
    boto = MagicMock()
    client = MagicMock()
    boto.client.return_value = client
    monkeypatch.setattr(s3, "boto3", boto)
    monkeypatch.setattr(s3, "UPLOAD_BUCKET_NAME", "rowlyticsuploads")

    result = s3.get_s3_client()

    assert result is client
    boto.client.assert_called_once_with("s3")
