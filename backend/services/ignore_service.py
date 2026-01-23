import pathspec
import logging
from typing import List, Optional
from backend.config import DEFAULT_IGNORE_PATTERNS

logger = logging.getLogger(__name__)

class IgnoreService:
    def __init__(self, additional_patterns: Optional[List[str]] = None):
        patterns = DEFAULT_IGNORE_PATTERNS.copy()
        if additional_patterns:
            patterns.extend(additional_patterns)

        self.spec = pathspec.PathSpec.from_lines('gitwildmatch', patterns)

    def should_ignore(self, file_path: str) -> bool:
        """
        Check if a file path should be ignored based on the patterns.
        """
        try:
            return self.spec.match_file(file_path)
        except Exception as e:
            logger.error(f"Error matching ignore pattern for {file_path}: {e}")
            return False

    def filter_paths(self, file_paths: List[str]) -> List[str]:
        """
        Filter a list of paths, returning only those that are NOT ignored.
        """
        return [p for p in file_paths if not self.should_ignore(p)]
