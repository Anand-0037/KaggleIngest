"""
Redis-based distributed cache for production deployments.
Falls back gracefully if Redis is unavailable.
"""

import hashlib
import json
import os
from collections.abc import Callable
from functools import wraps
from typing import Any

from logger import get_logger

logger = get_logger(__name__)

# Lazy import for redis
_redis = None


def _get_redis():
    """Lazy load redis module."""
    global _redis
    if _redis is None:
        try:
            import redis.asyncio as redis_async
            _redis = redis_async
        except ImportError:
            logger.warning("redis package not installed. Redis caching disabled.")
            _redis = False
    return _redis


class RedisCache:
    """
    Distributed cache using Redis with async support.
    Falls back gracefully if Redis is unavailable.
    """

    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._client = None
        self._connected = False

    async def connect(self):
        """Initialize Redis connection."""
        redis_mod = _get_redis()
        if not redis_mod:
            logger.warning("Redis module not available. Cache disabled.")
            return

        try:
            self._client = redis_mod.from_url(
                self.url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            await self._client.ping()
            self._connected = True
            logger.info(f"Redis connected: {self.url}")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Cache disabled.")
            self._client = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    async def get(self, key: str) -> Any | None:
        """Get cached value."""
        if not self.is_connected:
            return None

        try:
            value = await self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Redis get error: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int = 86400):
        """Set cached value with TTL (default 24 hours)."""
        if not self.is_connected:
            return

        try:
            await self._client.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"Redis set error: {e}")

    async def delete(self, key: str):
        """Delete a cached key."""
        if not self.is_connected:
            return

        try:
            await self._client.delete(key)
        except Exception as e:
            logger.error(f"Redis delete error: {e}")

    async def invalidate_pattern(self, pattern: str):
        """Invalidate keys matching pattern."""
        if not self.is_connected:
            return

        try:
            async for key in self._client.scan_iter(match=pattern):
                await self._client.delete(key)
        except Exception as e:
            logger.error(f"Redis invalidate error: {e}")

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Redis connection closed")


# Global cache instance
_cache: RedisCache | None = None


async def get_redis_cache() -> RedisCache:
    """Get or create Redis cache instance."""
    global _cache
    if _cache is None:
        _cache = RedisCache()
        await _cache.connect()
    return _cache


async def close_redis_cache():
    """Close Redis cache."""
    global _cache
    if _cache:
        await _cache.close()
        _cache = None


def cached(ttl: int = 86400, key_prefix: str = ""):
    """
    Decorator for caching async function results in Redis.
    Falls back to no caching if Redis is unavailable.
    
    Args:
        ttl: Time-to-live in seconds (default: 24 hours)
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cache = await get_redis_cache()

            # Generate cache key from function name and arguments
            # Skip 'self' if it's an instance method
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            key_data = f"{key_prefix}:{func.__name__}:{cache_args}:{sorted(kwargs.items())}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # Try cache first
            if cache.is_connected:
                cached_result = await cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Cache hit: {cache_key[:16]}...")
                    return cached_result

            # Cache miss - execute function
            result = await func(*args, **kwargs)

            # Store in cache
            if cache.is_connected and result is not None:
                await cache.set(cache_key, result, ttl)
                logger.debug(f"Cache set: {cache_key[:16]}...")

            return result
        return wrapper
    return decorator
