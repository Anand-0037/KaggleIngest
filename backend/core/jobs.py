from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, validator


class JobStatus(str, Enum):
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class IngestRequestBody(BaseModel):
    """Request body for POST /get-context endpoint."""
    url: str = Field(..., description="Kaggle competition or dataset URL")
    top_n: int = Field(10, ge=1, le=10, description="Number of notebooks to fetch")
    output_format: str = Field("toon", pattern="^(txt|toon|md)$", description="Output format")
    dry_run: bool = Field(False, description="Validate only without downloading")
    stream: bool = Field(True, description="Stream response to reduce memory")

    @validator('url')
    def validate_url(cls, v):
        """Ensure URL is not empty and looks like a Kaggle URL."""
        if not v or not v.strip():
            raise ValueError("URL cannot be empty")
        if "kaggle.com" not in v.lower():
            raise ValueError("URL must be a valid Kaggle URL")
        return v.strip()

class JobRequest(BaseModel):
    resource_type: str
    identifier: str
    top_n: int
    format_type: str
    kaggle_creds: dict[str, str] | None = None
    dry_run: bool = False

class JobResult(BaseModel):
    job_id: str
    status: JobStatus
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = None

class JobResponse(BaseModel):
    job_id: str
    status: JobStatus
    message: str
