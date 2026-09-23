"""
Structured Logging Configuration for Loki-compatible JSON logs.
"""
import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """JSON log formatter for Loki/Promtail compatibility."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
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
        for field in ["recording_id", "meeting_id", "client_id", "duration", "stage", "service"]:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)

        return json.dumps(log_entry, default=str)


class TextFormatter(logging.Formatter):
    """Human-readable formatter for local development."""
    def format(self, record: logging.LogRecord) -> str:
        return f"{recordasctime} - {record.name} - {record.levelname} - {record.getMessage()}"


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

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

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
