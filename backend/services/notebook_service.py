import asyncio
import os
import tempfile
import time
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from io import StringIO
from typing import Any, TypedDict

from config import MAX_CSV_FILES_TO_PARSE, MAX_SAMPLE_ROWS
from core.cache import get_cached_data, set_cached_data
from core.exceptions import KaggleIngestionError, NotebookDownloadError
from core.parser import clean_notebook_content, parse_csv_schema, parse_notebook
from core.toon_encoder import encode_to_toon
from logger import get_logger
from services.kaggle_service import KaggleService

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


# Thread pool for CPU-bound operations (parsing, cleaning)
_cpu_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="parse_worker")


class NotebookService:
    """
    Service for downloading, processing, and aggregating Kaggle notebooks.
    Performance optimized with:
    - Thread pool offloading for CPU-bound parsing
    - Parallel schema fetching
    - Async file operations where possible
    """
    def __init__(self):
        # In a real DI framework, this would be injected.
        # For now, relying on Singleton nature of KaggleService.
        self.kaggle_service = KaggleService()

    async def get_completion_context(
        self,
        resource_type: str,
        identifier: str,
        top_n: int = 10,
        kaggle_creds: dict[str, str] | None = None,
        language: str | None = None,
        dry_run: bool = False,
        progress_callback: Callable | None = None,
    ) -> dict[str, Any]:
        """
        Main orchestration method to get all context for a resource.
        """
        start_time = time.time()

        stats: ContextStats = {
            "successful_downloads": 0,
            "failed_downloads": 0,
            "failed_notebooks": [],
            "resource_type": resource_type,
            "resource_id": identifier,
            "start_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "dry_run": dry_run,
            "total_requested": 0,
            "message": None,
            "elapsed_time": 0.0
        }

        try:
            # 1. Fetch Metadata (kept sync for now as it's fast/cached)
            metadata = self._get_metadata(resource_type, identifier, kaggle_creds)

            if dry_run:
                stats["message"] = "Dry-run completed successfully (Metadata validated)"
                stats["elapsed_time"] = time.time() - start_time
                return {"stats": stats, "metadata": metadata, "schema": [], "notebooks": []}

            # 2. Fetch Schema & Process Notebooks
            # Using specific prefix for temporary directory safety
            # ignore_cleanup_errors=True prevents Windows file locking issues (Python 3.10+)
            with tempfile.TemporaryDirectory(prefix="kaggle_ingest_", ignore_cleanup_errors=True) as tmpdir:
                # PERF: Async schema fetching with parallel downloads
                schema = await self._get_schema_async(resource_type, identifier, tmpdir, kaggle_creds)

                # List notebooks asynchronously
                # 1. Fetch more candidates (up to 3x, max 100) to allow for re-ranking
                fetch_limit = min(top_n * 3, 100)

                notebook_metas = await self.kaggle_service.list_notebooks_async(
                    resource_type, identifier, fetch_limit, language, kaggle_creds
                )

                # 2. Re-rank based on Recency + Votes logic
                ranked_metas = self._rank_notebooks(notebook_metas)
                target_notebooks = ranked_metas[:top_n]

                # Stats should reflect user's request, not internal fetch
                stats["total_requested"] = top_n
                stats["notebooks_found"] = len(target_notebooks)

                # Process
                processed_notebooks = await self._process_notebooks(
                    target_notebooks, tmpdir, kaggle_creds, stats, progress_callback
                )

            stats["elapsed_time"] = time.time() - start_time

            # 3. Assemble Result
            return {
                "metadata": metadata,
                "schema": schema,
                "notebooks": processed_notebooks,
                "stats": stats
            }

        except Exception as e:
            logger.error(f"Context generation failed: {e}")
            logger.error(traceback.format_exc())
            raise

    def _get_metadata(self, resource_type: str, identifier: str, creds: dict | None) -> dict[str, Any]:
        """Fetch metadata with caching."""
        cache_key = f"meta_{resource_type}_{identifier}"
        cached = get_cached_data(cache_key)
        if cached:
            return cached

        if resource_type == "competition":
            meta = self.kaggle_service.get_competition_metadata(identifier, creds)
        else:
            meta = self.kaggle_service.get_dataset_metadata(identifier, creds)

        data = meta.model_dump()
        set_cached_data(cache_key, data)
        return data

    async def _get_schema_async(self, resource_type: str, identifier: str, tmpdir: str, creds: dict | None) -> list[dict[str, Any]]:
        """
        Fetch and parse schema with caching.
        PERF: Parallel downloads and CPU-bound parsing offloaded to thread pool.
        """
        cache_key = f"schema_{resource_type}_{identifier}"
        cached = get_cached_data(cache_key)
        if cached:
            return cached

        schema = []
        try:
            # List files is fast, keep sync
            csv_files = self.kaggle_service.list_files(resource_type, identifier, creds)
            files_to_process = csv_files[:MAX_CSV_FILES_TO_PARSE]

            if not files_to_process:
                return schema

            async def download_and_parse(filename: str) -> dict[str, Any] | None:
                """Download a single file and parse its schema."""
                try:
                    file_path = os.path.join(tmpdir, filename)
                    # Download in thread pool (blocking I/O)
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(
                        _cpu_executor,
                        lambda: self.kaggle_service.download_file(
                            resource_type, identifier, filename, tmpdir, creds
                        )
                    )

                    if os.path.exists(file_path):
                        # Parse in thread pool (CPU-bound)
                        file_schema = await loop.run_in_executor(
                            _cpu_executor,
                            parse_csv_schema,
                            file_path,
                            MAX_SAMPLE_ROWS
                        )
                        if file_schema:
                            return file_schema.model_dump()
                    return None

                except KaggleIngestionError as e:
                    logger.warning(f"Failed to download/parse schema for {filename}: {e}")
                    return None
                except Exception as e:
                    logger.warning(f"Unexpected error parsing schema for {filename}: {e}")
                    return None

            # PERF: Parallel schema fetching
            results = await asyncio.gather(
                *[download_and_parse(f) for f in files_to_process],
                return_exceptions=True
            )

            for result in results:
                if isinstance(result, dict):
                    schema.append(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Schema task exception: {result}")

            if schema:
                set_cached_data(cache_key, schema)
            return schema

        except Exception as e:
            logger.warning(f"Schema fetch warning: {e}")
            return []

    async def _process_notebooks(
        self, notebooks: list, tmpdir: str, creds: dict | None, stats: dict,
        progress_callback: Callable | None = None
    ) -> list[dict[str, Any]]:
        """
        Download and parse notebooks in parallel using asyncio.

        Args:
            notebooks: List of notebook metadata objects
            tmpdir: Working directory
            creds: API credentials
            stats: ContextStats object to update

        Returns:
            List of processed notebook dictionaries
        """
        import asyncio

        async def process_single_notebook(index, nb):
            nb_dir = os.path.join(tmpdir, f"nb_{index}")
            os.makedirs(nb_dir, exist_ok=True)
            try:
                logger.info(f"Downloading: {nb.ref}")
                # Use async download method
                await self.kaggle_service.download_notebook_async(nb.ref, nb_dir, creds)

                # PERF: Offload file listing to thread pool to avoid blocking
                loop = asyncio.get_running_loop()
                ipynb_files = await loop.run_in_executor(
                    None,
                    lambda: [f for f in os.listdir(nb_dir) if f.endswith(".ipynb")]
                )
                if not ipynb_files:
                    raise NotebookDownloadError(f"No .ipynb file found for {nb.ref}")

                # PERF: CPU-bound parsing offloaded to thread pool
                ipynb_path = os.path.join(nb_dir, ipynb_files[0])
                content = await loop.run_in_executor(
                    _cpu_executor,
                    parse_notebook,
                    ipynb_path
                )

                if not content:
                    raise ValueError("Parsing failed - empty content")

                # PERF: CPU-bound cleaning offloaded to thread pool
                content = await loop.run_in_executor(
                    _cpu_executor,
                    clean_notebook_content,
                    content
                )

                return {
                    "success": True,
                    "data": {
                        "meta": nb.model_dump(),
                        "index": index,
                        "content": content.model_dump()
                    }
                }
            except Exception as e:
                # Fallback to ref if title is empty
                title = getattr(nb, 'title', None) or nb.ref
                return {
                    "success": False,
                    "ref": nb.ref,
                    "title": title,
                    "error": str(e),
                    "type": type(e).__name__
                }

        # Create tasks
        tasks = [
            process_single_notebook(i, nb)
            for i, nb in enumerate(notebooks, 1)
        ]

        # Run in parallel
        # results = await asyncio.gather(*tasks) # Replaced with completed wrapper for progress

        completed_count = 0
        total_count = len(tasks)
        results = []

        # Use as_completed to report progress
        for future in asyncio.as_completed(tasks):
            result = await future
            results.append(result)
            completed_count += 1
            if progress_callback:
                try:
                    await progress_callback(completed_count, total_count)
                except Exception as e:
                    logger.warning(f"Progress callback failed: {e}")

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

        # Results are already in order due to gather, but index is safe
        processed.sort(key=lambda x: x["index"])
        return processed

    def _rank_notebooks(self, notebooks: list[Any]) -> list[Any]:
        """
        Rank notebooks based on a score combining upvotes and recency.
        Score = upvotes * (decay_factor ^ (age_in_months))
        """
        if not notebooks:
            return []

        now = datetime.now()

        def calculate_score(nb) -> float:
            # 1. Parse date
            age_days = 365 * 2 # Default to 2 years old if parsing fails
            if nb.last_updated:
                try:
                    # Generic parse attempts
                    # Expected: "2023-11-20 14:30:00"
                    if "T" in nb.last_updated:
                         dt = datetime.fromisoformat(nb.last_updated.replace('Z', '+00:00'))
                    elif " " in nb.last_updated:
                        dt = datetime.strptime(nb.last_updated, "%Y-%m-%d %H:%M:%S")
                    else:
                        dt = datetime.strptime(nb.last_updated, "%Y-%m-%d")

                    age_days = (now - dt).days
                except (ValueError, TypeError):
                    pass # Keep default

            # Avoid negative age
            age_days = max(0, age_days)
            age_months = age_days / 30.0

            # 2. Apply Decay (5% per month)
            decay_factor = 0.95
            base_score = nb.upvotes + 1

            # Boost logic: If a notebook is very new (< 3 months) give it a small bonus
            # regardless of votes to help surface new gems?
            # Actually, standard decay works: recent = higher multiplier.

            final_score = base_score * (decay_factor ** age_months)
            return final_score

        return sorted(notebooks, key=calculate_score, reverse=True)

    @staticmethod
    def format_output(
        data: dict[str, Any],
        format_type: str = "txt"
    ) -> str:
        """
        Format the gathered context data into the requested string format.
        PERF: Uses StringIO for efficient string building.
        """
        metadata = data["metadata"]
        schema = data["schema"]
        notebooks = data["notebooks"]

        if format_type == "toon":
            # Just wrap into TOON structure
            toon_data = {
                "metadata": metadata,
                "schema": schema,
                "notebooks": [
                    {
                        "index": nb["index"],
                        "title": nb["meta"].get("title"),
                        "author": nb["meta"].get("author"),
                        "upvotes": nb["meta"].get("upvotes"),
                        "markdown": nb["content"].get("markdown", []),
                        "code": nb["content"].get("code", [])
                    }
                    for nb in notebooks
                ],
                "statistics": data.get("stats", {})
            }
            return encode_to_toon(toon_data)

        elif format_type == "md":
            # PERF: Use StringIO instead of list concatenation
            out = StringIO()
            out.write("# Competition Analysis\n\n")
            out.write("| Metadata | Value |\n|---|---|\n")
            for k, v in metadata.items():
                if v:
                    safe_v = str(v).replace("|", "\\|").replace("\n", " ")
                    out.write(f"| **{k}** | {safe_v} |\n")
            out.write("\n---\n\n")

            if schema:
                out.write("## Dataset Schema\n\n")
                for f_info in schema:
                    out.write(f"### File: `{f_info.get('filename')}`\n")
                    cols = [f"`{c['name']}` ({c['dtype']})" for c in f_info.get('columns', [])]
                    out.write(f"**Columns:** {', '.join(cols)}\n\n")

                    if f_info.get('sample_rows'):
                        col_names = [c['name'] for c in f_info.get('columns', [])]
                        out.write("**Sample Data:**\n\n")
                        out.write("| " + " | ".join(col_names) + " |\n")
                        out.write("| " + " | ".join(["---"] * len(col_names)) + " |\n")
                        for row in f_info['sample_rows'][:5]:
                            safe_row = [str(x).replace("\n", " ").replace("|", "\\|")[:50] for x in row]
                            out.write("| " + " | ".join(safe_row) + " |\n")
                    out.write("\n")
                out.write("---\n\n")

            out.write("## Top Notebooks\n\n")
            for nb in notebooks:
                meta = nb["meta"]
                out.write(f"### {nb['index']}. {meta.get('title')}\n")
                out.write(f"**Author:** {meta.get('author')} | **Votes:** {meta.get('upvotes')}\n\n")

                md_content = nb["content"].get("markdown", [])
                if md_content:
                    out.write("#### 📝 Insights\n\n")
                    out.write("\n\n".join(md_content))
                    out.write("\n\n")

                code_content = nb["content"].get("code", [])
                if code_content:
                    out.write("#### 💻 Code\n\n")
                    out.write("```python\n")
                    out.write("\n\n".join(code_content))
                    out.write("\n```\n\n")
                out.write("---\n\n")

            return out.getvalue()

        else:  # TXT default
            # PERF: Use StringIO instead of list concatenation
            out = StringIO()
            out.write("# Metadata\n\n")
            for k, v in metadata.items():
                if v:
                    out.write(f"{k}: {v}\n")
            out.write("\n-----\n\n# Datasets\n\n")

            for f_info in schema:
                out.write(f"File: {f_info.get('filename')}\n")
                cols = ", ".join([f"{c['name']} ({c['dtype']})" for c in f_info.get('columns', [])])
                out.write(f"Columns: {cols}\n")
                out.write("Sample Rows:\n")
                for row in f_info.get('sample_rows', []):
                    out.write(f"{row}\n")
                out.write("\n")
            out.write("-----\n\n")

            for nb in notebooks:
                meta = nb["meta"]
                out.write(f"# Notebook {nb['index']}\n\n")
                out.write(f"Title: {meta.get('title')}\n")
                out.write(f"Author: {meta.get('author')}\n")
                out.write(f"Votes: {meta.get('upvotes')}\n\n")

                out.write("## Markdown\n")
                out.write("\n".join(nb["content"].get("markdown", [])))
                out.write("\n\n## Code\n")
                out.write("\n".join(nb["content"].get("code", [])))
                out.write("\n\n-----\n\n")

            return out.getvalue()
