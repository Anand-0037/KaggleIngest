"""
Kaggle API Service - handles all Kaggle API interactions.
"""
import json
import os

import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.core.exceptions import KaggleIngestionError, MetadataError, NotebookDownloadError
from backend.core.models import CompetitionMetadata, DatasetMetadata, NotebookMeta
from backend.config import KAGGLE_USERNAME, KAGGLE_KEY
from backend.logger import get_logger

# ... imports ...
import threading
from kaggle.api.kaggle_api_extended import KaggleApi

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
        pass
    except Exception as e:
        logger.warning(f"Failed to patch kagglesdk: {e}")

_patch_kaggle_sdk()

class KaggleService:
    """
    Singleton service for Kaggle API interactions.
    Handles authentication and client lifecycle.
    """
    _instance = None
    _lock = threading.Lock()
    _client = None
    _api_semaphore = threading.Semaphore(5)  # Limit concurrent Kaggle API calls to 5

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super(KaggleService, cls).__new__(cls)
        return cls._instance

    def get_client(self, creds: dict[str, str] | None = None):
        """
        Get Kaggle API client.
        If 'creds' is provided, returns a NEW client instance (thread-safe).
        If 'creds' is None, returns the cached global client (initialized from env).
        """
        if creds:
            try:
                # Create temporary client (not cached) for specific credentials
                client = KaggleApi()

                # Attempt to inject credentials if supported by SDK wrapper
                if hasattr(client, 'credentials'):
                    client.credentials = creds

                client.authenticate()
                return client
            except Exception as e:
                 logger.error(f"Failed to create custom client: {e}")
                 raise

        # Singleton Logic
        if self._client:
            return self._client

        with self._lock:
            if self._client:
                return self._client

            # Initialize global client
            self._client = KaggleApi()
            self._client.authenticate()
            return self._client


    async def download_notebook_sdk(self, ref: str, dest_path: str, creds: dict | None = None):
        """Download notebook asynchronously using Kaggle SDK in a thread."""
        await asyncio.to_thread(self.download_notebook, ref, dest_path, creds)

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def download_notebook(self, ref: str, dest_path: str, creds: dict | None = None):
        """Download notebook using Kaggle SDK (Sync) with retry."""
        api = self.get_client(creds)
        try:
            # kernels_pull downloads files to path
            # metadata=True downloads kernel-metadata.json
            with self._api_semaphore:
                api.kernels_pull(ref, path=dest_path, metadata=True, quiet=True)
        except Exception as e:
            logger.error(f"Sync download failed for {ref}: {e}")
            raise NotebookDownloadError(f"Failed to download {ref}: {e}")


    def list_notebooks(self, resource_type: str, identifier: str, top_n: int = 10, language: str | None = None, creds: dict | None = None) -> list[NotebookMeta]:
        """List notebooks synchronously using Kaggle SDK (Legacy Fallback)."""
        api = self.get_client(creds)
        search = identifier
        kwargs = {'page_size': top_n, 'sort_by': 'voteCount', 'search': None}
        if resource_type == 'competition':
            kwargs['competition'] = identifier
        else:
            kwargs['dataset'] = identifier
        if language:
            kwargs['language'] = language

        try:
            with self._api_semaphore:
                kernels = api.kernels_list(**kwargs)
            notebooks = []
            for kernel in kernels:
                # Handle lastRunTime/lastUpdated differences across SDK versions
                last_updated = (
                    getattr(kernel, 'lastRunTime', None) or
                    getattr(kernel, 'lastUpdated', None) or
                    ''
                )
                # Ensure totalVotes is int (some SDK versions return string)
                upvotes = getattr(kernel, 'totalVotes', 0)
                try:
                    upvotes = int(upvotes) if upvotes else 0
                except (ValueError, TypeError):
                    upvotes = 0

                notebooks.append(NotebookMeta(
                    ref=kernel.ref,
                    title=kernel.title,
                    author=kernel.author,
                    upvotes=upvotes,
                    url=f"https://www.kaggle.com/{kernel.ref}",
                    last_updated=str(last_updated) if last_updated else None
                ))
            return notebooks
        except Exception as e:
            logger.error(f"Sync list notebooks failed: {e}")
            raise KaggleIngestionError(f"Failed to list notebooks: {e}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def download_file(self, resource_type: str, identifier: str, filename: str, dest_path: str, creds: dict | None = None):
        """Download a specific file (Sync)."""
        api = self.get_client(creds)
        try:
            with self._api_semaphore:
                if resource_type == "competition":
                    api.competition_download_file(identifier, filename, path=dest_path, quiet=True)
                else:
                    api.dataset_download_file(identifier, filename, path=dest_path, quiet=True)
        except Exception as e:
             raise KaggleIngestionError(f"Failed to download file {filename}: {e}")

    def _extract_slug(self, identifier: str) -> str:
        """Extract slug from Kaggle URL if provided."""
        if 'kaggle.com/' in identifier:
            # Handle URLs like https://www.kaggle.com/competitions/titanic
            # or https://www.kaggle.com/datasets/user/slug
            parts = identifier.split('kaggle.com/')[-1].split('/')
            if len(parts) >= 2:
                # competitions/titanic -> titanic
                # datasets/user/slug -> user/slug
                if parts[0] == 'competitions':
                    return parts[1].split('?')[0]
                if parts[0] in ('datasets', 'code'):
                    return '/'.join(parts[1:3]).split('?')[0]
        return identifier.split('?')[0].strip('/')

    def get_competition_metadata(self, identifier: str, creds: dict | None = None) -> CompetitionMetadata:
        api = self.get_client(creds)
        slug = self._extract_slug(identifier)
        try:
            with self._api_semaphore:
                comps = api.competitions_list(search=slug)
            if hasattr(comps, 'competitions'):
                comps = comps.competitions
            for comp in comps:
                if getattr(comp, 'ref', '') == slug or getattr(comp, 'url', '').endswith(slug):
                    # Fetch leaderboard (top 10)
                    leaderboard = []
                    try:
                        with self._api_semaphore:
                            lb_data = api.competition_leaderboard_view(identifier)
                        if hasattr(lb_data, 'submissions'):
                            lb_data = lb_data.submissions
                        for i, entry in enumerate(lb_data[:10]):
                            leaderboard.append({
                                "rank": i + 1,
                                "team": getattr(entry, 'teamName', 'Unknown'),
                                "score": getattr(entry, 'score', 'N/A')
                            })
                    except Exception as lb_err:
                        logger.warning(f"Could not fetch leaderboard for {identifier}: {lb_err}")

                    return CompetitionMetadata(
                        title=comp.title,
                        url=comp.url,
                        description=getattr(comp, 'description', ''),
                        category=getattr(comp, 'category', ''),
                        prize=getattr(comp, 'reward', 'N/A'),
                        evaluation=getattr(comp, 'evaluationMetric', ''),
                        dates=str(getattr(comp, 'deadline', '')),
                        enabled_date=str(getattr(comp, 'enabledDate', '')),
                        max_team_size=getattr(comp, 'maxTeamSize', 0) or 0,
                        max_daily_submissions=getattr(comp, 'maxDailySubmissions', 0) or 0,
                        team_count=getattr(comp, 'teamCount', 0) or 0,
                        leaderboard=leaderboard
                    )
            raise MetadataError(f"Competition {identifier} not found")
        except Exception as e:
            raise MetadataError(f"Failed to fetch competition metadata: {e}")

    def get_dataset_metadata(self, identifier: str, creds: dict | None = None) -> DatasetMetadata:
        api = self.get_client(creds)
        slug = self._extract_slug(identifier)
        try:
            with self._api_semaphore:
                datasets = api.dataset_list(search=slug)
            for ds in datasets:
                if ds.ref == slug:
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
        api = self.get_client(creds)
        files = []
        try:
            with self._api_semaphore:
                if resource_type == "competition":
                    result = api.competition_list_files(identifier)
                    file_objects = getattr(result, 'files', result) if result else []
                else:
                    result = api.dataset_list_files(identifier)
                    file_objects = getattr(result, 'files', result) if result else []

            if not file_objects: return []

            for f in file_objects:
                name = str(f) if isinstance(f, str) else getattr(f, 'name', str(f))
                if name.endswith('.csv'):
                    files.append(name)
            return files
        except Exception as e:
            logger.warning(f"Failed to list files: {e}")
            return []
