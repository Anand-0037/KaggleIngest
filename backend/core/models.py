"""
Pydantic models for type-safe data structures.
"""

from typing import Any

from pydantic import BaseModel, Field, SecretStr, field_validator


class KaggleCredentials(BaseModel):
    """Secure Kaggle API credentials."""

    username: str = Field(..., description="Kaggle username")
    key: SecretStr = Field(..., description="Kaggle API key")

    @field_validator('key')
    @classmethod
    def validate_key_length(cls, v: SecretStr) -> SecretStr:
        if len(v.get_secret_value()) < 20:
            raise ValueError("Invalid Kaggle API key length (must be at least 20 characters)")
        return v

    def to_env_dict(self) -> dict:
        """Return credentials as environment variables (for subprocess)."""
        return {
            "KAGGLE_USERNAME": self.username,
            "KAGGLE_KEY": self.key.get_secret_value()
        }

    def to_dict(self) -> dict:
        """Return as dict for service layer (key exposed)."""
        return {
            "username": self.username,
            "key": self.key.get_secret_value()
        }



class NotebookMeta(BaseModel):
    """Metadata for a Kaggle notebook."""

    ref: str = Field(
        ..., description="Notebook reference (e.g., 'username/notebook-slug')"
    )
    title: str = Field(..., description="Notebook title")
    author: str = Field(..., description="Author username")
    upvotes: int = Field(0, description="Number of upvotes")
    url: str = Field(..., description="Full URL to the notebook")
    last_updated: str | None = Field(None, description="Last run timestamp")
    kernel_type: str | None = Field(None, description="Type: script or notebook")


class NotebookContent(BaseModel):
    """Parsed content from a notebook."""

    markdown: list[str] = Field(default_factory=list, description="Markdown cells")
    code: list[str] = Field(default_factory=list, description="Code cells")


class ColumnInfo(BaseModel):
    """Information about a dataset column."""

    name: str = Field(..., description="Column name")
    dtype: str = Field(..., description="Data type")


class DatasetFileSchema(BaseModel):
    """Schema information for a dataset file."""

    filename: str = Field(..., description="File name")
    columns: list[ColumnInfo] = Field(
        default_factory=list, description="Column information"
    )
    sample_rows: list[list[Any]] = Field(
        default_factory=list, description="Sample data rows"
    )


class CompetitionMetadata(BaseModel):
    """Metadata for a Kaggle competition."""

    title: str = Field(..., description="Competition title")
    url: str = Field(..., description="Competition URL")
    description: str = Field("", description="Competition description")
    category: str = Field("", description="Competition category")
    prize: str = Field("", description="Prize information")
    metric: str = Field("", description="Evaluation metric", alias="evaluation")
    deadline: str = Field("", description="Deadline date", alias="dates")


class DatasetMetadata(BaseModel):
    """Metadata for a Kaggle dataset."""

    title: str = Field(..., description="Dataset title")
    url: str = Field(..., description="Dataset URL")
    description: str = Field("", description="Dataset description")
    last_updated: str = Field("", description="Last update timestamp")


class IngestionStats(BaseModel):
    """Statistics from an ingestion job."""

    successful_downloads: int = Field(0, description="Number of successful downloads")
    failed_downloads: int = Field(0, description="Number of failed downloads")
    failed_notebooks: list[dict] = Field(
        default_factory=list, description="List of failed notebooks with reasons"
    )
    output_file: str = Field(..., description="Path to output file")
    start_time: str = Field("", description="Start timestamp")
    end_time: str = Field("", description="End timestamp")
    elapsed_time: float = Field(0.0, description="Elapsed time in seconds")
    elapsed_time_formatted: str = Field("", description="Human-readable elapsed time")
    notebooks_per_second: float = Field(0.0, description="Processing speed")
