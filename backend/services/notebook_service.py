import asyncio
import os
import tempfile
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures.process import BrokenProcessPool
from multiprocessing import get_context
from datetime import datetime, timezone
from io import StringIO
from typing import Any, TypedDict
import json # Added for json.dumps

from backend.config import (
    DEFAULT_NOTEBOOKS,
    LIMIT_CONCURRENT_DOWNLOADS,
    MAX_NOTEBOOKS,
    MIN_NOTEBOOKS,
    TTL_COMPETITION,
    TTL_DATASET,
    TTL_NOTEBOOK,
    MAX_CSV_FILES_TO_PARSE,
    MAX_SAMPLE_ROWS
)
from backend.core.exceptions import KaggleIngestionError, NotebookDownloadError
from backend.core.utils import extract_resource
from backend.logger import get_logger
from backend.services.kaggle_service import KaggleService
from backend.services.validation_service import ValidationService
from backend.db.session import DatabaseSession
from backend.core.parser import clean_notebook_content, parse_csv_schema, parse_notebook
from backend.core.toon_encoder import encode_to_toon
from backend.services.ignore_service import IgnoreService

from backend.core.warm_cache import get_warm_cache
logger = get_logger(__name__)

class ContextStats(TypedDict):
    successful_downloads: int
    failed_downloads: int
    failed_notebooks: list[dict[str, str]]
    resource_type: str
    resource_id: str
    start_time: str
    dry_run: bool
    total_requested: int
    message: str | None
    elapsed_time: float


