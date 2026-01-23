import asyncio
import asyncpg
import os
import sys

async def test():
    url = os.getenv("POSTGRES_URL")
    if not url:
        print("POSTGRES_URL not set")
        return

    try:
        conn = await asyncpg.connect(url)
        print("✅ Connected to DB")

        # Check tables
        rows = await conn.fetch("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';")
        tables = [r['table_name'] for r in rows]
        print(f"Tables: {tables}")

        if 'competition_cache' in tables:
            print("✅ competition_cache exists")
            row = await conn.fetchrow("SELECT COUNT(*) FROM competition_cache")
            print(f"competition_cache count: {row['count']}")
        else:
            print("❌ competition_cache MISSING")

        await conn.close()
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    asyncio.run(test())
