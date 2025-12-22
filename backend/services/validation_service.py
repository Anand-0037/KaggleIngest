"""
Validation service for request inputs.
Centralizes validation logic to keep endpoints clean.
"""

import json

from fastapi import HTTPException, UploadFile


class ValidationService:
    """Handles validation for API requests."""

    MAX_CREDENTIAL_FILE_SIZE = 10240  # 10KB

    @staticmethod
    async def validate_and_read_token_file(
        token_file: UploadFile | None
    ) -> dict[str, str] | None:
        """
        Validate and read Kaggle credentials file.

        Critical Fix: Check file size BEFORE reading to prevent DoS attacks.

        Args:
            token_file: Uploaded credential file

        Returns:
            Dictionary with username and key, or None if no file

        Raises:
            HTTPException: If file is too large or invalid
        """
        if not token_file:
            return None

        # SECURITY FIX: Check size before reading
        # Read only up to MAX_SIZE + 1 byte to detect oversized files
        content = await token_file.read(ValidationService.MAX_CREDENTIAL_FILE_SIZE + 1)

        if len(content) > ValidationService.MAX_CREDENTIAL_FILE_SIZE:
            raise HTTPException(
                status_code=413,
                detail=f"Credentials file too large (max {ValidationService.MAX_CREDENTIAL_FILE_SIZE} bytes)"
            )

        # Parse JSON
        try:
            creds = json.loads(content)
            username = creds.get("username")
            key = creds.get("key")

            if not username or not key:
                raise HTTPException(
                    status_code=400,
                    detail="Credentials file must contain 'username' and 'key' fields"
                )

            return {"username": username, "key": key}

        except json.JSONDecodeError as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid JSON in credentials file: {e}"
            )
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Failed to parse credentials file: {e}"
            )
