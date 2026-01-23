
# backend/core/logging_config.py

import logging
import sys
import json
from datetime import datetime, timezone

class JSONFormatter(logging.Formatter):
    """
    Structured JSON logging for production.
    Makes logs easily parsable by log aggregators.
    """

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Add extra fields (user_id, request_id, etc.)
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "request_id"):
            log_data["request_id"] = record.request_id

        return json.dumps(log_data)

def setup_logging():
    """
    Configure application-wide logging.
    Uses JSON format in production, human-readable in development.
    """
    import os

    environment = os.getenv("ENVIRONMENT", "development")

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Console handler
    handler = logging.StreamHandler(sys.stdout)

    if environment == "production":
        handler.setFormatter(JSONFormatter())
    else:
        # Human-readable format for development
        formatter = logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        handler.setFormatter(formatter)

    root_logger.addHandler(handler)

    # Reduce noise from third-party libraries
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
