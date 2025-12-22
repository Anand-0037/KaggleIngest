"""
Kaggle API Service - handles all Kaggle API interactions.
Thread-safe credential handling with client caching.
"""

import json
import os
import shutil
import threading

from typing import Any

from tenacity import retry, stop_after_attempt, wait_exponential

from core.exceptions import KaggleIngestionError, MetadataError, NotebookDownloadError
from core.models import CompetitionMetadata, DatasetMetadata, NotebookMeta
from logger import get_logger

logger = get_logger(__name__)


# =============================================================================
# SDK PATCH: Fix Kaggle SDK 1.8.x User-Agent=None bug
# =============================================================================
def _patch_kaggle_sdk():
    """Patch kagglesdk to fix User-Agent=None bug."""
    try:
        from kagglesdk.kaggle_http_client import KaggleHttpClient

        _original_init = KaggleHttpClient.__init__

        def _patched_init(self, *args, **kwargs):
            kwargs.pop('user_agent', None)
            _original_init(self, *args, **kwargs)
            self._user_agent = "kaggle-api/1.8.2"

        KaggleHttpClient.__init__ = _patched_init
        logger.debug("Patched kagglesdk.KaggleHttpClient for User-Agent fix")

    except ImportError:
        pass  # kagglesdk not available
    except Exception as e:
        logger.warning(f"Failed to patch kagglesdk: {e}")


# Apply patch on module load
_patch_kaggle_sdk()


