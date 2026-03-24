from __future__ import annotations

import boto3

cloudwatch = boto3.client("cloudwatch", region_name="us-east-2")


def publish_login_latency(latency_ms: float, environment: str) -> None:
    cloudwatch.put_metric_data(
        Namespace="Erg-lytics/Auth",
        MetricData=[
            {
                "MetricName": "LoginLatencyMs",
                "Dimensions": [
                    {"Name": "Environment", "Value": environment},
                ],
                "Unit": "Milliseconds",
                "Value": latency_ms,
            }
        ],
    )
