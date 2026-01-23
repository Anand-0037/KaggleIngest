
# backend/api/auth.py

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, EmailStr
from backend.core.database import get_db
from backend.core.security import generate_api_key, hash_password, verify_api_key
import asyncpg

router = APIRouter(prefix="/auth", tags=["Authentication"])

class SignupRequest(BaseModel):
    email: EmailStr
    password: str

class SignupResponse(BaseModel):
    message: str
    api_key: str
    instructions: str

@router.post("/signup", response_model=SignupResponse)
async def signup(
    request: SignupRequest,
    db: asyncpg.Pool = Depends(get_db)
):
    """
    Create new user account and generate API key.
    No OAuth needed - simple email/password + API key.
    """
    # Validate password strength
    if len(request.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")

    # Generate API key and hash password
    api_key = generate_api_key()
    password_hash = hash_password(request.password)

    try:
        # Insert user
        await db.execute(
            """
            INSERT INTO users (email, password_hash, api_key, tier, credits)
            VALUES ($1, $2, $3, 'free', 10)
            """,
            request.email,
            password_hash,
            api_key
        )

        return SignupResponse(
            message="Account created successfully",
            api_key=api_key,
            instructions="Add 'X-API-Key: <your_key>' header to all API requests"
        )

    except asyncpg.UniqueViolationError:
        raise HTTPException(409, "Email already registered")
    except Exception as e:
        raise HTTPException(500, f"Signup failed: {str(e)}")

@router.get("/me")
async def get_current_user(
    # Note: verify_api_key returns dict, valid injection
    user: dict = Depends(verify_api_key),
    db: asyncpg.Pool = Depends(get_db)
):
    """Get current user info."""
    return {
        "email": user['email'],
        "tier": user['tier'],
        "credits": user['credits'],
        "created_at": user['created_at']
    }
