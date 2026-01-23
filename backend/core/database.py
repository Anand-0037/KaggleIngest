
# backend/core/database.py

import asyncpg
import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)

from backend.config import POSTGRES_URL

class Database:
    """
    Singleton database connection pool manager.
    Replaces SQLite with PostgreSQL for production.
    """

    _pool: Optional[asyncpg.Pool] = None

    @classmethod
    async def connect(cls):
        """Initialize connection pool on startup."""
        if cls._pool is None:
            try:
                database_url = POSTGRES_URL
                if not database_url:
                    raise ValueError("POSTGRES_URL environment variable not set")

                cls._pool = await asyncpg.create_pool(
                    database_url,
                    min_size=2, # Minimum connections
                    max_size=10, # Maximum connections
                    command_timeout=60,
                    server_settings={
                        'application_name': 'kaggleingest',
                        'jit': 'off'  # Disable JIT for faster simple queries
                    }
                )

                logger.info("✅ Database connection pool established")

            except Exception as e:
                logger.error(f"❌ Failed to connect to database: {e}")
                raise

    @classmethod
    async def disconnect(cls):
        """Close connection pool on shutdown."""
        if cls._pool:
            await cls._pool.close()
            cls._pool = None
            logger.info("Database connection pool closed")

    @classmethod
    def get_pool(cls) -> asyncpg.Pool:
        """Get the connection pool instance."""
        if cls._pool is None:
            raise RuntimeError("Database not connected. Call Database.connect() first.")
        return cls._pool

# Convenience functions
async def get_db() -> asyncpg.Pool:
    """FastAPI dependency for database access."""
    return Database.get_pool()
