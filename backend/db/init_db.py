import asyncpg
from pathlib import Path
from backend.config import POSTGRES_URL
from backend.logger import get_logger

logger = get_logger(__name__)

async def init_db():
    """Initialize database schema from migrations folder."""
    try:
        conn = await asyncpg.connect(POSTGRES_URL)
        logger.info(" Connected to DB for initialization")

        # Use migrations folder
        migrations_dir = Path(__file__).parent.parent / "migrations"
        if not migrations_dir.exists():
            logger.error(f" Migrations directory not found: {migrations_dir}")
            return

        # Get all .sql files sorted by name
        migration_files = sorted(migrations_dir.glob("*.sql"))

        if not migration_files:
            logger.warning("No migration files found.")
            return

        for migration_file in migration_files:
            logger.info(f"Applying migration: {migration_file.name}")
            with open(migration_file, 'r') as f:
                schema_sql = f.read()

            async with conn.transaction():
                await conn.execute(schema_sql)

        logger.info(" Database schema initialized successfully")
        await conn.close()
    except Exception as e:
        logger.error(f" Database initialization failed: {e}")
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(init_db())
