import tiktoken

from core.exceptions import URLParseError

# Cache tiktoken encoding at module level (expensive to load)
_TOKEN_ENCODING = None

def extract_resource(url: str) -> dict:
    """Helper to extract resource from URL."""
    if not url or not isinstance(url, str):
        raise URLParseError("URL must be a non-empty string")

    url = url.strip().split("?")[0].split("#")[0].rstrip("/")

    if "/datasets/" in url:
        parts = url.split("/datasets/")[-1].split("/")
        if len(parts) >= 2:
            return {"type": "dataset", "id": f"{parts[0]}/{parts[1]}"}

    if "/competitions/" in url:
        comp_id = url.split("/competitions/")[-1].split("/")[0]
        return {"type": "competition", "id": comp_id}

    if "/c/" in url:
        comp_id = url.split("/c/")[-1].split("/")[0]
        return {"type": "competition", "id": comp_id}

    raise URLParseError(f"Invalid Kaggle URL format: {url}")


def format_time(seconds: float) -> str:
    """Format seconds into human-readable time."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count tokens for a given text using tiktoken (cached encoding)."""
    global _TOKEN_ENCODING
    if _TOKEN_ENCODING is None:
        try:
            _TOKEN_ENCODING = tiktoken.encoding_for_model(model)
        except Exception:
            _TOKEN_ENCODING = tiktoken.get_encoding("cl100k_base")
    return len(_TOKEN_ENCODING.encode(text))
