import logging
import sys
from logging.handlers import RotatingFileHandler

from config import LOG_LEVEL

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

    # RotatingFileHandler: 5MB max, keep 3 backups
    file_handler = RotatingFileHandler(
        "kaggle_ingest.log",
        maxBytes=5 * 1024 * 1024,  # 5MB
        backupCount=3,
        encoding="utf-8"
    )

    logging.basicConfig(
        level=log_level,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            file_handler,
        ],
    )

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a module."""
    return logging.getLogger(name)
