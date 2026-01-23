
import asyncpg
from datetime import datetime, timezone

class KaggleQuotaManager:
    """
    Centralized quota tracker in Postgres (no Redis needed).
    """

    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
        self.DAILY_LIMIT = 1000  # Kaggle's hard limit

    async def check_and_consume(self, cost: int = 1) -> bool:
        """
        Returns True if request allowed, False if quota exceeded.
        Uses Postgres atomic updates.
        """
        today = datetime.now(timezone.utc).date()

        async with self.db.acquire() as conn:
            # Atomic increment with row-level locking via INSERT ... ON CONFLICT RETURNING
            # This handles the distributed lock implicitly by serializing updates to the row
            result = await conn.fetchrow(
                """
                INSERT INTO kaggle_quota (date, used)
                VALUES ($1, $2)
                ON CONFLICT (date) DO UPDATE
                SET used = kaggle_quota.used + $2
                RETURNING used
                """,
                today, cost
            )

            current_usage = result['used']

            if current_usage > self.DAILY_LIMIT:
                # Quota exceeded. Rolling back the consumption (conceptually)
                # In a strict counting system we might want to decrement,
                # but for rate limiting it's okay if we count rejected requests or just leave it at limit.
                # To be nice to the counter, let's decrement.
                await conn.execute(
                    "UPDATE kaggle_quota SET used = used - $1 WHERE date = $2",
                    cost, today
                )
                return False

            return True

    async def get_remaining_quota(self) -> int:
        """Returns remaining quota for today."""
        today = datetime.now(timezone.utc).date()

        used = await self.db.fetchval(
            "SELECT COALESCE(used, 0) FROM kaggle_quota WHERE date = $1",
            today
        )

        return max(0, self.DAILY_LIMIT - (used or 0))
