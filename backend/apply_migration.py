import asyncio
import os
from backend.core.database import Database

async def apply_migration():
    # Ensure DATABASE_URL is set - it will be pulled from config.py which uses POSTGRES_URL
    print("Applying migration...")

    try:
        await Database.connect()
        pool = Database.get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                ALTER TABLE competition_cache
                ADD COLUMN IF NOT EXISTS notebooks JSONB;

                COMMENT ON COLUMN competition_cache.notebooks IS 'Raw processed notebook data as an array of JSON objects';
            """)
        print("✅ Migration applied successfully: Added 'notebooks' column to 'competition_cache'")
    except Exception as e:
        print(f"❌ Migration failed: {e}")
    finally:
        await Database.disconnect()

if __name__ == "__main__":
    asyncio.run(apply_migration())