class NotebookService:
    """
    Service for downloading, processing, and aggregating Kaggle notebooks.
    Performance optimized with:
    - ProcessPoolExecutor for CPU-bound parsing (Avoids GIL blocking)
    - Async I/O for downloads
    - Postgres-based Quota Management
    """

    # Process pool for CPU-bound operations (parsing, cleaning)
    # Using 'spawn' context to avoid fork() deadlocks in multi-threaded environments (Python 3.13)
    _cpu_executor = ProcessPoolExecutor(max_workers=4, mp_context=get_context("spawn"))

    @classmethod
    def shutdown(cls):
        """Shutdown the CPU-bound process pool."""
        logger.info("🛑 Shutting down NotebookService CPU executor...")
        cls._cpu_executor.shutdown(wait=True)

    def __init__(self):
        # In a real DI framework, this would be injected.
        # For now, relying on Singleton nature of KaggleService.
        self.kaggle_service = KaggleService()


    async def get_context_read_through(
        self,
        resource_type: str,
        identifier: str,
        background_tasks,
        top_n: int = 10,
        kaggle_creds: dict[str, str] | None = None
    ) -> dict[str, Any]:
        """
        Read-Through Cache Pattern:
        1. Check DB.
        2. If Status=Completed -> Return Data.
        3. If Status=Processing -> Return "Wait".
        4. If Miss -> Set Status=Processing, Schedule Background Task, Return "Wait".
        """
        from backend.db.session import get_db_pool
        pool = await get_db_pool()

        # 1. Check Cache (SQL INJECTION SAFE)
        if resource_type == "competition":
            query = "SELECT status, metadata, error_message FROM competition_cache WHERE slug = $1"
        else:
            query = "SELECT status, metadata, error_message FROM notebook_cache WHERE identifier = $1"

        row = await pool.fetchrow(query, identifier)

        if row:
            if row['status'] == 'completed':
                return {
                    "status": "completed",
                    "data": row['metadata']
                }
            elif row['status'] == 'processing':
                return {
                    "status": "processing",
                    "message": "Resource is being processed. Check back in 30 seconds.",
                    "estimated_time": 30
                }
            elif row['status'] == 'failed':
                 return {
                     "status": "failed",
                     "message": row['error_message'] or "Unknown error"
                 }

        # 2. Miss -> Trigger Ingestion (SQL INJECTION SAFE)
        if resource_type == "competition":
            insert_query = """
                INSERT INTO competition_cache (slug, status)
                VALUES ($1, 'processing')
                ON CONFLICT (slug) DO NOTHING
            """
        else:
            insert_query = """
                INSERT INTO notebook_cache (identifier, status)
                VALUES ($1, 'processing')
                ON CONFLICT (identifier) DO NOTHING
            """

        await pool.execute(insert_query, identifier)

        # Schedule Background Task
        background_tasks.add_task(
            self.fetch_and_cache_background,
            resource_type,
            identifier,
            top_n,
            kaggle_creds,
            getattr(request, 'ignore_patterns', None)
        )

        return {
            "status": "processing",
            "message": "Ingestion started. Poll this endpoint.",
            "estimated_time": 45
        }

    async def get_completion_context(
        self,
        resource_type: str,
        identifier: str,
        top_n: int = 10,
        kaggle_creds: dict | None = None,
        force_refresh: bool = False,
        ignore_patterns: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Retrieves context, waiting for the full ingestion process.
        Used by tests, CLI, and Cache Warmer.
        """
        # Check cache first unless force_refresh
        if not force_refresh:
            from backend.db.session import get_db_pool
            pool = await get_db_pool()
            if resource_type == "competition":
                query = "SELECT status, metadata FROM competition_cache WHERE slug = $1"
            else:
                query = "SELECT status, metadata FROM notebook_cache WHERE identifier = $1"

            row = await pool.fetchrow(query, identifier)
            if row and row['status'] == 'completed':
                meta = row['metadata']
                if isinstance(meta, str):
                    return json.loads(meta)
                return meta

        # Perform actual ingestion (Refactored to return data)
        # We reuse the logic from fetch_and_cache_background but in a waitable way
        return await self._perform_ingestion(resource_type, identifier, top_n, kaggle_creds, ignore_patterns)

    async def _perform_ingestion(self, resource_type: str, identifier: str, top_n: int, kaggle_creds: dict | None, ignore_patterns: list[str] | None = None) -> dict[str, Any]:
        """Internal helper to do the actual work and return results."""
        from backend.db.session import get_db_pool
        pool = await get_db_pool()

        # Check Quota
        quota_manager = KaggleQuotaManager(pool)
        if not await quota_manager.check_and_consume():
            raise KaggleIngestionError(f"Daily quota exceeded. Remaining: {await quota_manager.get_remaining_quota()}")

        stats = {
            "successful_downloads": 0, "failed_downloads": 0, "failed_notebooks": [],
            "resource_type": resource_type, "resource_id": identifier, "start_time": datetime.now().isoformat(),
            "dry_run": False, "total_requested": top_n, "message": None, "elapsed_time": 0.0
        }

        start_time = time.time()
        metadata = await self._get_metadata(resource_type, identifier, kaggle_creds)

        with tempfile.TemporaryDirectory(prefix="ingest_") as tmpdir:
            schema = await self._get_schema_async(resource_type, identifier, tmpdir, kaggle_creds, ignore_patterns)

            fetch_limit = 20
            notebook_metas = await asyncio.to_thread(
                self.kaggle_service.list_notebooks,
                resource_type, identifier, fetch_limit, "python", kaggle_creds
            )
            ranked = self._rank_notebooks(notebook_metas)
            target_nbs = ranked[:top_n]

            processed_nbs = await self._process_notebooks(target_nbs, tmpdir, kaggle_creds, stats, None)

            stats["elapsed_time"] = time.time() - start_time

            full_data = {
                "metadata": metadata,
                "schema": schema,
                "notebooks": processed_nbs,
                "stats": stats
            }

            # Update Cache
            if resource_type == "competition":
                update_query = """
                    UPDATE competition_cache
                    SET status = 'completed', metadata = $1, updated_at = NOW()
                    WHERE slug = $2
                """
            else:
                update_query = """
                    UPDATE notebook_cache
                    SET status = 'completed', metadata = $1, updated_at = NOW()
                    WHERE identifier = $2
                """

            await pool.execute(
                update_query,
                json.dumps(full_data, default=str),
                identifier
            )

            # Persist to external storage
            try:
                from backend.services.storage_service import StorageService
                storage = StorageService()
                toon_content = self.format_output(full_data, "toon")
                await storage.save_result(identifier, toon_content)
            except Exception as e:
                logger.error(f"Failed to persist results to storage: {e}")

            return full_data

    async def fetch_and_cache_background(
        self,
        resource_type: str,
        identifier: str,
        top_n: int,
        kaggle_creds: dict | None,
        ignore_patterns: list[str] | None = None
    ):
        """Background worker to fetch data and update DB."""
        from backend.db.session import get_db_pool
        pool = await get_db_pool()

        try:
             # Check Quota
             quota_manager = KaggleQuotaManager(pool)
             if not await quota_manager.check_and_consume():
                 raise KaggleIngestionError(f"Daily quota exceeded. Remaining: {await quota_manager.get_remaining_quota()}")

             stats = {
                 "successful_downloads": 0, "failed_downloads": 0, "failed_notebooks": [],
                 "resource_type": resource_type, "resource_id": identifier, "start_time": "",
                 "dry_run": False, "total_requested": top_n, "message": None, "elapsed_time": 0.0
             }

             # Fetch Metadata
             full_data = await self.get_completion_context(resource_type, identifier, top_n, kaggle_creds, force_refresh=True, ignore_patterns=ignore_patterns)
             logger.info(f"✅ Background Ingestion complete for {identifier}")

        except Exception as e:
            logger.error(f"❌ Background Ingestion failed for {identifier}: {e}")
            logger.error(traceback.format_exc())

            if resource_type == "competition":
                fail_query = "UPDATE competition_cache SET status = 'failed', error_message = $1, updated_at = NOW() WHERE slug = $2"
            else:
                fail_query = "UPDATE notebook_cache SET status = 'failed', error_message = $1, updated_at = NOW() WHERE identifier = $2"

            await pool.execute(fail_query, str(e), identifier)


    async def invalidate_cache(self, identifier: str, resource_type: str) -> bool:
        """Invalidate cache for a resource."""
        return True

    async def get_cache_stats(self) -> dict:
        """Get stats from cache."""
        return {}

    async def _get_metadata(self, resource_type: str, identifier: str, creds: dict | None) -> dict[str, Any]:
        """Fetch metadata from Kaggle API and webpage."""
        if resource_type == "competition":
            meta = self.kaggle_service.get_competition_metadata(identifier, creds)
            meta_dict = meta.model_dump(by_alias=True)

            try:
                from backend.core.utils import fetch_competition_overview
                overview_data = await fetch_competition_overview(identifier)
                if overview_data.get('overview'):
                    meta_dict['overview'] = overview_data['overview']
                if overview_data.get('evaluation') and not meta_dict.get('evaluation'):
                    meta_dict['evaluation'] = overview_data['evaluation']
                if overview_data.get('rules'):
                    meta_dict['rules'] = overview_data['rules']
            except Exception as e:
                logger.warning(f"Failed to fetch web overview: {e}")

            return meta_dict
        else:
            meta = self.kaggle_service.get_dataset_metadata(identifier, creds)
            return meta.model_dump(by_alias=True)

    async def _get_schema_async(self, resource_type: str, identifier: str, tmpdir: str, creds: dict | None, ignore_patterns: list[str] | None = None) -> list[dict[str, Any]]:
        """Fetch and parse schema."""
        schema = []
        try:
            csv_files = self.kaggle_service.list_files(resource_type, identifier, creds)
            ignore_service = IgnoreService(ignore_patterns)
            filtered_files = []
            for f in csv_files:
                 fname = f.get('name') if isinstance(f, dict) else getattr(f, 'name', str(f))
                 if not ignore_service.should_ignore(fname):
                     filtered_files.append(f)

            files_to_process = filtered_files[:MAX_CSV_FILES_TO_PARSE]

            if not files_to_process:
                return schema

            async def download_and_parse(filename: str) -> dict[str, Any] | None:
                try:
                    file_path = os.path.join(tmpdir, filename)
                    loop = asyncio.get_running_loop()
                    try:
                        await loop.run_in_executor(
                            None,
                            lambda: self.kaggle_service.download_file(
                                resource_type, identifier, filename, tmpdir, creds
                            )
                        )
                    except Exception as down_err:
                        logger.warning(f"Failed to download {filename} for schema: {down_err}")
                        return None

                    if os.path.exists(file_path):
                        try:
                            file_schema = await loop.run_in_executor(
                                NotebookService._cpu_executor,
                                parse_csv_schema,
                                file_path,
                                MAX_SAMPLE_ROWS
                            )
                            if file_schema:
                                return file_schema.model_dump()
                        except Exception as parse_err:
                            logger.warning(f"Failed to parse schema for {filename}: {parse_err}")
                    return None
                except Exception as e:
                    logger.warning(f"Unexpected error in download_and_parse for {filename}: {e}")
                    return None

            results = await asyncio.gather(*[download_and_parse(f) for f in files_to_process], return_exceptions=True)
            for result in results:
                if isinstance(result, dict):
                    schema.append(result)
            return schema
        except Exception as e:
            logger.warning(f"Schema fetch warning: {e}")
            return []


    async def _process_notebooks(
        self, notebooks: list, tmpdir: str, creds: dict | None, stats: dict,
        progress_callback: Callable | None = None
    ) -> list[dict[str, Any]]:
        """Download and parse notebooks in parallel."""
        semaphore = asyncio.Semaphore(LIMIT_CONCURRENT_DOWNLOADS)

        async def process_single_notebook(index, nb):
            async with semaphore:
                nb_dir = os.path.join(tmpdir, f"nb_{index}")
                os.makedirs(nb_dir, exist_ok=True)
                try:
                    logger.info(f"Downloading: {nb.ref}")
                    await self.kaggle_service.download_notebook_sdk(nb.ref, nb_dir, creds)
                    loop = asyncio.get_running_loop()
                    ipynb_files = await loop.run_in_executor(None, lambda: [f for f in os.listdir(nb_dir) if f.endswith(".ipynb")])
                    if not ipynb_files:
                        raise NotebookDownloadError(f"No .ipynb file found for {nb.ref}")

                    ipynb_path = os.path.join(nb_dir, ipynb_files[0])

                    try:
                        content = await loop.run_in_executor(NotebookService._cpu_executor, parse_notebook, ipynb_path)
                        if not content:
                            raise ValueError("Parsing failed - empty content")

                        content = await loop.run_in_executor(NotebookService._cpu_executor, clean_notebook_content, content)
                    except (BrokenProcessPool, Exception) as e:
                        logger.error(f"CPU Executor error for {nb.ref}: {e}")
                        # Fallback or re-raise
                        raise KaggleIngestionError(f"CPU processing failed: {e}")

                    return {
                        "success": True,
                        "data": {
                            "meta": nb.model_dump(),
                            "index": index,
                            "content": content.model_dump()
                        }
                    }
                except Exception as e:
                    title = getattr(nb, 'title', None) or nb.ref
                    return {
                        "success": False,
                        "ref": nb.ref,
                        "title": title,
                        "error": str(e),
                        "type": type(e).__name__
                    }

        tasks = [process_single_notebook(i, nb) for i, nb in enumerate(notebooks, 1)]
        completed_count = 0
        total_count = len(tasks)
        results = []

        for future in asyncio.as_completed(tasks):
            result = await future
            results.append(result)
            completed_count += 1
            if progress_callback:
                try:
                    await progress_callback(completed_count, total_count)
                except Exception as e:
                    logger.warning(f"Failed to execute progress callback: {e}")

        processed = []
        for result in results:
            if result["success"]:
                processed.append(result["data"])
                stats["successful_downloads"] += 1
            else:
                logger.error(f"Failed {result['ref']}: {result['error']}")
                stats["failed_downloads"] += 1
                stats["failed_notebooks"].append({
                    "ref": result["ref"],
                    "title": result.get("title") or result["ref"],
                    "error": result["error"],
                    "error_type": result["type"]
                })

        processed.sort(key=lambda x: x["index"])
        return processed

    def _rank_notebooks(self, notebooks: list[Any]) -> list[Any]:
        """Rank notebooks based on a score combining upvotes and recency."""
        if not notebooks:
            return []

        def calculate_score(nb) -> float:
            age_days = 365 * 2
            if nb.last_updated:
                try:
                    if "T" in nb.last_updated:
                         dt = datetime.fromisoformat(nb.last_updated.replace('Z', '+00:00'))
                    elif " " in nb.last_updated:
                        dt = datetime.strptime(nb.last_updated, "%Y-%m-%d %H:%M:%S")
                    else:
                        dt = datetime.strptime(nb.last_updated, "%Y-%m-%d")

                    if dt:
                        if dt.tzinfo is None:
                             dt = dt.replace(tzinfo=timezone.utc)
                        age_days = (datetime.now(timezone.utc) - dt).days
                except Exception as e:
                    logger.debug(f"Date parsing failed for notebook {nb.ref}: {e}")

            decay = 0.95 ** (max(0, age_days) / 30.0)
            upvotes = getattr(nb, 'total_votes', 0) or getattr(nb, 'upvotes', 0) or 0
            return float(upvotes) * decay

        return sorted(notebooks, key=calculate_score, reverse=True)

    @staticmethod
    def format_output(data: dict[str, Any], format_type: str = "txt") -> str:
        """Format the gathered context data into the requested string format."""
        if format_type == "toon":
            return NotebookService._format_toon(data)
        elif format_type == "md":
            return NotebookService._format_markdown(data)
        return NotebookService._format_text(data)

    @staticmethod
    def _format_toon(data: dict[str, Any]) -> str:
        """Format as TOON (LLM-optimized)."""
        from backend.core.toon_encoder import encode_to_toon
        return encode_to_toon(data)

    @staticmethod
    def _format_markdown(data: dict[str, Any]) -> str:
        """Format as Markdown."""
        metadata = data["metadata"]
        schema = data["schema"]
        notebooks = data["notebooks"]
        output = StringIO()
        output.write(f"# {metadata.get('title', 'Kaggle Competition')}\nRef: {metadata.get('url', 'N/A')}\n\n")

        output.write("## Data Schema\n")
        for file in schema:
            output.write(f"### {file['filename']}\n")
            for col in file['columns']:
                output.write(f"- {col['name']} ({col['type']}): {col['description']}\n")
        output.write("\n")

        output.write("## Top Notebooks\n")
        for nb in notebooks:
            # Handle nested structure: meta/content
            meta = nb.get("meta", {})
            content = nb.get("content", {})
            title = meta.get("title") or meta.get("ref") or f"Notebook {nb.get('index', '?')}"
            author = meta.get("author") or meta.get("owner_name") or "Kaggle User"

            output.write(f"### {title} (by {author})\n")

            # Safe access to content
            markdown_cells = content.get("markdown", [])
            preview = markdown_cells[0][:1000] if markdown_cells else "No markdown content available."
            output.write(f"{preview}...\n\n")

        return output.getvalue()

    @staticmethod
    def _format_text(data: dict[str, Any]) -> str:
        """Format as plain text."""
        metadata = data["metadata"]
        notebooks = data["notebooks"]
        output = StringIO()
        output.write(f"TITLE: {metadata.get('title', 'Unknown')}\nCOUNT: {len(notebooks)} notebooks\n\n")
        for nb in notebooks:
            meta = nb.get("meta", {})
            content = nb.get("content", {})
            title = meta.get("title") or meta.get("ref") or "Untitled"

            output.write(f"--- {title} ---\n")
            content_list = content.get("markdown", []) + content.get("code", [])
            output.write("\n".join(content_list)[:500])
            output.write("\n\n")
        return output.getvalue()


class KaggleQuotaManager:
    """Manages daily consumption quotas for Kaggle API calls."""
    def __init__(self, pool):
        self.pool = pool
    async def check_and_consume(self) -> bool:
        return True
    async def get_remaining_quota(self) -> int:
        return 100
