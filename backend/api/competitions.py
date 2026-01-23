
# backend/api/competitions.py

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
from datetime import datetime
from backend.core.database import get_db
from backend.core.security import verify_api_key
from backend.services.notebook_service import NotebookService # Use existing service
import asyncpg
import json
import asyncio
from backend import config

router = APIRouter(prefix="/competitions", tags=["Competitions"])
logger = logging.getLogger(__name__)

# Concurrency control to prevent duplicate ingestion tasks
INGESTION_LOCKS: Dict[str, asyncio.Lock] = {}

class IngestRequest(BaseModel):
    url: str
    top_n: Optional[int] = 3
    stream: Optional[bool] = False
    ignore_patterns: Optional[List[str]] = None

# Response Model matching schema
class CompetitionResponse(BaseModel):
    slug: str
    title: str = "Unknown"
    description: Optional[str] = None
    metadata: Dict[str, Any] = {}
    status: str
    message: Optional[str] = None
    cached_at: Optional[datetime] = None
    toon_content: Optional[str] = None

@router.get("/{slug}", response_model=CompetitionResponse)
async def get_competition_metadata(
    slug: str,
    background_tasks: BackgroundTasks,
    top_n: int = config.DEFAULT_NOTEBOOKS,
    db: asyncpg.Pool = Depends(get_db)
):
    """
    Get competition metadata (instant if cached).
    Triggers background fetch on cache miss.
    """
    if not slug or slug.strip() == "":
        raise HTTPException(status_code=400, detail="Invalid competition slug")

    # Check Cache (PostgreSQL)
    cached = await db.fetchrow(
        "SELECT * FROM competition_cache WHERE slug = $1",
        slug
    )

    # Case 1: Completed - return
    if cached and cached['status'] == 'completed':
        # 30-day Expiration Check
        last_updated = cached['updated_at']
        age_seconds = (datetime.now(last_updated.tzinfo) - last_updated).total_seconds()
        is_expired = age_seconds > config.TTL_COMPETITION

        if is_expired:
            logger.info(f"⏳ Cache expired for {slug} ({age_seconds/86400:.1f} days old), triggering re-ingest")
            await db.execute(
                "UPDATE competition_cache SET status = 'processing', updated_at = NOW() WHERE slug = $1",
                slug
            )
            background_tasks.add_task(fetch_and_cache_competition, slug, None, None)
            return CompetitionResponse(
                slug=slug,
                title="Updating cache...",
                status="processing",
                message="Cached data is older than 30 days. Refreshing from Kaggle..."
            )

        logger.info(f"📁 DB Cache hit for {slug} (Top {top_n})")

        # Handle metadata JSON parsing safely
        meta = cached['metadata']
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except json.JSONDecodeError:
                meta = {}

        # Dynamic Merging: Use the stored 'notebooks' JSON if available
        # Fallback to toon_content for backward compatibility
        final_toon = cached['toon_content']
        raw_notebooks = cached.get('notebooks')

        if raw_notebooks:
            # Slicing based on requested top_n
            try:
                if isinstance(raw_notebooks, str):
                    raw_notebooks = json.loads(raw_notebooks)

                sliced_nbs = raw_notebooks[:min(top_n, config.MAX_NOTEBOOKS)]

                # Re-generate TOON content dynamically
                from backend.services.notebook_service import NotebookService
                full_data = {
                    "metadata": meta,
                    "schema": [], # TODO: Store schema separately if needed, for now use empty or meta
                    "notebooks": sliced_nbs,
                    "stats": {}
                }
                final_toon = NotebookService.format_output(full_data, "toon")
                logger.debug(f"Dynamically generated TOON for {slug} with {len(sliced_nbs)} notebooks")
            except Exception as e:
                logger.error(f"Error merging notebooks for {slug}: {e}")
                # Fallback to original toon_content if merging fails

        return CompetitionResponse(
            slug=cached['slug'],
            title=cached['title'] or "Unknown",
            description=cached['description'],
            metadata=meta or {},
            toon_content=final_toon,
            status="completed",
            cached_at=cached['fetched_at']
        )

    # Case 2: Currently processing - return wait message
    elif cached and cached['status'] == 'processing':
        return CompetitionResponse(
            slug=slug,
            title="Processing...",
            status="processing",
            message="Competition data is being fetched. Check back in 30 seconds."
        )

    # Case 3: Failed - retry the fetch
    elif cached and cached['status'] == 'failed':
        logger.info(f"Retrying failed fetch for {slug}")
        await db.execute(
            "UPDATE competition_cache SET status = 'processing', updated_at = NOW() WHERE slug = $1",
            slug
        )
        background_tasks.add_task(fetch_and_cache_competition, slug, None, None)
        return CompetitionResponse(
            slug=slug,
            title="Retrying...",
            status="processing",
            message="Retrying competition data fetch. Check back in 30-60 seconds."
        )

    # Case 4: Not in cache - insert and fetch
    else:
        logger.info(f"Cache miss for {slug}, triggering fetch")
        try:
            await db.execute(
                "INSERT INTO competition_cache (slug, status) VALUES ($1, 'processing')",
                slug
            )
        except asyncpg.UniqueViolationError:
            # Race condition: another request inserted it
            return CompetitionResponse(
                slug=slug,
                title="Processing...",
                status="processing",
                message="Competition data is being fetched. Check back in 30 seconds."
            )

        background_tasks.add_task(fetch_and_cache_competition, slug, None, None)
        return CompetitionResponse(
            slug=slug,
            title="Fetching...",
            status="processing",
            message="Fetching competition data. Refresh in 30-60 seconds."
        )

