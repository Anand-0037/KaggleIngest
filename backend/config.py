import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file in the same directory as this file
load_dotenv(dotenv_path=Path(__file__).parent / ".env")

# API Configuration
API_TITLE = "KaggleIngest API"
API_VERSION = "5.0.0"  # Single source of truth for version

# Supported output formats
# Output format (TOON only for token efficiency)
DEFAULT_OUTPUT_FORMAT = "toon"

# Popular competitions for warm caching
POPULAR_COMPETITIONS = [
    "titanic",
    "house-prices-advanced-regression-techniques",
    "digit-recognizer",
    "store-sales-time-series-forecasting",
    "nlp-getting-started"
]


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

# Concurrency limits
LIMIT_CONCURRENT_DOWNLOADS = int(os.getenv("LIMIT_CONCURRENT_DOWNLOADS", "5"))

# Notebook limits
MIN_NOTEBOOKS = 1
MAX_NOTEBOOKS = 10  # Hard limit for caching efficiency
DEFAULT_NOTEBOOKS = 3

# Dataset schema limits
try:
    MAX_CSV_FILES_TO_PARSE = int(os.getenv("MAX_CSV_FILES", "3"))
except (ValueError, TypeError):
    MAX_CSV_FILES_TO_PARSE = 3

MAX_SAMPLE_ROWS = 10


# Logging configuration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# Kaggle Credentials
KAGGLE_USERNAME = os.getenv("KAGGLE_USERNAME")
KAGGLE_KEY = os.getenv("KAGGLE_KEY")

# Output file settings
DEFAULT_OUTPUT_FILE = "context_output.txt"

# Strict Environment Validation
missing_keys = []
if not KAGGLE_USERNAME: missing_keys.append("KAGGLE_USERNAME")
if not KAGGLE_KEY: missing_keys.append("KAGGLE_KEY")

if missing_keys and os.getenv("ENV") == "production":
    raise RuntimeError(f"❌ CRITICAL: Missing required environment variables: {', '.join(missing_keys)}")
elif missing_keys:
    print(f"⚠️  WARNING: Missing credentials {missing_keys}. Kaggle API calls will fail.")


# PostgreSQL Connection
# SECURITY: Never hardcode production credentials
POSTGRES_URL = os.getenv('POSTGRES_URL') or os.getenv('DATABASE_URL')

if not POSTGRES_URL:
    if os.getenv("ENV") == "production":
        raise RuntimeError("❌ CRITICAL: POSTGRES_URL must be set in production")
    else:
        # Development fallback - local PostgreSQL or in-memory mode
        POSTGRES_URL = os.getenv(
            'DATABASE_URL_DEV',
            'postgresql://postgres:postgres@localhost:5432/kaggleingest_dev'
        )
        print("⚠️ WARNING: Using development database URL. Set POSTGRES_URL for production.")

# Ensure asyncpg compatibility (remove ?channel_binding=require)
if POSTGRES_URL:
    POSTGRES_URL = POSTGRES_URL.replace('?channel_binding=require', '?').replace('&channel_binding=require', '')

if POSTGRES_URL and 'sslmode' not in POSTGRES_URL and 'localhost' not in POSTGRES_URL:
     POSTGRES_URL += '?sslmode=require'

DATABASE_URL = POSTGRES_URL  # Alias for backward compatibility

# Resource-specific TTLs (Seconds) - 30 days for monthly refresh
TTL_NOTEBOOK = 259200      # 3 days (notebooks can change more frequently)
TTL_COMPETITION = 2592000  # 30 days
TTL_DATASET = 2592000      # 30 days

# Data Quality: Default Ignore Patterns
# These match standard .gitignore syntax via pathspec
DEFAULT_IGNORE_PATTERNS = [
    # System & Environment
    "__pycache__/", "*.pyc", "*.pyo", "*.pyd",
    ".git/", ".svn/", ".hg/",
    ".DS_Store", "Thumbs.db",
    "node_modules/", "venv/", ".venv/", "env/",

    # Locfiles (context noise)
    "package-lock.json", "yarn.lock", "uv.lock", "poetry.lock", "Pipfile.lock",

    # Images & Media
    "*.png", "*.jpg", "*.jpeg", "*.gif", "*.webp", "*.ico", "*.svg",
    "*.mp4", "*.mov", "*.avi", "*.mp3", "*.wav",

    # Archives & Binaries
    "*.zip", "*.tar", "*.gz", "*.rar", "*.7z", "*.whl",
    "*.exe", "*.dll", "*.so", "*.dylib", "*.bin",

    # Large Data Files (unless explicitly requested, usually noise for code context)
    "*.csv", "*.tsv", "*.jsonl", "*.parquet", "*.pkl", "*.h5", "*.npy", "*.pt", "*.pth", "*.onnx",
    "*.db", "*.sqlite", "*.sqlite3",

    # Documents
    "*.pdf", "*.doc", "*.docx", "*.xls", "*.xlsx", "*.ppt", "*.pptx",
]

# Observability
SENTRY_DSN = os.getenv("SENTRY_DSN")
SENTRY_ENABLED = SENTRY_DSN is not None
PROMETHEUS_ENABLED = os.getenv("PROMETHEUS_ENABLED", "True").lower() == "true"
PROMETHEUS_METRICS_PATH = "/metrics"

# Storage Settings
STORAGE_STRATEGY = os.getenv("STORAGE_STRATEGY", "local").lower() # "local" or "s3"
S3_BUCKET = os.getenv("S3_BUCKET", "kaggleingest-results")
S3_ENDPOINT = os.getenv("S3_ENDPOINT") # For MinIO compatibility
S3_ACCESS_KEY = os.getenv("S3_ACCESS_KEY")
S3_SECRET_KEY = os.getenv("S3_SECRET_KEY")
S3_REGION = os.getenv("S3_REGION", "us-east-1")
