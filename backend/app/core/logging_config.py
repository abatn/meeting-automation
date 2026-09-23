"""
Structured Logging Configuration for Loki-compatible JSON logs.
"""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for Loki/Promtail compatibility."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created, tz=timezone.utc
            ).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        # Add extra fields (pipeline context, timing, etc.)
        if hasattr(record, "extra_data") and record.extra_data:
            log_entry["extra"] = record.extra_data

        # Add common pipeline fields if present
        for field in [
            "recording_id",
            "meeting_id",
            "client_id",
            "duration",
            "stage",
            "service",
        ]:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for local development."""

    def format(self, record: logging.LogRecord) -> str:
        ts = self.formatTime(record, "%Y-%m-%d %H:%M:%S,%03d")
        return f"{ts} - {record.name} - {record.levelname} - {record.getMessage()}"


def _real_stream():
    """Bind to the process's original std stream.

    Celery workers set worker_redirect_stdouts=True and replace sys.stdout
    with LoggingProxy(celery.redirected). StreamHandler(sys.stdout) then
    feeds back into the logging system and root records are dropped by
    LoggingProxy's recursion guard. Use __stdout__/__stderr__ (never proxied)
    so root/service TIMING logs reach kubectl logs.
    """
    stream = getattr(sys, "__stdout__", None) or sys.stdout
    return stream


def setup_logging(json_format: bool = True) -> None:
    """
    Configure structured logging for the application.

    Args:
        json_format: If True, use JSON format (for production/Loki).
                     If False, use human-readable format (for local dev).
    """
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create handler on the real process stream (not Celery LoggingProxy)
    handler = logging.StreamHandler(_real_stream())

    if json_format:
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(TextFormatter())

    root_logger.addHandler(handler)

    # Reduce noise from external libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
