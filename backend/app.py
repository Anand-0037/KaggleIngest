"""
FastAPI application for Kaggle notebook ingestion.
v5.0 - Production-ready with Redis caching, streaming responses, and async I/O.
"""

import asyncio
import json
import os
import shutil
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager

import aiofiles
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import (
    Depends,
    FastAPI,
    File,
    HTTPException,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from config import (
    CORS_ORIGINS,
    DEFAULT_NOTEBOOKS,
    MAX_NOTEBOOKS,
    MIN_NOTEBOOKS,
    RATE_LIMIT,
    REDIS_URL,
    SECURE_HEADERS,
)
from core.exceptions import URLParseError
from core.file_cache import get_file_cache
from core.jobs import IngestRequestBody, JobRequest, JobStatus
from core.redis_cache import close_redis_cache, get_redis_cache, get_upstash_cache, use_upstash
from core.utils import extract_resource
from logger import get_logger, setup_logging
from services.kaggle_service import KaggleService
from services.notebook_service import NotebookService
from services.validation_service import ValidationService

setup_logging()
logger = get_logger(__name__)

# --- Environment ---
IS_PRODUCTION = os.getenv("ENV", "development").lower() == "production"

# --- Rate Limiting ---
# Custom key function to properly handle X-Forwarded-For when behind reverse proxies
def get_real_client_ip(request: Request) -> str:
    """
    Get the real client IP address, respecting X-Forwarded-For header.
    This prevents rate-limiting all users as one when behind a load balancer.
    """
    # Check X-Forwarded-For header (set by reverse proxies)
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # Take the first IP in the chain (original client)
        return forwarded_for.split(",")[0].strip()

    # Check X-Real-IP header (Nginx)
    real_ip = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip.strip()

    # Fallback to direct connection IP
    return get_remote_address(request)

limiter = Limiter(key_func=get_real_client_ip)

# --- Metrics ---
REQUEST_COUNT = Counter('api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])
REQUEST_DURATION = Histogram('api_request_duration_seconds', 'Request duration', ['method', 'endpoint'])
CACHE_HITS = Counter('cache_hits_total', 'Cache hit count')
CACHE_MISSES = Counter('cache_misses_total', 'Cache miss count')
ACTIVE_REQUESTS = Gauge('active_requests', 'Currently processing requests')
DOWNLOADS_IN_PROGRESS = Gauge('downloads_in_progress', 'Notebook downloads in progress')

# --- Thread Pool for blocking operations ---
executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="kaggle_worker")


# --- Lifespan (startup/shutdown) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown."""
    app.state.start_time = time.time()

    # Initialize cache (Upstash if configured, else standard Redis)
    if use_upstash():
        upstash_cache = get_upstash_cache()
        app.state.cache = upstash_cache
        app.state.use_upstash = True
        cache_status = "Upstash" if upstash_cache.is_connected else "disabled"
    else:
        cache = await get_redis_cache()
        app.state.cache = cache
        app.state.use_upstash = False
        cache_status = "Redis" if cache.is_connected else "disabled"

    app.state.local_jobs = {}  # Helper for non-Redis fallback

    # Initialize ARQ Redis Pool (still needs TCP connection for job queue)
    try:
        # Parse REDIS_URL or use defaults
        # Simple parse for demo, arq usually takes settings
        redis_settings = RedisSettings(host='localhost', port=6379)
        if "redis://" in REDIS_URL:
            # simplistic parse logic or rely on env
            pass

        pool = await create_pool(redis_settings)
        app.state.arq_pool = pool
        logger.info(f"ARQ Redis Pool initialized: {pool}")
    except Exception as e:
        logger.error(f"Failed to initialize ARQ pool: {e}")
        app.state.arq_pool = None

    logger.info(f"KaggleIngest API v5.0 starting up (Cache: {cache_status})")

    yield

    # Initialize Limiter
    app.state.limiter = limiter

    # Setup cleanup task for cache files
    # ... (existing cleanup logic)

    executor.shutdown(wait=True)
    if getattr(app.state, 'arq_pool', None):
        await app.state.arq_pool.close()
    await close_redis_cache()
    logger.info("KaggleIngest API shutting down")


app = FastAPI(
    title="Kaggle Notebook Ingestion API",
    version="5.0.0",
    description="Production-ready API with Redis caching, streaming responses, and async operations",
    lifespan=lifespan,
    # Disable docs in production
    docs_url=None if IS_PRODUCTION else "/docs",
    redoc_url=None if IS_PRODUCTION else "/redoc",
)

# Set up Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Middleware ---
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    for header, value in SECURE_HEADERS.items():
        response.headers[header] = value
    return response


@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    """Track request metrics."""
    ACTIVE_REQUESTS.inc()
    start_time = time.time()

    try:
        response = await call_next(request)
        duration = time.time() - start_time

        REQUEST_COUNT.labels(
            method=request.method,
            endpoint=request.url.path,
            status=response.status_code
        ).inc()

        REQUEST_DURATION.labels(
            method=request.method,
            endpoint=request.url.path
        ).observe(duration)

        return response
    finally:
        ACTIVE_REQUESTS.dec()


# --- Dependencies ---
def get_notebook_service():
    return NotebookService()


def get_kaggle_service():
    return KaggleService()


# --- Streaming Response Helper ---
async def stream_file_chunks(filepath: str, chunk_size: int = 8192, delete_after: bool = False):
    """
    Stream file in chunks.

    Args:
        filepath: Path to file to stream
        chunk_size: Size of chunks to read
        delete_after: If True, delete file after streaming (default: False for caching)
    """
    try:
        async with aiofiles.open(filepath, 'rb') as f:
            while chunk := await f.read(chunk_size):
                yield chunk
    finally:
        # ARCHITECTURAL CHANGE: Only delete if explicitly requested
        # By default, files are kept for caching and cleaned up by TTL task
        if delete_after:
            try:
                if os.path.exists(filepath):
                    os.remove(filepath)
                    logger.debug(f"Cleaned up streamed file: {filepath}")
            except Exception as e:
                logger.warning(f"Failed to cleanup {filepath}: {e}")


# --- Endpoints ---

@app.get("/health")
async def health_check():
    """
    Enhanced health check with uptime, Redis, and dependency status.
    NOTE: Does NOT check Kaggle to avoid SystemExit crashes on missing credentials.
    """
    uptime = time.time() - getattr(app.state, 'start_time', time.time())
    cache = getattr(app.state, 'cache', None)

    status = {
        "status": "healthy",
        "version": "5.0.0",
        "uptime_seconds": round(uptime, 2),
        "environment": "production" if IS_PRODUCTION else "development",
        "dependencies": {}
    }

    # Check cache (Upstash or Redis)
    cache_type = "upstash" if getattr(app.state, 'use_upstash', False) else "redis"
    status["dependencies"]["cache"] = cache.is_connected if cache else False
    status["dependencies"]["cache_type"] = cache_type if (cache and cache.is_connected) else "none"

    # Check cache directory
    cache_path = os.path.expanduser("~/.cache/kaggleingest")
    status["dependencies"]["file_cache"] = os.access(os.path.dirname(cache_path), os.W_OK)

    # Check disk space (>1GB free)
    try:
        disk = shutil.disk_usage("/")
        status["dependencies"]["disk_space"] = disk.free > 1e9
    except Exception:
        status["dependencies"]["disk_space"] = False

    # Kaggle check is done separately via /health/ready to avoid startup crashes
    status["dependencies"]["kaggle_api"] = "check /health/ready"

    return status



@app.get("/health/ready")
async def readiness_check(kaggle_service: KaggleService = Depends(get_kaggle_service)):
    """
    Readiness check - is this instance ready to receive traffic?
    Catches SystemExit from Kaggle SDK to prevent crashes.
    """
    try:
        kaggle_service.get_client()
        return {"ready": True, "kaggle": True}
    except SystemExit as e:
        # Kaggle SDK calls exit(1) when credentials are missing
        logger.warning(f"Kaggle SDK exited during readiness check: {e}")
        return {"ready": True, "kaggle": False, "note": "Kaggle credentials not configured"}
    except Exception as e:
        logger.warning(f"Readiness check failed: {e}")
        return {"ready": True, "kaggle": False, "error": str(e)}



@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/get-context")
@limiter.limit(f"{RATE_LIMIT}/minute")
async def submit_ingest_job_json(
    request: Request,
    body: IngestRequestBody,
    notebook_service: NotebookService = Depends(get_notebook_service)
):
    """
    Submit ingestion job (POST with JSON body).

    CRITICAL FIX: POST endpoint now accepts JSON body as per REST conventions.
    Query parameters in POST requests are non-standard and can hit URL length limits.

    Request body:
    ```json
    {
        "url": "https://kaggle.com/competitions/titanic",
        "top_n": 10,
        "output_format": "txt",
        "dry_run": false,
        "stream": true
    }
    ```

    - **token_file**: Optional multipart file upload for Kaggle credentials
    """
    logger.info(f"POST Request: url={body.url}, top_n={body.top_n}, format={body.output_format}")

    # Pure JSON POST doesn't handle multipart files
    kaggle_creds = None

    try:
        # Validate URL
        resource = extract_resource(body.url)

        # Construct Job Request
        job_params = JobRequest(
            resource_type=resource["type"],
            identifier=resource["id"],
            top_n=body.top_n,
            format_type=body.output_format,
            kaggle_creds=kaggle_creds,
            dry_run=body.dry_run
        ).dict() # serialize for arq

        # Enqueue Job
        pool = getattr(app.state, 'arq_pool', None)
        if not pool:
            # Fallback for local dev without Redis
            logger.warning("Redis unavailable, running synchronously (Fallback)")
            try:
                # Run sync
                result_data = await notebook_service.get_completion_context(
                    resource_type=resource["type"],
                    identifier=resource["id"],
                    top_n=body.top_n,
                    kaggle_creds=kaggle_creds,
                    dry_run=body.dry_run
                )

                # Create Mock Job ID
                mock_job_id = f"sync_{uuid.uuid4().hex[:8]}"

                # Store in memory
                app.state.local_jobs[mock_job_id] = {
                    "status": "complete",
                    "result": result_data,
                    "enqueued_time": time.time()
                }

                return {
                    "job_id": mock_job_id,
                    "status": "complete",
                    "message": "Job completed synchronously (Redis unavailable)."
                }
            except Exception as e:
                logger.error(f"Sync Fallback Failed: {e}")
                raise HTTPException(status_code=500, detail=f"Job failed: {e}") from e

        job = await pool.enqueue_job('process_ingest_job', job_params)

        if not job:
             raise HTTPException(status_code=500, detail="Failed to enqueue job")

        # Return Job ID
        return {
            "job_id": job.job_id,
            "status": "queued",
            "message": "Job submitted successfully. Poll /jobs/{job_id} for status."
        }

    except URLParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job Submission Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/get-context-upload") # New dedicated upload endpoint
@limiter.limit(f"{RATE_LIMIT}/minute")
@app.get("/get-context") # Legacy GET
@app.post("/get-context-legacy") # Support old style POST if needed
@limiter.limit(f"{RATE_LIMIT}/minute")
async def submit_ingest_job_upload(
    request: Request,
    url: str = Query(..., description="Kaggle competition or dataset URL"),
    top_n: int = Query(
        DEFAULT_NOTEBOOKS,
        ge=MIN_NOTEBOOKS,
        le=MAX_NOTEBOOKS,
        description="Number of notebooks to fetch"
    ),
    output_format: str = Query(
        "txt",
        pattern="^(txt|toon|md)$",
        description="Output format (txt, toon, md)"
    ),
    dry_run: bool = Query(False, description="Validate only"),
    token_file: UploadFile | None = File(None, description="Kaggle JSON credentials (max 10KB)"),
    notebook_service: NotebookService = Depends(get_notebook_service)
):
    """
    Legacy GET endpoint for backward compatibility.

    For new integrations, prefer POST /get-context with JSON body.
    This endpoint uses query parameters which can hit URL length limits.
    """
    logger.info(f"GET Request (Legacy): url={url}, top_n={top_n}, format={output_format}")

    # SECURITY FIX: Validate credentials file
    kaggle_creds = await ValidationService.validate_and_read_token_file(token_file)

    try:
        # Validate URL
        resource = extract_resource(url)

        # Construct Job Request
        job_params = JobRequest(
            resource_type=resource["type"],
            identifier=resource["id"],
            top_n=top_n,
            format_type=output_format,
            kaggle_creds=kaggle_creds,
            dry_run=dry_run
        ).dict()

        # Enqueue Job (same logic as POST)
        pool = getattr(app.state, 'arq_pool', None)
        if not pool:
            logger.warning("Redis unavailable, running synchronously (Fallback)")
            try:
                result_data = await notebook_service.get_completion_context(
                    resource_type=resource["type"],
                    identifier=resource["id"],
                    top_n=top_n,
                    kaggle_creds=kaggle_creds,
                    dry_run=dry_run
                )

                mock_job_id = f"sync_{uuid.uuid4().hex[:8]}"
                app.state.local_jobs[mock_job_id] = {
                    "status": "complete",
                    "result": result_data,
                    "enqueued_time": time.time()
                }

                return {
                    "job_id": mock_job_id,
                    "status": "complete",
                    "message": "Job completed synchronously (Redis unavailable)."
                }
            except Exception as e:
                logger.error(f"Sync Fallback Failed: {e}")
                raise HTTPException(status_code=500, detail=f"Job failed: {e}") from e

        job = await pool.enqueue_job('process_ingest_job', job_params)
        if not job:
             raise HTTPException(status_code=500, detail="Failed to enqueue job")

        return {
            "job_id": job.job_id,
            "status": "queued",
            "message": "Job submitted successfully. Poll /jobs/{job_id} for status."
        }

    except URLParseError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Job Submission Error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/jobs/{job_id}/download")
async def download_job_result(
    job_id: str,
    format: str = Query("txt", pattern="^(txt|toon|md)$"),
    notebook_service: NotebookService = Depends(get_notebook_service)
):
    """
    Download the generated context file for a completed job.

    PERFORMANCE FIX: Check cache first, only format if cache miss.
    PERFORMANCE FIX: Offload CPU-bound formatting to thread pool.
    """
    try:
        # QUICK WIN: Check if file already cached
        file_cache = get_file_cache()
        cached_file = file_cache.get_cached_file(job_id, format)

        if cached_file:
            # Cache hit - serve directly
            logger.info(f"Serving cached file for job {job_id}")
            filename = cached_file.name

            headers = {
                'Content-Disposition': f'attachment; filename="{filename}"',
                'X-Content-Type-Options': 'nosniff',
            }

            return StreamingResponse(
                stream_file_chunks(str(cached_file), delete_after=False),
                media_type="text/plain",
                headers=headers
            )

        # Cache miss - fetch job result and format
        logger.info(f"Cache miss for job {job_id}, formatting output")

        pool = getattr(app.state, 'arq_pool', None)
        if not pool:
            # Check local jobs
            local_job = app.state.local_jobs.get(job_id)
            if not local_job:
                raise HTTPException(status_code=404, detail="Job not found (Redis unavailable)")

            status = local_job["status"]
            result_data = local_job.get("result")

            if status != "complete":
                raise HTTPException(status_code=400, detail=f"Job not complete (status: {status})")

        else:
            from arq.jobs import Job
            job = Job(job_id, redis=pool)
            status = await job.status()

            if status != "complete":
                 raise HTTPException(status_code=400, detail=f"Job not complete (status: {status})")

            info = await job.result_info()
            result_data = info.result if info else None

            if not result_data:
                 raise HTTPException(status_code=404, detail="Job result not found")

        # PERFORMANCE FIX: Run CPU-bound formatting in thread pool
        # This prevents blocking the event loop during string concatenation
        loop = asyncio.get_event_loop()
        content = await loop.run_in_executor(
            executor,
            notebook_service.format_output,
            result_data,
            format
        )

        # Save to cache
        filepath = await file_cache.save_to_cache(job_id, format, content)
        filename = filepath.name

        headers = {
            'Content-Disposition': f'attachment; filename="{filename}"',
            'X-Content-Type-Options': 'nosniff',
        }

        return StreamingResponse(
            stream_file_chunks(str(filepath), delete_after=False),
            media_type="text/plain",
            headers=headers
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Download Error: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/jobs/{job_id}")
async def get_job_status(job_id: str):
    """Check status of a background job."""
    pool = getattr(app.state, 'arq_pool', None)
    if not pool:
        # Check local jobs
        local_job = app.state.local_jobs.get(job_id)
        if not local_job:
             # Just return 404
             raise HTTPException(status_code=404, detail="Job not found")

        return {
            "job_id": job_id,
            "status": local_job["status"],
            "result": local_job.get("result"),
            "error": local_job.get("error")
        }

    from arq.jobs import Job
    job = Job(job_id, redis=pool)
    status = await job.status()

    result = None
    error = None

    if status == JobStatus.COMPLETED or status == "complete":
        # arq returns 'complete' string
        info = await job.result_info()
        result = info.result if info else None

    elif status == "failed":
        try:
             await job.result()
        except Exception as e:
             error = str(e)

    response = {
        "job_id": job_id,
        "status": status,
        "result": result, # contains metadata/stats
        "error": error
    }

    # Fetch Progress if still running
    if status == "queued" or status == "in_progress":
        try:
            progress_key = f"job_progress:{job_id}"
            progress_data = await pool.get(progress_key)
            if progress_data:
                response["progress"] = json.loads(progress_data)
        except Exception as e:
            logger.warning(f"Failed to fetch progress for {job_id}: {e}")

    return response


@app.delete("/cache/invalidate")
async def invalidate_cache(pattern: str = Query("*", description="Key pattern to invalidate")):
    """
    Invalidate Redis cache entries matching pattern.
    Admin endpoint - should be protected in production.
    """
    cache = getattr(app.state, 'cache', None)
    if not cache or not cache.is_connected:
        raise HTTPException(status_code=503, detail="Redis cache not available")

    await cache.invalidate_pattern(pattern)
    return {"status": "invalidated", "pattern": pattern}

