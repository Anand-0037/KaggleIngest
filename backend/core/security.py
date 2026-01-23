# backend/core/security.py

from fastapi import Header, HTTPException, Request, Depends
from typing import Optional
import asyncpg
import hashlib
import secrets
from slowapi import Limiter
from slowapi.util import get_remote_address

from backend.core.database import get_db

async def verify_api_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"), # Alias for standard header
    db: asyncpg.Pool = Depends(get_db)
) -> dict:
    """
    Verify API key and return user object.
    This is your authentication middleware.
    """
    if not x_api_key:
        raise HTTPException(
            status_code=401,
            detail="Missing X-API-Key header. Get your key at https://kaggleingest.com/dashboard"
        )

    # Query user from database
    user = await db.fetchrow(
        "SELECT * FROM users WHERE api_key = $1",
        x_api_key
    )

    if not user:
        raise HTTPException(
            status_code=403,
            detail="Invalid API key"
        )

    # Update last request timestamp (Fire and forget optimization or async await?)
    # Await ensures it happens, but adds latency. For simple MVP, await is fine.
    try:
        await db.execute(
            "UPDATE users SET last_request_at = NOW() WHERE id = $1",
            user['id']
        )
    except Exception as e:
        logger.warning(f"Failed to update user stats after login: {e}")

    return dict(user)

def get_real_client_ip(request: Request) -> str:
    """
    Extract real client IP from X-Forwarded-For header.
    CRITICAL for rate limiting behind load balancers.
    """
    forwarded_for = request.headers.get("x-forwarded-for")

    if forwarded_for:
        # X-Forwarded-For: client, proxy1, proxy2
        # Split and check loop
        for ip in forwarded_for.split(","):
            ip = ip.strip()
            # Validate it's not a private IP
            # Simple prefix check
            if not (ip.startswith("10.") or
                    ip.startswith("192.168.") or
                    (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31) or
                    ip.startswith("127.")):
                return ip

        # If all private, return first
        return forwarded_for.split(",")[0].strip()

    # Fallback to direct connection (dev environment)
    return request.client.host if request.client else "127.0.0.1"

# Initialize Limiter with our real IP extractor
limiter = Limiter(key_func=get_real_client_ip)

def generate_api_key() -> str:
    """Generate secure API key for new users."""
    return f"ki_{secrets.token_urlsafe(32)}"

def hash_password(password: str) -> str:
    """Hash password using SHA256 (upgrade to bcrypt later)."""
    return hashlib.sha256(password.encode()).hexdigest()
