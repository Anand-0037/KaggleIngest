class KaggleIngestionError(Exception):
    """Base exception for Kaggle ingestion errors."""
    pass


class URLParseError(KaggleIngestionError):
    """Error parsing Kaggle URL."""
    pass


class NotebookDownloadError(KaggleIngestionError):
    """Error downloading notebooks."""
    pass


class MetadataError(KaggleIngestionError):
    """Error fetching metadata."""
    pass
