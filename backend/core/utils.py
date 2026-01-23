import re
import json
import asyncio
from typing import Optional, Dict, Any, Tuple
from urllib.parse import urlparse, unquote
from backend.core.exceptions import URLParseError
from backend.logger import get_logger
import tiktoken

# Cache tiktoken encoding at module level (expensive to load)
_TOKEN_ENCODING = None

# Security constants
MAX_URL_LENGTH = 2048
SAFE_SLUG_PATTERN = re.compile(r'^[\w\-\.]+$')
VALID_KAGGLE_ORIGINS = ('https://www.kaggle.com/', 'https://kaggle.com/')

def extract_resource(url: str) -> dict:
    """Extract resource from Kaggle URL with comprehensive validation.

    Args:
        url: Kaggle URL to parse

    Returns:
        dict with 'type' and 'id' keys

    Raises:
        URLParseError: If URL is invalid or malformed
    """
    if not url or not isinstance(url, str):
        raise URLParseError("URL must be a non-empty string")

    # Length check to prevent DoS
    if len(url) > MAX_URL_LENGTH:
        raise URLParseError(f"URL exceeds maximum length of {MAX_URL_LENGTH} characters")

    url = url.strip().split("?")[0].split("#")[0].rstrip("/")

    # Origin validation
    if not any(url.startswith(origin) for origin in VALID_KAGGLE_ORIGINS):
        raise URLParseError("URL must be a valid Kaggle URL (https://www.kaggle.com/...)")

    if "/datasets/" in url:
        parts = url.split("/datasets/")[-1].split("/")
        if len(parts) >= 2:
            owner, slug = parts[0], parts[1]
            # Validate slug format
            if not SAFE_SLUG_PATTERN.match(owner) or not SAFE_SLUG_PATTERN.match(slug):
                raise URLParseError("Invalid dataset identifier format")
            return {"type": "dataset", "id": f"{owner}/{slug}"}

    if "/competitions/" in url:
        comp_id = url.split("/competitions/")[-1].split("/")[0]
        if not SAFE_SLUG_PATTERN.match(comp_id):
            raise URLParseError("Invalid competition identifier format")
        return {"type": "competition", "id": comp_id}

    if "/c/" in url:
        comp_id = url.split("/c/")[-1].split("/")[0]
        if not SAFE_SLUG_PATTERN.match(comp_id):
            raise URLParseError("Invalid competition identifier format")
        return {"type": "competition", "id": comp_id}

    raise URLParseError(f"Could not parse Kaggle resource from URL: {url}")


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


async def fetch_competition_overview(identifier: str) -> dict:
    """
    Fetch competition overview (description, evaluation metric, rules) from Kaggle webpage.

    Args:
        identifier: Competition slug (e.g., 'titanic')

    Returns:
        dict with 'overview', 'evaluation', 'rules' keys
    """
    import aiohttp
    from bs4 import BeautifulSoup

    logger = get_logger(__name__)
    result = {
        'overview': '',
        'evaluation': '',
        'rules': ''
    }

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }

    async def fetch_page(session, path: str) -> str:
        url = f"https://www.kaggle.com/competitions/{identifier}/{path}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    return await resp.text()
        except Exception as e:
            logger.warning(f"Failed to fetch {url}: {e}")
        return ""

    def extract_text(html: str) -> str:
        if not html:
            return ""
        soup = BeautifulSoup(html, 'html.parser')
        # Find main content area
        content = soup.find('div', {'class': 'markdown-body'}) or soup.find('div', {'id': 'description'})
        if content:
            return content.get_text(separator='\n', strip=True)[:2000]  # Limit to 2000 chars
        return ""

    try:
        # Create session once and reuse
        async with aiohttp.ClientSession(headers=headers) as session:
            # Fetch overview and rules concurrently
            overview_html, rules_html = await asyncio.gather(
                fetch_page(session, "overview"),
                fetch_page(session, "rules"),
                return_exceptions=True
            )

            # Handle potential exceptions from gather
            if isinstance(overview_html, Exception): overview_html = ""
            if isinstance(rules_html, Exception): rules_html = ""

            result['overview'] = extract_text(overview_html)
            result['rules'] = extract_text(rules_html)

            # Try to extract evaluation metric from overview or separate page if needed
            # For efficiency we just check overview first
            if 'evaluation' in overview_html.lower() or 'metric' in overview_html.lower():
                result['evaluation'] = "See overview for metric details."
            else:
                 # Optional: fetch evaluation page if not found
                 pass

    except Exception as e:
        logger.warning(f"Error fetching competition overview: {e}")

    return result
