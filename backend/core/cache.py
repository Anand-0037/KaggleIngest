import hashlib
import json
import time
from pathlib import Path
from typing import Any

from filelock import FileLock

from logger import get_logger

logger = get_logger(__name__)

CACHE_DIR = Path.home() / ".cache" / "kaggleingest"
CACHE_EXPIRY_HOURS = 24


def get_cache_path(key: str) -> Path:
    """Generate a file path for a cache key."""
    if not CACHE_DIR.exists():
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # Hash the key to create a safe filename
    safe_key = hashlib.md5(key.encode()).hexdigest()
    return CACHE_DIR / f"{safe_key}.json"


def get_cached_data(key: str) -> Any | None:
    """Retrieve data from cache if it exists and hasn't expired."""
    cache_path = get_cache_path(key)
    lock_path = cache_path.with_suffix(".lock")

    if not cache_path.exists():
        return None

    try:
        with FileLock(lock_path, timeout=5):
            with open(cache_path, encoding="utf-8") as f:
                cached = json.load(f)

            # Check expiry
            age = time.time() - cached.get("timestamp", 0)
            if age < CACHE_EXPIRY_HOURS * 3600:
                logger.debug(f"Cache hit for key: {key}")
                return cached.get("data")

            logger.debug(f"Cache expired for key: {key}")
            return None

    except Exception as e:
        logger.warning(f"Failed to read cache: {e}")
        return None


def set_cached_data(key: str, data: Any) -> None:
    """Save data to cache."""
    cache_path = get_cache_path(key)
    lock_path = cache_path.with_suffix(".lock")

    try:
        with FileLock(lock_path, timeout=5):
            cache_data = {
                "timestamp": time.time(),
                "data": data
            }
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f)
            logger.debug(f"Cached data for key: {key}")

    except Exception as e:
        logger.warning(f"Failed to write cache: {e}")
