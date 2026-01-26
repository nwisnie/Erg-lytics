"""Logging configuration for Rowlytics."""

from __future__ import annotations

import json
import logging
import os
import sys
from logging import LogRecord


class JsonFormatter(logging.Formatter):
    """Format logs as JSON for better parsing in CloudWatch."""

    def format(self, record: LogRecord) -> str:
        """Format the log record as JSON."""
        log_data = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        if record.exc_text:
            log_data["exc_text"] = record.exc_text

        return json.dumps(log_data)


def setup_logging(app=None):
    """Configure logging for the Rowlytics application."""
    env = os.getenv("ROWLYTICS_ENV", "development")
    log_level = os.getenv("ROWLYTICS_LOG_LEVEL", "INFO")

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level.upper()))

    # Clear existing handlers
    root_logger.handlers.clear()

    # Console handler with JSON formatter for production, text for development
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))

    if env == "production":
        formatter = JsonFormatter()
    else:
        format_parts = (
            "%(asctime)s - %(name)s - %(levelname)s - ",
            "[%(module)s:%(funcName)s:%(lineno)d] - %(message)s",
        )
        formatter = logging.Formatter("".join(format_parts))

    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Set boto3 logging
    boto3_level = logging.WARNING if env == "production" else logging.DEBUG
    logging.getLogger("boto3").setLevel(boto3_level)
    logging.getLogger("botocore").setLevel(boto3_level)
    logging.getLogger("urllib3").setLevel(boto3_level)

    # Configure Flask app logger if available
    if app:
        app.logger.setLevel(getattr(logging, log_level.upper()))
        app.logger.propagate = True

    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)
