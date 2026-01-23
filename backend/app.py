
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
import logging
import time
import asyncpg
import sys
import os

# Add parent directory to sys.path to allow 'backend' imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.core.database import Database
from backend.core.logging_config import setup_logging
from backend.api import auth, competitions
from backend.core.security import limiter
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
import sentry_sdk
from prometheus_client import make_asgi_app, Counter, Histogram
from backend import config

# Setup structured logging
setup_logging()
logger = logging.getLogger(__name__)

# Initialize Sentry
if config.SENTRY_ENABLED:
    sentry_sdk.init(
        dsn=config.SENTRY_DSN,
        traces_sample_rate=1.0,
        profiles_sample_rate=1.0,
    )
    logger.info("🛡️ Sentry initialized")

# Prometheus Metrics
from prometheus_client import REGISTRY

def get_metric(metric_type, name, documentation, labelnames):
    if name in REGISTRY._names_to_collectors:
        return REGISTRY._names_to_collectors[name]
    return metric_type(name, documentation, labelnames)

REQUEST_COUNT = get_metric(Counter, "http_requests_total", "Total HTTP Requests", ["method", "endpoint", "status"])
REQUEST_LATENCY = get_metric(Histogram, "http_request_duration_seconds", "HTTP Request Latency", ["method", "endpoint"])

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Refined Lifespan: Handles DB connection pool.
    """
    logger.info("🚀 Starting KaggleIngest API...")

    # Initialize DB Pool
    try:
        await Database.connect()
    except Exception as e:
        logger.error(f"Failed to connect to database: {e}")

    yield

    logger.info("🛑 Shutting down KaggleIngest API...")
    await Database.disconnect()
    from backend.services.notebook_service import NotebookService
    NotebookService.shutdown()

app = FastAPI(
    title="KaggleIngest API",
    description="Token-optimized Kaggle competition metadata service",
    version="2.0.0",
    lifespan=lifespan
)

# Rate Limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "https://kaggleingest.com",
        "https://www.kaggleingest.com",
        "https://kaggle-ingest.vercel.app",
        "https://kaggle-ingest-rho.vercel.app",
        "*"
    ], # Allow * for ease of dev, specific origins for prod safety recommended but Vercel previews are dynamic
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GZip Compression
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Request Timing Middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    method = request.method
    endpoint = request.url.path

    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time

    # Update Prometheus metrics
    if config.PROMETHEUS_ENABLED:
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=response.status_code).inc()
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint).observe(duration)

    process_time = duration * 1000
    response.headers["X-Process-Time-Ms"] = str(int(process_time))
    return response

# Prometheus metrics endpoint
if config.PROMETHEUS_ENABLED:
    metrics_app = make_asgi_app()
    app.mount("/api/metrics", metrics_app)

# Routers (with /api prefix)
app.include_router(auth.router, prefix="/api")
app.include_router(competitions.router, prefix="/api")

# Search endpoint was previously directly in app.py in an iteration,
# but "Action Plan" didn't strictly specify where it goes.
# We'll add it here or in competitions router.
# For now, let's keep the user's "search" instruction in mind.
# The user asked for "Competition metadata endpoint" in api/competitions.py.
# Access to /search might be missing if I don't add it.
# I will add a simple search endpoint here integrating the SearchService if it exists.
# Moving to /api/search and removing auth.

from backend.services.search_service import CompetitionSearchService
from fastapi import Depends
from backend.core.database import get_db
from backend.core.security import verify_api_key

async def get_search_service():
    pool = Database.get_pool()
    return CompetitionSearchService(pool)

@app.get("/api/search")
@limiter.limit("20/minute")
async def search_competitions(
    request: Request,
    query: str,
    search_service: CompetitionSearchService = Depends(get_search_service)
):
    """
    Search competitions using hybrid Postgres FTS + Fuzzy search.
    """
    try:
        results = await search_service.search_competitions(query)
        return {"results": results}
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail="Search failed")



# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# LEGACY ROUTES (For backwards compatibility with stale Vercel frontend)
# ------------------------------------------------------------------------------
from fastapi import BackgroundTasks, UploadFile, File, Form
@app.post("/get-context", response_model=CompetitionResponse, tags=["Legacy"])
async def legacy_get_context(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    db: asyncpg.Pool = Depends(get_db)
):
    """
    Alias for /api/get-context to support older frontends.
    """
    logger.warning(f"⚠️ Legacy /get-context called for {request.url}")
    return await get_context(request, background_tasks, db)

@app.post("/get-context-upload", response_model=CompetitionResponse, tags=["Legacy"])
async def legacy_get_context_upload(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    top_n: int = Form(3),
    token_file: UploadFile = File(...),
    db: asyncpg.Pool = Depends(get_db)
):
    """
    Alias for /api/get-context-upload to support older frontends.
    """
    return await get_context_upload(background_tasks, url, top_n, token_file, db)
# ------------------------------------------------------------------------------


from backend.api.competitions import CompetitionResponse, fetch_and_cache_competition, IngestRequest

@app.post("/api/get-context", response_model=CompetitionResponse)
async def get_context(
    request: IngestRequest,
    background_tasks: BackgroundTasks,
    db: asyncpg.Pool = Depends(get_db)
):
    """
    Generic context endpoint for any Kaggle URL.
    """
    from backend.services.kaggle_service import KaggleService
    k_service = KaggleService()
    slug = k_service._extract_slug(request.url)

    from backend.api.competitions import get_competition_metadata
    return await get_competition_metadata(slug, background_tasks, request.top_n, db=db)

@app.post("/api/get-context-upload", response_model=CompetitionResponse)
async def get_context_upload(
    background_tasks: BackgroundTasks,
    url: str = Form(...),
    top_n: int = Form(3),
    token_file: UploadFile = File(...),
    db: asyncpg.Pool = Depends(get_db)
):
    """
    Ingestion endpoint with kaggle.json upload support.
    """
    from backend.services.validation_service import ValidationService
    from backend.services.kaggle_service import KaggleService

    creds = await ValidationService.validate_and_read_token_file(token_file)
    k_service = KaggleService()
    slug = k_service._extract_slug(url)

    cached = await db.fetchrow(
        "SELECT * FROM competition_cache WHERE slug = $1",
        slug
    )

    if cached and cached['status'] == 'completed':
        await db.execute(
            "UPDATE competition_cache SET status = 'processing', updated_at = NOW() WHERE slug = $1",
            slug
        )
    elif not cached:
         await db.execute(
            "INSERT INTO competition_cache (slug, status) VALUES ($1, 'processing')",
            slug
        )

    background_tasks.add_task(fetch_and_cache_competition, slug, creds)

    return CompetitionResponse(
        slug=slug,
        title="Processing...",
        status="processing",
        message="Private ingestion started with provided credentials."
    )


@app.get("/health")
async def health_check():
    """Health Check for Load Balancers."""
    try:
        pool = Database.get_pool()
        async with pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8000, reload=True)
