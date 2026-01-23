
import asyncpg
from typing import List, Dict, Any

class CompetitionSearchService:
    """
    Postgres FTS implementation (Refined Architecture).
    Handles typos with pg_trgm and relevance ranking.
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool

    async def search_competitions(
        self,
        query: str,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Multi-strategy search:
        1. Exact match on slug
        2. Full-text search with ranking (tsvector)
        3. Fuzzy trigram similarity (pg_trgm)
        """
        if not query:
            return []

        # Ensure extensions are active is done in migration

        results = await self.db.fetch(
            """
            WITH exact_match AS (
                SELECT *, 10.0 as score
                FROM competition_cache
                WHERE slug = $1 AND status = 'completed'
            ),
            fts_match AS (
                SELECT *,
                    ts_rank(search_vector, plainto_tsquery('english', $1)) as score
                FROM competition_cache
                WHERE search_vector @@ plainto_tsquery('english', $1)
                  AND status = 'completed'
            ),
            fuzzy_match AS (
                SELECT *,
                    similarity(title, $1) as score
                FROM competition_cache
                WHERE similarity(title, $1) > 0.1
                  AND status = 'completed'
            )
            SELECT DISTINCT ON (slug)
                slug, title, description, metadata, score
            FROM (
                SELECT * FROM exact_match
                UNION ALL
                SELECT * FROM fts_match
                UNION ALL
                SELECT * FROM fuzzy_match
            ) combined
            ORDER BY slug, score DESC
            LIMIT $2
            """,
            query, limit
        )

        return [dict(r) for r in results]