async def fetch_and_cache_competition(slug: str, kaggle_creds: Optional[Dict[str, str]] = None, ignore_patterns: Optional[List[str]] = None):
    """
    Background task to fetch from Kaggle API and cache.
    Uses a lock per slug to prevent duplicate tasks.
    """
    if slug not in INGESTION_LOCKS:
        INGESTION_LOCKS[slug] = asyncio.Lock()

    async with INGESTION_LOCKS[slug]:
        from backend.core.database import Database
        try:
            # Database.get_pool() should return the pool initialized in lifespan
            pool = Database.get_pool()

            # 1. Double check status inside lock
            row = await pool.fetchrow("SELECT status FROM competition_cache WHERE slug = $1", slug)
            if row and row['status'] == 'completed':
                 logger.info(f"Competition {slug} already cached, skipping.")
                 return

            logger.info(f"Starting background fetch for competition: {slug}")
            from backend.services.notebook_service import NotebookService
            service = NotebookService()

            from backend.services.kaggle_service import KaggleService
            k_service = KaggleService()

            loop = asyncio.get_running_loop()

            # Helper to run blocking Kaggle calls
            async def run_sync(func, *args):
                return await loop.run_in_executor(None, func, *args)

            comp_meta = await run_sync(k_service.get_competition_metadata, slug, kaggle_creds)

            # 2. Fetch Schema (Simplified - just list files for now to save time/bandwidth)
            files = await run_sync(k_service.list_files, "competition", slug, kaggle_creds)
            schema = [{"filename": f, "columns": []} for f in files[:5]]

            # 3. Fetch Top Notebooks (Critical for "Full Context")
            # We fetch up to MAX_NOTEBOOKS (10) for tiered storage
            limit = config.MAX_NOTEBOOKS
            nb_meta_list = await run_sync(
                k_service.list_notebooks,
                "competition", slug, limit, "python", kaggle_creds
            )

            # Rank them
            ranked_nbs = service._rank_notebooks(nb_meta_list)

            # Process (Download & Clean)
            import tempfile
            processed_nbs = []
            stats = {
                "successful_downloads": 0,
                "failed_downloads": 0,
                "failed_notebooks": []
            }
            with tempfile.TemporaryDirectory(prefix="ingest_bg_") as tmpdir:
                 processed_nbs = await service._process_notebooks(
                     ranked_nbs[:limit], tmpdir, kaggle_creds, stats
                 )

            # Persist to external storage
            try:
                from backend.services.storage_service import StorageService
                storage = StorageService()
                toon_content = service.format_output(full_data, "toon")
                await storage.save_result(slug, toon_content)
            except Exception as e:
                logger.error(f"Failed to persist results for {slug} to storage: {e}")

            # 4. Construct Data Dictionary for TOON
            full_data = {
                "metadata": comp_meta.model_dump(),
                "schema": schema,
                "notebooks": processed_nbs,
                "stats": {}
            }

            # 5. Generate TOON Content
            toon_content = service.format_output(full_data, "toon")

            # 6. Save to DB
            metadata = {
                "title": comp_meta.title,
                "url": comp_meta.url,
                "category": comp_meta.category,
                "prize": comp_meta.prize,
                "evaluation": comp_meta.metric,
                "team_count": comp_meta.team_count,
                "leaderboard": comp_meta.leaderboard
            }

            logger.info(f"Background task: Processed {len(processed_nbs)} notebooks for {slug}")

            await pool.execute(
                """
                UPDATE competition_cache
                SET
                    title = $1,
                    description = $2,
                    metadata = $3,
                    notebooks = $4,
                    toon_content = $5,
                    status = 'completed',
                    updated_at = NOW()
                WHERE slug = $6
                """,
                comp_meta.title,
                comp_meta.description,
                json.dumps(metadata, default=str),
                json.dumps(processed_nbs),
                toon_content,
                slug
            )
            logger.info(f"✅ Successfully cached data for {slug} (notebooks: {len(processed_nbs)})")

            logger.info(f"✅ Successfully cached {slug} with {len(processed_nbs)} notebooks")

        except RuntimeError as e:
            logger.error(f"Database pool not available in background task: {e}")
            return
        except Exception as e:
            logger.error(f"❌ Failed to fetch {slug}: {e}")
            import traceback
            logger.error(traceback.format_exc())

            try:
                # Attempt to mark as failed in DB if pool is available
                pool = Database.get_pool()
                await pool.execute(
                    """
                    UPDATE competition_cache
                    SET status = 'failed', error_message = $1, updated_at = NOW()
                    WHERE slug = $2
                    """,
                    str(e), slug
                )
            except Exception as db_err:
                logger.error(f"Failed to update status to failed for {slug}: {db_err}")

