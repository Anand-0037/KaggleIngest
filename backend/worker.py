import json
import logging
import os
import sys
from typing import Any

import arq
from arq.connections import RedisSettings

# Add current dir to path to find modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import JOB_TIMEOUT, REDIS_URL
from core.file_cache import get_file_cache
from core.jobs import JobRequest
from services.notebook_service import NotebookService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("arq.worker")

async def startup(ctx):
    logger.info("Starting up worker...")
    # Initialize services
    ctx['notebook_service'] = NotebookService()
    list_files_method = ctx['notebook_service'].kaggle_service.list_files
    # Verify Kaggle CLI is available (optional but good sanity check)
    logger.info("Worker services initialized.")

async def shutdown(ctx):
    logger.info("Shutting down worker...")

async def process_ingest_job(ctx, job_req: dict[str, Any]):
    """
    Process an ingestion job.
    Params are passed as a dict serialization of JobRequest.
    """
    job_id = ctx['job_id']
    logger.info(f"Processing job {job_id} with params: {job_req}")

    service: NotebookService = ctx['notebook_service']

    try:
        # Re-hydrate request
        req = JobRequest(**job_req)

        # Define Progress Callback
        async def update_progress(processed, total):
            if not getattr(ctx.get('redis'), 'setex', None):
                 # Fallback if ctx doesn't expose raw redis client easily,
                 # ARQ ctx['redis'] is usually the pool.
                 # Actually ARQ ctx has 'redis' which is ArqRedis, inherited from Redis.
                 # Let's try to use it.
                 pass

            try:
                # Progress Key: job_progress:{job_id}
                key = f"job_progress:{job_id}"
                percent = int((processed / total) * 100) if total > 0 else 0
                data = json.dumps({
                    "processed": processed,
                    "total": total,
                    "percent": percent
                })
                # raw redis access via ctx['redis']
                # TTL 5 minutes
                await ctx['redis'].setex(key, 300, data)
                # logger.info(f"Job {job_id} progress: {percent}%")
            except Exception as e:
                logger.warning(f"Failed to update progress for {job_id}: {e}")

        # Execute the main logic
        # get_completion_context is an async method
        result = await service.get_completion_context(
            resource_type=req.resource_type,
            identifier=req.identifier,
            top_n=req.top_n,
            kaggle_creds=req.kaggle_creds,
            language=None,
            dry_run=req.dry_run,
            progress_callback=update_progress
        )

        # Format the output based on request (this is usually done in API, but
        # doing it here saves result processing time later?
        # Actually API endpoint usually accesses the raw result dict or formatted string.
        # Let's return the structured dict, strict JSON serialization happens by arq.

        logger.info(f"Job {job_id} completed successfully.")
        return result

    except Exception as e:
        logger.error(f"Job {job_id} failed: {e}")
        # Re-raise so ARQ marks it as failed
        raise


async def cleanup_cache_files(ctx):
    """
    Periodic task to clean up expired cached files.
    Runs every 30 minutes to remove files older than 1 hour.
    """
    logger.info("Running cache cleanup task...")

    try:
        file_cache = get_file_cache()
        files_removed, bytes_freed = file_cache.cleanup_expired_files(ttl_seconds=3600)

        logger.info(
            f"Cache cleanup complete: removed {files_removed} files, "
            f"freed {bytes_freed / 1024:.2f} KB"
        )

        return {
            "files_removed": files_removed,
            "bytes_freed": bytes_freed
        }
    except Exception as e:
        logger.error(f"Cache cleanup failed: {e}")
        raise

# Parse REDIS_URL to settings
# redis://localhost:6379 -> host, port
# Basic parsing (assuming standard format)
# Alternatively use from_dsn if available or manual parse
# For now, let's assume standard localhost default from config if parsing fails
redis_settings = RedisSettings(host='localhost', port=6379)
if "redis://" in REDIS_URL:
    try:
        # simplistic parse for host/port
        # redis://host:port/...
        part = REDIS_URL.split("://")[1]
        if ":" in part:
            host, port_str = part.split(":", 1)
            port = int(port_str.split("/")[0])
            redis_settings = RedisSettings(host=host, port=port)
    except Exception as e:
        logger.warning(f"Failed to parse REDIS_URL {REDIS_URL}, using default. Error: {e}")

class WorkerSettings:
    functions = [process_ingest_job]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = redis_settings
    job_timeout = JOB_TIMEOUT
    max_jobs = 5  # Limit concurrent jobs to prevent OOM/Disk overload

    # Periodic cleanup task: runs every 30 minutes
    cron_jobs = [
        # (task, minute, ...)
        # Run cache cleanup at minute 0 and 30 of every hour
        arq.cron(cleanup_cache_files, minute={0, 30}),
    ]
