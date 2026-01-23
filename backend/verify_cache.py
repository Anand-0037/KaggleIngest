import asyncio
import json
from backend.core.database import Database

async def check_db_content(slug: str):
    await Database.connect()
    pool = Database.get_pool()
    row = await pool.fetchrow("SELECT slug, status, notebooks, toon_content FROM competition_cache WHERE slug = $1", slug)

    if not row:
        print(f"❌ No record found for {slug}")
        return

    print(f"Slug: {row['slug']}")
    print(f"Status: {row['status']}")

    notebooks = row['notebooks']
    if notebooks:
        parsed_nb = json.loads(notebooks) if isinstance(notebooks, str) else notebooks
        print(f"✅ Notebooks count in DB: {len(parsed_nb)}")
        for i, nb in enumerate(parsed_nb[:2]):
             title = nb.get('meta', {}).get('title', 'N/A')
             print(f"  [{i+1}] {title}")
    else:
        print("❌ Notebooks column is EMPTY")

    toon = row['toon_content']
    if toon:
        print(f"✅ TOON content length: {len(toon)}")
    else:
        print("❌ TOON content is EMPTY")

    await Database.disconnect()

async def clear_cache(slug: str):
    await Database.connect()
    pool = Database.get_pool()
    await pool.execute("DELETE FROM competition_cache WHERE slug = $1", slug)
    print(f"✅ Cleared cache for {slug}")
    await Database.disconnect()

async def test_api_dynamic_merging(slug: str):
    import aiohttp
    async with aiohttp.ClientSession() as session:
        for n in [1, 3, 5]:
            url = f"http://localhost:8000/api/competitions/{slug}?top_n={n}"
            async with session.get(url) as resp:
                data = await resp.json()
                toon = data.get('toon_content', '')
                print(f" top_n={n} | TOON Length: {len(toon)}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("slug")
    parser.add_argument("--clear", action="store_true")
    parser.add_argument("--api", action="store_true")
    args = parser.parse_args()

    if args.clear:
        asyncio.run(clear_cache(args.slug))
    elif args.api:
        asyncio.run(test_api_dynamic_merging(args.slug))
    else:
        asyncio.run(check_db_content(args.slug))
