"""
Upstash Redis cache implementation using REST API.
Works with Upstash's serverless Redis offering.
Falls back to standard Redis if Upstash env vars not set.
"""

import hashlib
import json
import os
from collections.abc import Callable
from functools import wraps
from typing import Any

from logger import get_logger

logger = get_logger(__name__)

# Check for Upstash environment variables
UPSTASH_URL = os.getenv("UPSTASH_REDIS_REST_URL")
UPSTASH_TOKEN = os.getenv("UPSTASH_REDIS_REST_TOKEN")

# Lazy imports
_upstash_redis = None
_standard_redis = None


def _get_upstash():
    """Lazy load upstash-redis module."""
    global _upstash_redis
    if _upstash_redis is None:
        try:
            from upstash_redis import Redis as UpstashRedis
            _upstash_redis = UpstashRedis
        except ImportError:
            logger.warning("upstash-redis package not installed.")
            _upstash_redis = False
    return _upstash_redis


def _get_standard_redis():
    """Lazy load standard redis.asyncio module."""
    global _standard_redis
    if _standard_redis is None:
        try:
            import redis.asyncio as redis_async
            _standard_redis = redis_async
        except ImportError:
            logger.warning("redis package not installed.")
            _standard_redis = False
    return _standard_redis


class UpstashCache:
    """
    Cache implementation using Upstash Redis REST API.
    Synchronous but works serverlessly without TCP connections.
    """

    def __init__(self):
        self._client = None
        self._connected = False

    def connect(self):
        """Initialize Upstash connection."""
        if not UPSTASH_URL or not UPSTASH_TOKEN:
            logger.warning("Upstash credentials not set. Cache disabled.")
            return

        UpstashRedis = _get_upstash()
        if not UpstashRedis:
            return

        try:
            self._client = UpstashRedis(
                url=UPSTASH_URL,
                token=UPSTASH_TOKEN
            )
            # Test connection
            self._client.ping()
            self._connected = True
            logger.info("Upstash Redis connected via REST API")
        except Exception as e:
            logger.warning(f"Upstash connection failed: {e}. Cache disabled.")
            self._client = None
            self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None

    def get(self, key: str) -> Any | None:
        """Get cached value."""
        if not self.is_connected:
            return None

        try:
            value = self._client.get(key)
            if value:
                return json.loads(value)
            return None
        except Exception as e:
            logger.error(f"Upstash get error: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 86400):
        """Set cached value with TTL (default 24 hours)."""
        if not self.is_connected:
            return

        try:
            self._client.setex(
                key,
                ttl,
                json.dumps(value, default=str)
            )
        except Exception as e:
            logger.error(f"Upstash set error: {e}")

    def delete(self, key: str):
        """Delete a cached key."""
        if not self.is_connected:
            return

        try:
            self._client.delete(key)
        except Exception as e:
            logger.error(f"Upstash delete error: {e}")

    def close(self):
        """Close connection (no-op for REST API)."""
        self._connected = False
        logger.info("Upstash connection closed")


class StandardRedisCache:
    """
    Standard Redis cache using TCP connection (async).
    Fallback when Upstash is not configured.
    """

    def __init__(self, url: str | None = None):
        self.url = url or os.getenv("REDIS_URL", "redis://localhost:6379")
        self._client = None
        self._connected = False

    async def connect(self):
        """Initialize Redis connection."""
        redis_mod = _get_standard_redis()
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
            logger.info(f"Standard Redis connected: {self.url}")
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
        """Set cached value with TTL."""
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

    async def close(self):
        """Close Redis connection."""
        if self._client:
            await self._client.close()
            self._connected = False
            logger.info("Redis connection closed")


# Global cache instances
_upstash_cache: UpstashCache | None = None
_standard_cache: StandardRedisCache | None = None


def get_upstash_cache() -> UpstashCache:
    """Get or create Upstash cache instance (sync)."""
    global _upstash_cache
    if _upstash_cache is None:
        _upstash_cache = UpstashCache()
        _upstash_cache.connect()
    return _upstash_cache


async def get_redis_cache() -> StandardRedisCache:
    """Get or create standard Redis cache instance (async)."""
    global _standard_cache
    if _standard_cache is None:
        _standard_cache = StandardRedisCache()
        await _standard_cache.connect()
    return _standard_cache


async def close_redis_cache():
    """Close all cache connections."""
    global _upstash_cache, _standard_cache

    if _upstash_cache:
        _upstash_cache.close()
        _upstash_cache = None

    if _standard_cache:
        await _standard_cache.close()
        _standard_cache = None


def use_upstash() -> bool:
    """Check if Upstash should be used (env vars set)."""
    return bool(UPSTASH_URL and UPSTASH_TOKEN)


def cached_upstash(ttl: int = 86400, key_prefix: str = ""):
    """
    Decorator for caching function results in Upstash (sync).

    Args:
        ttl: Time-to-live in seconds (default: 24 hours)
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable):
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_upstash_cache()

            # Generate cache key
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            key_data = f"{key_prefix}:{func.__name__}:{cache_args}:{sorted(kwargs.items())}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # Try cache first
            if cache.is_connected:
                cached_result = cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Upstash cache hit: {cache_key[:16]}...")
                    return cached_result

            # Cache miss - execute function
            result = func(*args, **kwargs)

            # Store in cache
            if cache.is_connected and result is not None:
                cache.set(cache_key, result, ttl)
                logger.debug(f"Upstash cache set: {cache_key[:16]}...")

            return result
        return wrapper
    return decorator


def cached(ttl: int = 86400, key_prefix: str = ""):
    """
    Decorator for caching async function results.
    Uses Upstash if configured, otherwise standard Redis.

    Args:
        ttl: Time-to-live in seconds (default: 24 hours)
        key_prefix: Prefix for cache keys
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            key_data = f"{key_prefix}:{func.__name__}:{cache_args}:{sorted(kwargs.items())}"
            cache_key = hashlib.md5(key_data.encode()).hexdigest()

            # Try Upstash first if configured
            if use_upstash():
                upstash = get_upstash_cache()
                if upstash.is_connected:
                    cached_result = upstash.get(cache_key)
                    if cached_result is not None:
                        logger.debug(f"Upstash cache hit: {cache_key[:16]}...")
                        return cached_result

                    result = await func(*args, **kwargs)

                    if result is not None:
                        upstash.set(cache_key, result, ttl)
                        logger.debug(f"Upstash cache set: {cache_key[:16]}...")

                    return result

            # Fallback to standard Redis
            cache = await get_redis_cache()

            if cache.is_connected:
                cached_result = await cache.get(cache_key)
                if cached_result is not None:
                    logger.debug(f"Redis cache hit: {cache_key[:16]}...")
                    return cached_result

            result = await func(*args, **kwargs)

            if cache.is_connected and result is not None:
                await cache.set(cache_key, result, ttl)
                logger.debug(f"Redis cache set: {cache_key[:16]}...")

            return result
        return wrapper
    return decorator