class KaggleService:
    """
    Singleton service for Kaggle API interactions.
    Handles authentication, client lifecycle, and raw API calls.
    Thread-safe credential handling with per-credential caching.
    """
    _instance = None
    _client_cache: dict[str, Any] = {}
    _env_lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(KaggleService, cls).__new__(cls)
        return cls._instance

    def _get_cache_key(self, creds: dict | None) -> str:
        """Generate cache key for client based on credentials."""
        if not creds:
            return "default"
        return json.dumps(dict(sorted(creds.items())))

    def get_client(self, kaggle_creds: dict[str, str] | None = None) -> Any:
        """
        Get or create a Kaggle API client.
        Thread-safe with double-check locking.
        Credentials are restored immediately after authenticate().
        """
        # Fallback to KAGGLE_CONFIG_JSON if no credentials provided
        if not kaggle_creds:
            config_json = os.environ.get("KAGGLE_CONFIG_JSON")
            if config_json:
                try:
                    kaggle_creds = json.loads(config_json)
                    logger.debug("Using credentials from KAGGLE_CONFIG_JSON env var")
                except Exception as e:
                    logger.warning(f"Failed to parse KAGGLE_CONFIG_JSON: {e}")

        cache_key = self._get_cache_key(kaggle_creds)

        # Fast path: cached client (no lock needed)
        if cache_key in self._client_cache:
            return self._client_cache[cache_key]

        with self._env_lock:
            # Double-check inside lock
            if cache_key in self._client_cache:
                return self._client_cache[cache_key]

            try:
                from kaggle.api.kaggle_api_extended import KaggleApi

                # Store and set credentials atomically
                original_env = {
                    "KAGGLE_USERNAME": os.environ.get("KAGGLE_USERNAME"),
                    "KAGGLE_KEY": os.environ.get("KAGGLE_KEY")
                }

                try:
                    if kaggle_creds:
                        os.environ["KAGGLE_USERNAME"] = kaggle_creds["username"]
                        os.environ["KAGGLE_KEY"] = kaggle_creds["key"]

                    api = KaggleApi()
                    api.authenticate()  # Reads credentials into memory

                finally:
                    # Restore immediately after authenticate
                    for key, val in original_env.items():
                        if val is not None:
                            os.environ[key] = val
                        elif key in os.environ and kaggle_creds:
                            del os.environ[key]

                self._client_cache[cache_key] = api
                return api

            except Exception as e:
                logger.error(f"Failed to authenticate with Kaggle: {e}")
                raise KaggleIngestionError(f"Authentication failed: {str(e)}")

    _kaggle_cli_path: str | None = None

    @property
    def kaggle_cli_path(self) -> str:
        """Get absolute path to kaggle CLI. Instance-level caching."""
        if KaggleService._kaggle_cli_path is None:
            KaggleService._kaggle_cli_path = self._resolve_kaggle_cli_path()
        return KaggleService._kaggle_cli_path

    @staticmethod
    def _resolve_kaggle_cli_path() -> str:
        """Resolve CLI path - called once per process lifecycle."""
        import sys
        venv_bin = os.path.dirname(sys.executable)
        kaggle_path = os.path.join(venv_bin, "kaggle")
        if os.path.exists(kaggle_path):
            logger.info(f"Using kaggle CLI at: {kaggle_path}")
            return kaggle_path

        # Fallback to system path
        path = shutil.which("kaggle")
        if path:
            logger.info(f"Using system kaggle CLI at: {path}")
            return path

        # Last resort
        logger.warning("Kaggle CLI not found in venv or system PATH, using 'kaggle'")
        return "kaggle"

    async def _run_command_async(self, cmd: list[str], timeout: int = 300) -> str:
        """Run a command asynchronously using asyncio subprocess."""
        import asyncio

        # Use absolute path for kaggle command
        if cmd and cmd[0] == "kaggle":
             cmd[0] = self.kaggle_cli_path

        cmd_str = self._sanitize_cmd(cmd)
        logger.debug(f"Async Executing: {cmd_str}")

        try:
            # Create subprocess
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **(self._get_env_vars(self.current_creds) if hasattr(self, 'current_creds') else {})}
            )

            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
            except TimeoutError:
                process.kill()
                raise KaggleIngestionError(f"Command timed out after {timeout}s: {cmd_str}")

            if process.returncode != 0:
                error_msg = stderr.decode().strip()
                logger.error(f"Command failed ({process.returncode}): {error_msg}")
                raise KaggleIngestionError(f"Command failed: {error_msg}")

            return stdout.decode().strip()

        except FileNotFoundError:
            raise KaggleIngestionError("Kaggle CLI not found. Is it installed?")
        except Exception as e:
            logger.error(f"Async execution error: {e}")
            raise KaggleIngestionError(f"Execution failed: {str(e)}")

    def _get_env_vars(self, creds: dict | None) -> dict[str, str]:
        """Get environment variables for credentials."""
        if not creds:
            return {}
        return {
            "KAGGLE_USERNAME": creds["username"],
            "KAGGLE_KEY": creds["key"]
        }

    async def list_notebooks_async(
        self,
        resource_type: str,
        identifier: str,
        top_n: int = 10,
        language: str | None = None,
        creds: dict | None = None
    ) -> list[NotebookMeta]:
        """List notebooks asynchronously using Kaggle CLI."""
        # Save creds for _run_command_async context if needed, or pass explicitly
        # For thread/async safety, we pass env vars directly in creates_subprocess

        # CLI: kaggle kernels list --competition [comp] --sort-by voteCount --page-size [n] --csv
        cmd = [self.kaggle_cli_path, "kernels", "list", "--csv", "--sort-by", "voteCount", "--page-size", str(top_n)]

        if resource_type == "competition":
            cmd.extend(["--competition", identifier])
        else:
            cmd.extend(["--dataset", identifier])

        if language:
            cmd.extend(["--language", language])

        # Temporarily set env vars for the subprocess call
        # We need to construct the env manually for the subprocess
        env_vars = self._get_env_vars(creds)

        # Helper to run with specific env
        async def run_with_env():
             import asyncio
             process = await asyncio.create_subprocess_exec(
                 *cmd,
                 stdout=asyncio.subprocess.PIPE,
                 stderr=asyncio.subprocess.PIPE,
                 env={**os.environ, **env_vars}
             )
             stdout, stderr = await process.communicate()
             if process.returncode != 0:
                 raise KaggleIngestionError(f"CLI List failed: {stderr.decode()}")
             return stdout.decode()

        try:
            output = await run_with_env()
            # Parse CSV output
            import csv
            import io
            notebooks = []
            reader = csv.DictReader(io.StringIO(output))
            for row in reader:
                try:
                    # ref is usually "owner/slug" in CSV
                    ref = row.get("ref")
                    if not ref: continue

                    notebooks.append(NotebookMeta(
                        ref=ref,
                        title=row.get("title", ""),
                        author=row.get("author", ""),
                        upvotes=int(row.get("totalVotes", 0)),
                        url=f"https://www.kaggle.com/{ref}",
                        last_updated=row.get("lastRunTime"),
                        # 'kernelType' isn't always in CSV view, but good if present
                        kernel_type=row.get("kernelType")
                    ))
                except Exception as e:
                    logger.warning(f"Failed to parse notebook row: {e}")

            return notebooks[:top_n]

        except Exception as e:
            logger.warning(f"Async list failed: {e}. Falling back to sync SDK.")
            # Fallback to sync method (will block formatted in asyncio.to_thread if we wanted,
            # but for now just call it - caller should handle blocking)
            import asyncio
            return await asyncio.to_thread(
                self.list_notebooks, resource_type, identifier, top_n, language, creds
            )

    async def download_notebook_async(self, ref: str, dest_path: str, creds: dict | None = None):
        """Download notebook asynchronously using Kaggle CLI."""
        cmd = [self.kaggle_cli_path, "kernels", "pull", ref, "--path", dest_path, "--metadata"]

        env_vars = self._get_env_vars(creds)

        try:
            import asyncio
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env={**os.environ, **env_vars}
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                raise NotebookDownloadError(f"Async download failed: {stderr.decode()}")

        except Exception as e:
             logger.error(f"Async download failed for {ref}: {e}")
             raise NotebookDownloadError(f"Failed to download {ref}: {e}")

    # Keep synchronous methods for backward compatibility or fallbacks
    def list_notebooks(
        self,
        resource_type: str,
        identifier: str,
        top_n: int = 10,
        language: str | None = None,
        creds: dict | None = None
    ) -> list[NotebookMeta]:
        """List notebooks synchronously using Kaggle SDK."""
        api = self.get_client(creds)

        search = identifier
        sort_by = 'voteCount'

        try:
            # Note: SDK methods differ slightly by resource type if using lower-level API,
            # but kernels_list is generic.
            # api.kernels_list(page=1, page_size=20, search=..., competition=..., dataset=...)

            kwargs = {
                'page_size': top_n,
                'sort_by': sort_by,
                'search': None # Identifier passed via competition/dataset param
            }

            if resource_type == 'competition':
                kwargs['competition'] = identifier
            else:
                kwargs['dataset'] = identifier

            if language:
                kwargs['language'] = language

            kernels = api.kernels_list(**kwargs)

            notebooks = []
            for kernel in kernels:
                notebooks.append(NotebookMeta(
                    ref=kernel.ref,
                    title=kernel.title,
                    author=kernel.author,
                    upvotes=getattr(kernel, 'totalVotes', 0),
                    url=f"https://www.kaggle.com/{kernel.ref}"
                ))

            return notebooks

        except Exception as e:
            logger.error(f"Sync list notebooks failed: {e}")
            raise KaggleIngestionError(f"Failed to list notebooks: {e}")




    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def download_file(self, resource_type: str, identifier: str, filename: str, dest_path: str, creds: dict | None = None):
        """Download a specific file from a dataset or competition."""
        api = self.get_client(creds)
        try:
            if resource_type == "competition":
                api.competition_download_file(identifier, filename, path=dest_path, quiet=True)
            else:
                api.dataset_download_file(identifier, filename, path=dest_path, quiet=True)
        except Exception as e:
             raise KaggleIngestionError(f"Failed to download file {filename}: {e}")

    def get_competition_metadata(self, identifier: str, creds: dict | None = None) -> CompetitionMetadata:
        """Fetch competition metadata."""
        api = self.get_client(creds)
        try:
            comps = api.competitions_list(search=identifier)
            # Handle SDK response object wrapping the list (ApiListCompetitionsResponse)
            if hasattr(comps, 'competitions'):
                comps = comps.competitions

            # Find exact match
            for comp in comps:
                if getattr(comp, 'ref', '') == identifier or getattr(comp, 'url', '').endswith(identifier):
                    return CompetitionMetadata(
                        title=comp.title,
                        url=comp.url,
                        description=getattr(comp, 'description', ''),
                        category=getattr(comp, 'category', ''),
                        prize=getattr(comp, 'reward', 'N/A'),
                        evaluation=getattr(comp, 'evaluationMetric', ''),
                        dates=str(getattr(comp, 'deadline', ''))
                    )
            raise MetadataError(f"Competition {identifier} not found")
        except Exception as e:
            raise MetadataError(f"Failed to fetch competition metadata: {e}")

    def get_dataset_metadata(self, identifier: str, creds: dict | None = None) -> DatasetMetadata:
        """Fetch dataset metadata."""
        api = self.get_client(creds)
        try:
            datasets = api.dataset_list(search=identifier)
            for ds in datasets:
                if ds.ref == identifier:
                    # Use getattr with fallback - SDK uses different attribute names
                    last_updated = getattr(ds, 'lastUpdated', None) or getattr(ds, 'lastRunTime', '') or ''
                    return DatasetMetadata(
                        title=ds.title,
                        url=ds.url,
                        description=getattr(ds, 'subtitle', ''),
                        last_updated=str(last_updated) if last_updated else ''
                    )
            raise MetadataError(f"Dataset {identifier} not found")
        except Exception as e:
            raise MetadataError(f"Failed to fetch dataset metadata: {e}")

    def list_files(self, resource_type: str, identifier: str, creds: dict | None = None) -> list[str]:
        """List CSV files in the resource."""
        api = self.get_client(creds)
        files = []
        try:
            if resource_type == "competition":
                result = api.competition_list_files(identifier)
                # Handle both direct list and object with .files attribute
                file_objects = getattr(result, 'files', result) if result else []
            else:
                result = api.dataset_list_files(identifier)
                file_objects = getattr(result, 'files', result) if result else []

            # Handle None or empty result
            if not file_objects:
                return []

            for f in file_objects:
                name = str(f) if isinstance(f, str) else getattr(f, 'name', str(f))
                if name.endswith('.csv'):
                    files.append(name)
            return files
        except Exception as e:
            logger.warning(f"Failed to list files: {e}")
            return []

