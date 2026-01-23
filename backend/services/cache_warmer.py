
import asyncio
import os
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
# Using standard timezone from datetime to avoid pytz dependency if possible, or just standard utc
from datetime import timezone

from backend.logger import get_logger
from backend.db.session import DatabaseSession
from backend.services.competition_lister import CompetitionLister, CompetitionMetadata
from backend.services.notebook_service import NotebookService
from backend.config import POPULAR_COMPETITIONS

logger = get_logger(__name__)

class CacheWarmer:
    """
    Orchestrates background warming of competitions.
    """

    def __init__(self):
        self.lister = CompetitionLister()
        self.notebook_service = NotebookService()
        self.db = DatabaseSession.get_instance()
        # Fix: Helper to ensure timezone aware scheduler
        self.scheduler = AsyncIOScheduler(timezone=timezone.utc)
        self._warming_lock = asyncio.Lock()

    def start_scheduler(self):
        """Start the background scheduler."""
        if not self.scheduler.running:
            # Add jobs
            self.scheduler.add_job(
                self.safe_refresh_registry,
                'interval',
                hours=24,
                coalesce=True, # Prevent stacking
                max_instances=1
            )
            self.scheduler.add_job(
                self.warm_priority_competitions,
                'interval',
                hours=6,
                coalesce=True,
                max_instances=1
            )
            self.scheduler.add_job(
                self.cleanup_stale_processing,
                'interval',
                minutes=30,
                coalesce=True,
                max_instances=1
            )
            self.scheduler.start()
            logger.info("⏰ Cache Warmer Scheduler started")

    def stop_scheduler(self):
        """Stop the scheduler gracefully."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False) # wait=False to not block shutdown
            logger.info("🛑 Cache Warmer Scheduler stopped")

    async def safe_refresh_registry(self):
        """Wrapper for error handling."""
        try:
            await self.refresh_registry()
        except Exception as e:
            logger.error(f"Registry refresh failed: {e}", exc_info=True)

    async def refresh_registry(self):
        """Fetch latest competitions and update registry."""
        logger.info("Starting competition registry refresh...")

        # 1. Fetch from API
        competitions = self.lister.list_competitions(page=1)
        fetched_slugs = {c.slug for c in competitions}

        # 2. Add Popular Competitions if not present
        # We don't have full metadata for them if we don't fetch,
        # but we can insert them with basic info and let the warmer fill details later?
        # Or better, fetch them individually if needed.
        # For now, just ensure they exist in list with high priority.
        for slug in POPULAR_COMPETITIONS:
            if slug not in fetched_slugs:
                # Create a placeholder metadata
                competitions.append(CompetitionMetadata(
                    slug=slug,
                    title=slug.replace("-", " ").title(),
                    description="Popular competition",
                    deadline=None, # Unknown
                    reward="0",
                    team_count=9999,
                    is_active=True,
                    priority=1 # Always high priority
                ))

        pool = await self.db.get_pool()
        async with pool.acquire() as conn:
            # Use improved Upsert logic
            for comp in competitions:
                await conn.execute("""
                    INSERT INTO competitions_registry
                    (slug, title, description, dataset_count, priority, deadline, is_active, last_metadata_refresh)
                    VALUES ($1, $2, $3, 0, $4, $5, $6, NOW())
                    ON CONFLICT (slug) DO UPDATE SET
                        title = EXCLUDED.title,
                        description = EXCLUDED.description,
                        -- Only update priority if it's higher (smaller number)
                        priority = LEAST(competitions_registry.priority, EXCLUDED.priority),
                        deadline = EXCLUDED.deadline,
                        is_active = EXCLUDED.is_active,
                        last_metadata_refresh = NOW()
                    WHERE
                        competitions_registry.title IS DISTINCT FROM EXCLUDED.title
                        OR competitions_registry.deadline IS DISTINCT FROM EXCLUDED.deadline
                        OR competitions_registry.is_active IS DISTINCT FROM EXCLUDED.is_active
                        OR competitions_registry.priority > EXCLUDED.priority
                """, comp.slug, comp.title, comp.description, comp.priority, comp.deadline, comp.is_active)

        logger.info(f"✅ Registry refreshed ({len(competitions)} competitions)")

    async def warm_priority_competitions(self):
        """Warm up Priority 1 competitions."""
        if self._warming_lock.locked():
            logger.info("⚠️ Warmup already in progress, skipping")
            return

        async with self._warming_lock:
            logger.info("🔥 Starting Priority Warmup...")
            try:
                pool = await self.db.get_pool()
                # Fetch Priority 1 comps that haven't been refreshed in 24 hours
                rows = await pool.fetch("""
                    SELECT slug FROM competitions_registry
                    WHERE priority = 1
                    AND (last_notebooks_refresh IS NULL OR last_notebooks_refresh < NOW() - INTERVAL '24 hours')
                    LIMIT 20
                """)

                slugs_warmed = []
                for row in rows:
                    slug = row['slug']
                    logger.info(f"🔥 Warming {slug}...")
                    try:
                        # Ingest top 10 notebooks
                        await self.notebook_service.get_completion_context(
                            resource_type='competition',
                            identifier=slug,
                            top_n=10
                        )
                        slugs_warmed.append(slug)

                        # Sleep to be nice to Kaggle API
                        await asyncio.sleep(5)

                    except Exception as e:
                        logger.error(f"Failed to warm {slug}: {e}")

                # Batch Update Timestamp
                if slugs_warmed:
                    await pool.execute(
                        "UPDATE competitions_registry SET last_notebooks_refresh = NOW() WHERE slug = ANY($1)",
                        slugs_warmed
                    )
                    logger.info(f"✅ Successfully warmed {len(slugs_warmed)} competitions")

                logger.info("✅ Priority Warmup Complete")

            except Exception as e:
                logger.error(f"Warmup failed: {e}", exc_info=True)

    async def cleanup_stale_processing(self):
        """Reset stuck 'processing' tasks to 'failed'."""
        if self._warming_lock.locked():
             return

        async with self._warming_lock:
            logger.info("🧹 Starting stale processing cleanup...")
            try:
                pool = await self.db.get_pool()
                async with pool.acquire() as conn:
                    result = await conn.execute("""
                        UPDATE competition_cache
                        SET status = 'failed',
                            message = 'Processing timed out (stale cleanup)',
                            updated_at = NOW()
                        WHERE status = 'processing'
                        AND updated_at < NOW() - INTERVAL '1 hour'
                    """)
                    logger.info(f"🧹 Stale cleanup finished: {result}")
            except Exception as e:
                logger.error(f"Stale cleanup failed: {e}", exc_info=True)
