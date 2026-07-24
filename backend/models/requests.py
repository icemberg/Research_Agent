"""Request/response models for the API and CLI."""

from __future__ import annotations

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Metadata for a document ingestion request (files come via multipart)."""
    pass  # Files are uploaded via multipart form data


class IngestResponse(BaseModel):
    """Response after ingesting a document."""
    document_id: str
    name: str
    chunk_count: int
    status: str = "indexed"


class AskRequest(BaseModel):
    """Request body for /api/v1/ask."""
    question: str = Field(..., min_length=1, description="The research question")
    document_ids: list[str] | None = Field(
        default=None,
        description="Optional: restrict to specific documents. None = search all.",
    )
    allow_web_search: bool = Field(
        default=False,
        description="Allow web search when corpus is insufficient",
    )
