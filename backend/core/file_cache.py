"""
File caching utilities for formatted output files.
Implements TTL-based caching to avoid re-formatting on every download.
"""

import time
from pathlib import Path

import aiofiles

from logger import get_logger

logger = get_logger(__name__)


class FileCache:
    """Manages cached formatted output files."""

    def __init__(self, cache_dir: str = "outputs", default_ttl: int = 3600):
        """
        Initialize file cache.

        Args:
            cache_dir: Directory to store cached files
            default_ttl: Time-to-live in seconds (default: 1 hour)
        """
        self.cache_dir = Path(cache_dir)
        self.default_ttl = default_ttl
        self.cache_dir.mkdir(exist_ok=True)

    def get_cache_path(self, job_id: str, format_type: str) -> Path:
        """
        Generate consistent cache file path.

        Args:
            job_id: Unique job identifier
            format_type: Output format (txt, toon, md)

        Returns:
            Path to cached file
        """
        # Use job_id prefix for readability
        filename = f"{job_id[:16]}_{format_type}.{format_type}"
        return self.cache_dir / filename

    def get_cached_file(self, job_id: str, format_type: str) -> Path | None:
        """
        Check if cached file exists and is still valid.

        Args:
            job_id: Job identifier
            format_type: Output format

        Returns:
            Path to cached file if valid, None otherwise
        """
        filepath = self.get_cache_path(job_id, format_type)

        if not filepath.exists():
            logger.debug(f"Cache miss: {filepath}")
            return None

        # Check TTL
        file_age = time.time() - filepath.stat().st_mtime
        if file_age > self.default_ttl:
            logger.debug(f"Cache expired: {filepath} (age: {file_age:.0f}s)")
            # Remove expired file
            try:
                filepath.unlink()
            except Exception as e:
                logger.warning(f"Failed to remove expired cache file: {e}")
            return None

        logger.info(f"Cache hit: {filepath} (age: {file_age:.0f}s)")
        return filepath

    async def save_to_cache(
        self,
        job_id: str,
        format_type: str,
        content: str
    ) -> Path:
        """
        Save formatted content to cache.

        Args:
            job_id: Job identifier
            format_type: Output format
            content: Formatted content to save

        Returns:
            Path to saved file
        """
        filepath = self.get_cache_path(job_id, format_type)

        async with aiofiles.open(filepath, "w", encoding="utf-8", errors="replace") as f:
            await f.write(content)

        logger.info(f"Saved to cache: {filepath} ({len(content)} bytes)")
        return filepath

    def cleanup_expired_files(self, ttl_seconds: int | None = None) -> tuple[int, int]:
        """
        Remove cached files older than TTL.

        Args:
            ttl_seconds: Time-to-live override, uses default if None

        Returns:
            Tuple of (files_removed, bytes_freed)
        """
        ttl = ttl_seconds or self.default_ttl
        current_time = time.time()
        files_removed = 0
        bytes_freed = 0

        try:
            for filepath in self.cache_dir.glob("*"):
                if not filepath.is_file():
                    continue

                file_age = current_time - filepath.stat().st_mtime
                if file_age > ttl:
                    try:
                        file_size = filepath.stat().st_size
                        filepath.unlink()
                        files_removed += 1
                        bytes_freed += file_size
                        logger.debug(f"Cleaned up expired file: {filepath} (age: {file_age:.0f}s)")
                    except Exception as e:
                        logger.warning(f"Failed to remove {filepath}: {e}")

        except Exception as e:
            logger.error(f"Cache cleanup failed: {e}")

        if files_removed > 0:
            logger.info(
                f"Cache cleanup complete: removed {files_removed} files, "
                f"freed {bytes_freed / 1024:.2f} KB"
            )

        return files_removed, bytes_freed


# Global cache instance
_cache_instance: FileCache | None = None


def get_file_cache() -> FileCache:
    """Get or create global file cache instance."""
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = FileCache()
    return _cache_instance
