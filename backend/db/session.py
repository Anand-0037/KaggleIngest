import asyncio
import asyncpg
import logging
from typing import Optional
from backend.config import POSTGRES_URL

logger = logging.getLogger(__name__)

class DatabaseSession:
    _instance: Optional['DatabaseSession'] = None
    _pool: Optional[asyncpg.Pool] = None
    _lock: asyncio.Lock = None  # Will be initialized per-instance

    def __init__(self):
        # Create lock in init to avoid issues with module-level async lock
        if DatabaseSession._lock is None:
            DatabaseSession._lock = asyncio.Lock()

    @classmethod
    def get_instance(cls) -> 'DatabaseSession':
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    async def get_pool(self) -> asyncpg.Pool:
        """Get the connection pool, creating it if necessary."""
        if self._pool is None:
            await self.connect()
        return self._pool

    async def connect(self):
        """Initialize the connection pool if not already initialized.

        Thread-safe: Uses asyncio.Lock to prevent race conditions.
        """
        async with self._lock:
            if self._pool is None:
                try:
                    # Reasonable defaults for Neon free tier (10 connections max)
                    self._pool = await asyncpg.create_pool(
                        POSTGRES_URL,
                        min_size=2,
                        max_size=10,
                        max_queries=50000,
                        max_inactive_connection_lifetime=300,
                        # SSL handled by connection string
                        server_settings={'application_name': 'kaggleingest'}
                    )
                    logger.info("✅ Database pool created")
                except Exception as e:
                    logger.error(f"❌ Failed to create DB pool: {e}")
                    raise

    async def close(self):
        """Close the connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            logger.info("🛑 Database pool closed")

async def get_db_pool() -> asyncpg.Pool:
    """Dependency helper to get the pool."""
    db = DatabaseSession.get_instance()
    return await db.get_pool()
