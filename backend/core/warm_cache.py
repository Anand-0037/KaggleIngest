"""Warm cache implementation using PostgreSQL."""
import json
import logging
from typing import Optional, List
from datetime import datetime

from backend.config import POPULAR_COMPETITIONS
from backend.db.session import DatabaseSession

logger = logging.getLogger(__name__)

class WarmCache:
    """Pre-fetched competition cache in PostgreSQL."""

    def __init__(self):
        self.db = DatabaseSession.get_instance()

    async def connect(self):
        """No-op: connection managed by DatabaseSession."""
        pass

    async def close(self):
        """No-op: connection managed by DatabaseSession."""
        pass



    async def save_competition(self, identifier: str, metadata: dict,
                               schema: list, notebooks: list, ttl_seconds: int = 86400):
        """Save competition data with an expiration time."""
        try:
            pool = await self.db.get_pool()
            async with pool.acquire() as conn:
                async with conn.transaction():
                    # Upsert competition metadata with dynamic expiry
                    # SECURITY: Using parameterized query to prevent SQL injection
                    await conn.execute("""
                        INSERT INTO warm_cache_competitions
                        (identifier, metadata, schema, notebook_count, is_popular, last_refreshed, expires_at)
                        VALUES ($1, $2, $3, $4, $5, NOW(), NOW() + make_interval(secs => $6))
                        ON CONFLICT (identifier)
                        DO UPDATE SET
                            metadata = EXCLUDED.metadata,
                            schema = EXCLUDED.schema,
                            notebook_count = EXCLUDED.notebook_count,
                            last_refreshed = NOW(),
                            expires_at = NOW() + make_interval(secs => $6)
                    """, identifier, json.dumps(metadata or {}), json.dumps(schema or []),
                        len(notebooks), identifier in POPULAR_COMPETITIONS, ttl_seconds)

                    # Clear old notebooks
                    await conn.execute("""
                        DELETE FROM warm_cache_notebooks WHERE competition_id = $1
                    """, identifier)

                    # Insert new notebooks (batch)
                    if notebooks:
                        values = []
                        for nb in notebooks:
                            meta = nb.get('meta', {})
                            content = nb.get('content', {})

                            # Safely convert Pydantic models to dicts
                            if hasattr(meta, 'model_dump'):
                                meta = meta.model_dump()
                            elif hasattr(meta, 'dict'):
                                meta = meta.dict()

                            if hasattr(content, 'model_dump'):
                                content = content.model_dump()
                            elif hasattr(content, 'dict'):
                                content = content.dict()

                            ref = meta.get('ref') or f"nb_{nb.get('index')}"
                            values.append((
                                identifier, ref, nb.get('index', 0),
                                json.dumps(meta), json.dumps(content)
                            ))

                        await conn.executemany("""
                            INSERT INTO warm_cache_notebooks
                            (competition_id, notebook_ref, rank, metadata, parsed_content)
                            VALUES ($1, $2, $3, $4, $5)
                        """, values)

            logger.info(f"🔥 Saved {identifier} to warm cache (expires in {ttl_seconds}s)")
        except Exception as e:
            logger.error(f"Failed to save competition {identifier}: {e}")
            raise

    async def get_competition(self, identifier: str, limit: int = 10) -> Optional[dict]:
        """Retrieve pre-cached competition data if valid."""
        try:
            pool = await self.db.get_pool()
            async with pool.acquire() as conn:
                # Get competition metadata (checking expires_at)
                comp = await conn.fetchrow("""
                    SELECT metadata, schema, notebook_count, last_refreshed
                    FROM warm_cache_competitions
                    WHERE identifier = $1 AND expires_at > NOW()
                """, identifier)

                if not comp:
                    return None

                # Get notebooks (sliced to limit)
                notebooks = await conn.fetch("""
                    SELECT rank, metadata, parsed_content
                    FROM warm_cache_notebooks
                    WHERE competition_id = $1
                    ORDER BY rank ASC
                    LIMIT $2
                """, identifier, limit)

            return {
                'metadata': json.loads(comp['metadata']),
                'schema': json.loads(comp['schema']),
                'notebooks': [
                    {
                        'index': nb['rank'],
                        'meta': json.loads(nb['metadata']),
                        'content': json.loads(nb['parsed_content'])
                    }
                    for nb in notebooks
                ],
                'stats': {
                    'cached': True,
                    'refreshed_at': comp['last_refreshed'].isoformat()
                }
            }
        except Exception as e:
            logger.warning(f"Warm cache get error: {e}")
            return None

    async def search_notebooks(self, query: str, competition: str = None,
                               limit: int = 10) -> List[dict]:
        """Full-text search across cached notebooks."""
        try:
            pool = await self.db.get_pool()

            sql = """
                SELECT competition_id, notebook_ref, rank, metadata,
                       ts_rank(to_tsvector('english', parsed_content::text),
                              plainto_tsquery('english', $1)) AS relevance
                FROM warm_cache_notebooks
                WHERE to_tsvector('english', parsed_content::text) @@
                      plainto_tsquery('english', $1)
            """

            params = [query]
            if competition:
                sql += " AND competition_id = $2"
                params.append(competition)

            sql += " ORDER BY relevance DESC, rank ASC LIMIT $" + str(len(params) + 1)
            params.append(limit)

            async with pool.acquire() as conn:
                results = await conn.fetch(sql, *params)

            return [
                {
                    'competition': r['competition_id'],
                    'notebook_ref': r['notebook_ref'],
                    'rank': r['rank'],
                    'metadata': json.loads(r['metadata']),
                    'relevance': float(r['relevance'])
                }
                for r in results
            ]
        except Exception as e:
            logger.warning(f"Search error: {e}")
            return []

# Global instance
_warm_cache = None

async def get_warm_cache() -> WarmCache:
    """Get or create warm cache instance."""
    global _warm_cache
    if _warm_cache is None:
        _warm_cache = WarmCache()
        # Connection is now lazy/singleton-managed
        await _warm_cache.db.connect()
    return _warm_cache
