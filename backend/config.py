# Configuration and Environment Settings
import os

# API Configuration
API_TITLE = "KaggleIngest API"
API_VERSION = "5.0.0"  # Single source of truth for version

# Supported output formats
SUPPORTED_OUTPUT_FORMATS = ["txt", "toon"]
DEFAULT_OUTPUT_FORMAT = "toon"


# CORS Settings - load from environment or use secure defaults
def _parse_cors_origins(origins_str: str) -> list[str]:
    """Parse CORS origins from a comma-separated string.

    Args:
        origins_str: Comma-separated list of allowed origins

    Returns:
        List of valid origins with empty strings and duplicates removed
    """
    if not origins_str:
        return []

    # Split, strip whitespace, and remove empty strings
    origins = [o.strip() for o in origins_str.split(",") if o.strip()]

    # Remove duplicates while preserving order (Python 3.7+ dict preserves insertion order)
    return list(dict.fromkeys(origins))


# Default CORS origins for development
DEFAULT_CORS_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173", # Vite default port
    "http://127.0.0.1:5173",
    "https://studio.firebase.google.com/studio-90517064300",
]

# Get CORS origins from environment or use defaults
_cors_origins_str = os.getenv("CORS_ORIGINS")
if not _cors_origins_str and os.getenv("ENV") == "production":
    # In production, we should NOT have loose defaults
    CORS_ORIGINS = []
    print("WARNING: ENV=production but CORS_ORIGINS is not set. API will be inaccessible from browsers.")
else:
    CORS_ORIGINS = (
        _parse_cors_origins(_cors_origins_str)
        if _cors_origins_str is not None
        else DEFAULT_CORS_ORIGINS
    )

# Security headers configuration
SECURE_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}

# Rate limiting (requests per minute)
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "20"))  # Default: 20 requests per minute

# Notebook limits
MIN_NOTEBOOKS = 1
MAX_NOTEBOOKS = 50
DEFAULT_NOTEBOOKS = 10

# Dataset schema limits
try:
    MAX_CSV_FILES_TO_PARSE = int(os.getenv("MAX_CSV_FILES", "3"))
except (ValueError, TypeError):
    MAX_CSV_FILES_TO_PARSE = 3

MAX_SAMPLE_ROWS = 10

# Timeout settings (seconds)
try:
    SUBPROCESS_TIMEOUT = int(os.getenv("SUBPROCESS_TIMEOUT", "300"))
except (ValueError, TypeError):
    SUBPROCESS_TIMEOUT = 300  # 5 minutes

# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Output file settings
DEFAULT_OUTPUT_FILE = "context_output.txt"

# Job Queue Configuration (Redis)
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
JOB_TIMEOUT = 600  # 10 minutes for job execution
