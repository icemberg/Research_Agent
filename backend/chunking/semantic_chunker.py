"""
Contextual Semantic Chunker — the heart of retrieval accuracy.

Strategy (combines best practices from Anthropic's Contextual Retrieval + semantic splitting):

1. **Paragraph-aware splitting**: Splits on natural boundaries (paragraphs, headings)
   instead of blind character/token counts. No fact is severed mid-sentence.

2. **Contextual prefix** (Anthropic-style): Each chunk gets a context prefix that
   situates it within the document. Example: "This passage is from the document
   'Climate Report 2024', Section: 'Temperature Projections'. It discusses..."
   This dramatically improves retrieval because an isolated chunk like "It increased
   by 1.5°C" becomes "This passage from Climate Report, Section Temperature
   Projections, discusses temperature increase of 1.5°C" — now the embedding
   captures the full meaning.

3. **Overlap with sentence boundaries**: Overlap is not a fixed character count
   but extends to the nearest sentence boundary, ensuring no fact is split.

4. **Hash-based dedup**: id = sha256(source + text) for idempotent re-ingestion.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from backend.config import settings
from backend.loaders.base import LoadedSection
from backend.models.passage import Passage, PassageSource

logger = logging.getLogger(__name__)

# Sentence boundary regex — handles ., !, ? followed by space or EOL
SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return len(text) // 4


def _generate_passage_id(source_name: str, text: str) -> str:
    """Deterministic ID for dedup — same source+text always gives same ID."""
    content = f"{source_name}::{text}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _build_context_prefix(source_name: str, metadata: dict) -> str:
    """
    Build an Anthropic-style contextual prefix for the chunk.
    This is prepended to the chunk text during embedding (not during display)
    so that the vector captures the document-level context.
    """
    parts = [f"From document '{source_name}'"]

    if "section_heading" in metadata:
        parts.append(f"Section: '{metadata['section_heading']}'")
    if "page_number" in metadata:
        parts.append(f"Page {metadata['page_number']}")
    if "row_number" in metadata:
        parts.append(f"Row {metadata['row_number']}")

    return ", ".join(parts) + ". "


def _split_into_sentences(text: str) -> list[str]:
    """Split text into sentences, preserving sentence integrity."""
    sentences = SENTENCE_BOUNDARY.split(text)
    # Clean up: remove empty strings and strip whitespace
    return [s.strip() for s in sentences if s.strip()]


class SemanticChunker:
    """
    Chunks documents with contextual awareness and semantic boundaries.

    Config-driven: chunk_size and chunk_overlap come from settings (Open/Closed).
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap

    def chunk_sections(
        self,
        sections: list[LoadedSection],
        source_name: str,
    ) -> list[Passage]:
        """
        Convert loaded sections into Passage objects with contextual prefixes.

        This is the main entry point — takes the raw sections from a loader
        and produces the final Passage objects ready for embedding.
        """
        passages: list[Passage] = []
        seen_ids: set[str] = set()

        # Build a brief document summary from all section headings
        # (used for richer context prefixes)
        doc_headings = []
        for section in sections:
            heading = section.metadata.get("section_heading", "")
            if heading and heading not in doc_headings:
                doc_headings.append(heading)

        for section in sections:
            section_chunks = self._chunk_section(section, source_name, doc_headings)
            for passage in section_chunks:
                if passage.id not in seen_ids:
                    seen_ids.add(passage.id)
                    passages.append(passage)
                else:
                    logger.debug(f"Dedup: skipping duplicate chunk {passage.id}")

        logger.info(
            f"Chunked '{source_name}': {len(sections)} sections → {len(passages)} passages"
        )
        return passages

    def _chunk_section(
        self,
        section: LoadedSection,
        source_name: str,
        doc_headings: list[str],
    ) -> list[Passage]:
        """Split a single section into overlapping, sentence-aligned chunks."""
        text = section.text.strip()
        if not text:
            return []

        # Build the contextual prefix for this section
        context_prefix = _build_context_prefix(source_name, section.metadata)

        # If the section is small enough, keep it whole
        if _estimate_tokens(text) <= self.chunk_size:
            passage_id = _generate_passage_id(source_name, text)
            return [
                Passage(
                    id=passage_id,
                    text=text,
                    source_name=source_name,
                    location=section.metadata.get("location", ""),
                    source_type=PassageSource.DOCUMENT,
                    metadata=section.metadata,
                    context_prefix=context_prefix,
                )
            ]

        # Split into sentences for sentence-boundary-aware chunking
        sentences = _split_into_sentences(text)
        if not sentences:
            return []

        passages: list[Passage] = []
        current_chunk_sentences: list[str] = []
        current_tokens = 0

        for sentence in sentences:
            sentence_tokens = _estimate_tokens(sentence)

            # If adding this sentence would exceed chunk_size, flush
            if current_tokens + sentence_tokens > self.chunk_size and current_chunk_sentences:
                chunk_text = " ".join(current_chunk_sentences)
                passage_id = _generate_passage_id(source_name, chunk_text)

                passages.append(
                    Passage(
                        id=passage_id,
                        text=chunk_text,
                        source_name=source_name,
                        location=section.metadata.get("location", ""),
                        source_type=PassageSource.DOCUMENT,
                        metadata={
                            **section.metadata,
                            "chunk_index": len(passages),
                        },
                        context_prefix=context_prefix,
                    )
                )

                # Overlap: keep the last few sentences for context continuity
                overlap_sentences: list[str] = []
                overlap_tokens = 0
                for s in reversed(current_chunk_sentences):
                    s_tokens = _estimate_tokens(s)
                    if overlap_tokens + s_tokens > self.chunk_overlap:
                        break
                    overlap_sentences.insert(0, s)
                    overlap_tokens += s_tokens

                current_chunk_sentences = overlap_sentences
                current_tokens = overlap_tokens

            current_chunk_sentences.append(sentence)
            current_tokens += sentence_tokens

        # Flush remaining
        if current_chunk_sentences:
            chunk_text = " ".join(current_chunk_sentences)
            passage_id = _generate_passage_id(source_name, chunk_text)
            passages.append(
                Passage(
                    id=passage_id,
                    text=chunk_text,
                    source_name=source_name,
                    location=section.metadata.get("location", ""),
                    source_type=PassageSource.DOCUMENT,
                    metadata={
                        **section.metadata,
                        "chunk_index": len(passages),
                    },
                    context_prefix=context_prefix,
                )
            )

        return passages
