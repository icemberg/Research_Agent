"""
Core data models shared across every pipeline component.

Passage is the atomic unit of evidence — everything from chunking through
citation validation speaks this schema.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class PassageSource(str, Enum):
    """Where a passage originated."""
    DOCUMENT = "document"
    WEB_SEARCH = "web_search"


class Passage(BaseModel):
    """A single chunk of evidence with full provenance metadata."""
    id: str = Field(..., description="Deterministic hash of source_name + text")
    text: str = Field(..., description="Chunk text content")
    source_name: str = Field(..., description="Original document name or URL")
    location: str = Field(
        default="",
        description="Page number, section heading, paragraph index, or URL",
    )
    source_type: PassageSource = Field(default=PassageSource.DOCUMENT)
    metadata: dict = Field(default_factory=dict)
    score: float = Field(default=0.0, description="Retrieval / re-rank score")
    context_prefix: str = Field(
        default="",
        description="Contextual prefix prepended during chunking (Anthropic-style)",
    )


class Citation(BaseModel):
    """A single citation linking a marker number to its source passage."""
    marker: int = Field(..., description="Citation marker number, e.g. 1 for [1]")
    source: str = Field(..., description="Source document name or URL")
    location: str = Field(..., description="Page, section, or URL path")
    snippet: str = Field(..., description="Exact passage text used as evidence")


class AnswerResponse(BaseModel):
    """Complete response from the research agent."""
    answer_text: str = Field(default="", description="Synthesized answer with [n] markers")
    citations: list[Citation] = Field(default_factory=list)
    abstained: bool = Field(default=False, description="True if agent couldn't answer")
    confidence_note: str = Field(default="")
    latency_ms: float = Field(default=0.0)
    question_id: str = Field(default="")
    question: str = Field(default="")
    created_at: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
    )


class DocumentInfo(BaseModel):
    """Metadata for an ingested document."""
    document_id: str
    name: str
    chunk_count: int = 0
    upload_time: str = Field(
        default_factory=lambda: datetime.now().isoformat(),
    )
    file_size_bytes: int = 0
    status: str = "indexed"
