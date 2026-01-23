import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

import logging
import sys
from backend.config import LOG_LEVEL

# Track if logging has been configured to avoid duplicate handlers
_logging_configured = False


# Configure logging
def setup_logging():
    """Configure application logging with proper formatting and rotation."""
    global _logging_configured

    # Avoid setting up logging multiple times
    if _logging_configured:
        return

    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Validate LOG_LEVEL
    try:
        log_level = getattr(logging, LOG_LEVEL.upper())
    except AttributeError:
        # Fallback to INFO if invalid level
        log_level = logging.INFO
        print(f"Warning: Invalid LOG_LEVEL '{LOG_LEVEL}', using INFO", file=sys.stderr)

    # Configurable log file path - handles containers and readonly filesystems
    log_file = os.getenv("LOG_FILE", "kaggle_ingest.log")
    log_dir = Path(log_file).parent

    handlers = [logging.StreamHandler(sys.stdout)]

    try:
        # Create log directory if it doesn't exist
        if log_dir and str(log_dir) != ".":
            log_dir.mkdir(parents=True, exist_ok=True)

        # RotatingFileHandler: 5MB max, keep 3 backups
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding="utf-8"
        )
        handlers.append(file_handler)
    except (OSError, PermissionError) as e:
        # Log to stderr if file logging fails (e.g., readonly filesystem)
        print(f"Warning: Could not create log file '{log_file}': {e}", file=sys.stderr)

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=handlers,
    )

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)

