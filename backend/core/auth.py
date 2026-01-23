
from fastapi import Header, HTTPException
from typing import Optional
from backend.db.session import get_db_pool
import logging

logger = logging.getLogger(__name__)

async def verify_api_key_db(x_api_key: Optional[str] = Header(None, alias="X-API-Key")):
    """
    Verify API key against the database.
    Updates last_request_at on success.
    """
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing X-API-Key header")

    pool = await get_db_pool()

    # Check key and update timestamp in one go (if possible) or fetch then update
    # Simple check for now
    row = await pool.fetchrow(
        "SELECT id FROM users WHERE api_key = $1",
        x_api_key
    )

    if not row:
        raise HTTPException(status_code=403, detail="Invalid API key")

    # Async update (fire and forget logic or await? await is safer for correctness)
    try:
        await pool.execute(
            "UPDATE users SET last_request_at = NOW() WHERE id = $1",
            row['id']
        )
    except Exception as e:
        logger.warning(f"Failed to update last_request_at for user {row['id']}: {e}")

    return row
