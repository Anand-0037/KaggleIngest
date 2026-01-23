"""
PostgreSQL-backed content cache.
Stores large text content (notebooks, source files) to avoid re-fetching.
"""
import logging
import re
from typing import Optional
from backend.db.session import DatabaseSession

logger = logging.getLogger(__name__)

VALID_CACHE_KEY = re.compile(r'^[a-zA-Z0-9_\-:/.]+$')  # Allow dots for file extensions

class PgCache:
    def __init__(self):
        self.db = DatabaseSession.get_instance()

    async def connect(self):
        """No-op: managed by DatabaseSession."""
        pass

    async def close(self):
        """No-op: managed by DatabaseSession."""
        pass



    @property
    def is_connected(self) -> bool:
        """Check if database pool is connected.

        Handles exceptions gracefully to avoid crashes.
        """
        try:
            pool = self.db.get_pool()
            return pool is not None and not pool._closed
        except (RuntimeError, AttributeError):
            return False

    async def get(self, key: str) -> Optional[str]:
        """Retrieve content from cache."""
        try:
            pool = await self.db.get_pool()
            if not pool:
                return None
            async with pool.acquire() as conn:
                row = await conn.fetchrow("""
                    SELECT cache_value FROM cache_entries WHERE cache_key = $1 AND expires_at > NOW()
                """, key)
                return row['cache_value'] if row else None
        except Exception as e:
            logger.warning(f"Cache get error for {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl: int = 86400):
        """Save content to cache."""
        try:
            pool = await self.db.get_pool()
            if not pool:
                return
            async with pool.acquire() as conn:
                await conn.execute("""
                    INSERT INTO cache_entries (cache_key, cache_value, cache_type, expires_at)
                    VALUES ($1, $2, 'generic', NOW() + make_interval(secs => $3))
                    ON CONFLICT (cache_key)
                    DO UPDATE SET
                        cache_value = EXCLUDED.cache_value,
                        expires_at = NOW() + make_interval(secs => $3)
                """, key, value, ttl)
        except Exception as e:
            logger.error(f"Cache set error for {key}: {e}")

    async def delete(self, key: str) -> bool:
        """Delete entry from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if entry was deleted, False otherwise
        """
        try:
            pool = await self.db.get_pool()
            if not pool:
                return False
            async with pool.acquire() as conn:
                result = await conn.execute("""
                    DELETE FROM cache_entries WHERE cache_key = $1
                """, key)
                return result != "DELETE 0"
        except Exception as e:
            logger.warning(f"Cache delete error for {key}: {e}")
            return False

_pg_cache = None

async def get_pg_cache() -> PgCache:
    """Get or create PgCache instance."""
    global _pg_cache
    if _pg_cache is None:
        _pg_cache = PgCache()
        # Ensure the shared pool is connected
        await _pg_cache.db.connect()
    return _pg_cache

